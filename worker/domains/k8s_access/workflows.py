"""Workflow домена k8s_access: заявка → AWX job → обновление статуса."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import VersioningBehavior
from temporalio.exceptions import is_cancelled_exception

with workflow.unsafe.imports_passed_through():
    from worker.domains.k8s_access.activities import (
        get_awx_job_status,
        get_request_data,
        launch_awx_job,
        update_request_status,
    )

AWX_TERMINAL_STATUSES = frozenset({"successful", "failed", "error", "canceled"})
POLL_INTERVAL_SEC = 30
POLL_MAX_ITERATIONS = 20  # 20 * 30s = 10 min max ожидания


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class K8sAccessCheckWorkflow:
    """Workflow: получить данные заявки → запустить AWX job → обновить статус (success/failed)."""

    @workflow.run
    async def run(self, ticket_id: str) -> dict:
        request_data = await workflow.execute_activity(
            get_request_data,
            args=[ticket_id],
            start_to_close_timeout=timedelta(seconds=30),
        )
        normalized = request_data.get("normalized") or {}
        awx_template_id = normalized.get("awx_template_id")
        host_dst = normalized.get("dst_host", "")
        port_dst = int(normalized.get("dst_port", 0))

        if not awx_template_id or not host_dst or not port_dst:
            await workflow.execute_activity(
                update_request_status,
                args=[ticket_id, "failed"],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"status": "failed", "reason": "missing normalized fields"}

        try:
            launch_result = await workflow.execute_activity(
                launch_awx_job,
                args=[awx_template_id, host_dst, port_dst],
                start_to_close_timeout=timedelta(minutes=2),
            )
            job_id = launch_result.get("job_id")
            if not job_id:
                await workflow.execute_activity(
                    update_request_status,
                    args=[ticket_id, "failed"],
                    start_to_close_timeout=timedelta(seconds=15),
                )
                return {"status": "failed", "reason": "no job_id from AWX"}

            job_status = {"status": "pending", "message": None}
            for _ in range(POLL_MAX_ITERATIONS):
                await workflow.sleep(timedelta(seconds=POLL_INTERVAL_SEC))
                job_status = await workflow.execute_activity(
                    get_awx_job_status,
                    args=[job_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                if job_status.get("status") in AWX_TERMINAL_STATUSES:
                    break

            awx_final_status = job_status.get("status", "unknown")
            request_status = "success" if awx_final_status == "successful" else "failed"
            awx_payload = {
                "job_id": job_id,
                "status": awx_final_status,
                "message": job_status.get("message"),
            }
            await workflow.execute_activity(
                update_request_status,
                args=[ticket_id, request_status, awx_payload],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"status": request_status, "awx_status": awx_final_status}
        except BaseException as e:
            if is_cancelled_exception(e):
                # Ручная отмена: не глотаем — Temporal покажет Canceled, а не Completed.
                try:
                    await workflow.execute_activity(
                        update_request_status,
                        args=[ticket_id, "canceled"],
                        start_to_close_timeout=timedelta(seconds=15),
                    )
                except BaseException:
                    workflow.logger.exception(
                        "update_request_status(canceled) при отмене workflow: ticket_id=%s",
                        ticket_id,
                    )
                raise
            if not isinstance(e, Exception):
                raise
            workflow.logger.exception("AWX job failed: %s", e)
            await workflow.execute_activity(
                update_request_status,
                args=[ticket_id, "failed"],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"status": "failed", "reason": str(e)}
