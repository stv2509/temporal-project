"""Worker runtime runner with domain registry support."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker, WorkerDeploymentConfig, WorkerDeploymentVersion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Корень репозитория в path для импорта worker.*
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
load_dotenv(_repo_root / ".env")

from worker.registry import get_domain_registration  # noqa: E402


def _resolve_temporal_target() -> str:
    """K8s worker-controller задаёт TEMPORAL_ADDRESS; локально обычно TEMPORAL_HOST."""
    return (
        os.environ.get("TEMPORAL_ADDRESS", "").strip()
        or os.environ.get("TEMPORAL_HOST", "localhost:7233").strip()
    )


def _worker_deployment_config_from_env() -> WorkerDeploymentConfig | None:
    """Включаем versioning, если заданы обе env-переменные (в K8s их задаёт контроллер)."""
    deployment_name = os.environ.get("TEMPORAL_DEPLOYMENT_NAME", "").strip()
    build_id = os.environ.get("TEMPORAL_WORKER_BUILD_ID", "").strip()
    if deployment_name and build_id:
        return WorkerDeploymentConfig(
            version=WorkerDeploymentVersion(
                deployment_name=deployment_name,
                build_id=build_id,
            ),
            use_worker_versioning=True,
        )
    if deployment_name or build_id:
        logger.warning(
            "Worker versioning отключён: в окружении только одна из "
            "TEMPORAL_DEPLOYMENT_NAME / TEMPORAL_WORKER_BUILD_ID. "
            "В K8s обе обычно подставляет temporal-worker-controller — "
            "если так и должно быть, проверьте Pod и оператор. "
            "Локально без контроллера задайте обе в .env сами, если нужен UI versioning."
        )
    return None


async def run_worker() -> None:
    domain_key = os.environ.get("WORKER_DOMAIN", "k8s_access").strip().lower()
    registration = get_domain_registration(domain_key)

    temporal_target = _resolve_temporal_target()
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = registration.resolve_task_queue()
    deployment_config = _worker_deployment_config_from_env()

    client = await Client.connect(temporal_target, namespace=temporal_namespace)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=registration.workflows,
        activities=registration.activities,
        deployment_config=deployment_config,
    )
    logger.info(
        "Worker starting: domain=%s address=%s namespace=%s task_queue=%s worker_versioning=%s",
        domain_key,
        temporal_target,
        temporal_namespace,
        task_queue,
        deployment_config is not None,
    )
    await worker.run()
