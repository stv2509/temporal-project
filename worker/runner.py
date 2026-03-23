"""Worker runtime runner with domain registry support."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Корень репозитория в path для импорта worker.*
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
load_dotenv(_repo_root / ".env")

from worker.registry import get_domain_registration  # noqa: E402


async def run_worker() -> None:
    domain_key = os.environ.get("WORKER_DOMAIN", "k8s_access").strip().lower()
    registration = get_domain_registration(domain_key)

    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = registration.resolve_task_queue()

    client = await Client.connect(temporal_host, namespace=temporal_namespace)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=registration.workflows,
        activities=registration.activities,
    )
    logger.info(
        "Worker starting: domain=%s host=%s namespace=%s task_queue=%s",
        domain_key,
        temporal_host,
        temporal_namespace,
        task_queue,
    )
    await worker.run()
