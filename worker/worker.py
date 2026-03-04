"""Temporal worker: K8s access check workflow и activities."""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Корень репозитория в path для импорта worker.activities / worker.workflows
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
load_dotenv(_repo_root / ".env")

from temporalio.client import Client  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from worker import activities  # noqa: E402
from worker.workflows import K8sAccessCheckWorkflow  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "awx-task-queue")


async def main() -> None:
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[K8sAccessCheckWorkflow],
        activities=[
            activities.get_request_data,
            activities.get_awx_job_status,
            activities.launch_awx_job,
            activities.update_request_status,
        ],
    )
    logger.info(
        "Worker starting: host=%s namespace=%s task_queue=%s",
        TEMPORAL_HOST,
        TEMPORAL_NAMESPACE,
        TEMPORAL_TASK_QUEUE,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
