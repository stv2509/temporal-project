"""Workflow проверки сетевого доступа K8s: заявка → AWX job → обновление статуса."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from worker.activities import (
        get_request_data,
        launch_awx_job,
        update_request_status,
    )


@workflow.defn
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
            await workflow.execute_activity(
                launch_awx_job,
                args=[awx_template_id, host_dst, port_dst],
                start_to_close_timeout=timedelta(minutes=10),
            )
            await workflow.execute_activity(
                update_request_status,
                args=[ticket_id, "success"],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"status": "success"}
        except Exception as e:
            workflow.logger.exception("AWX job failed: %s", e)
            await workflow.execute_activity(
                update_request_status,
                args=[ticket_id, "failed"],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return {"status": "failed", "reason": str(e)}
