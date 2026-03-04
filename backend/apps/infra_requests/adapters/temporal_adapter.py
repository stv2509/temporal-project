"""Адаптер для запуска workflow в Temporal."""

import asyncio
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class TemporalAdapter:
    """Запуск workflow в Temporal. Хост и параметры — из Django settings/env."""

    def __init__(
        self,
        host: str | None = None,
        namespace: str | None = None,
        task_queue: str | None = None,
    ) -> None:
        self._host = host or getattr(settings, "TEMPORAL_HOST", "localhost:7233")
        self._namespace = namespace or getattr(
            settings, "TEMPORAL_NAMESPACE", "default"
        )
        self._task_queue = task_queue or getattr(
            settings, "TEMPORAL_TASK_QUEUE", "awx-task-queue"
        )

    async def start_workflow_async(
        self,
        workflow_id: str,
        workflow_name: str,
        args: list[Any],
    ) -> None:
        """Запустить workflow в Temporal (async). При WorkflowAlreadyStarted — не бросать ошибку."""
        from temporalio.client import Client
        from temporalio.exceptions import WorkflowAlreadyStartedError

        host = str(self._host or "localhost:7233")
        namespace = str(self._namespace or "default")
        task_queue = str(self._task_queue or "awx-task-queue")
        client = await Client.connect(host, namespace=namespace)
        try:
            await client.start_workflow(  # type: ignore[arg-type]
                workflow_name,
                *args,
                id=workflow_id,
                task_queue=task_queue,
            )
            logger.info("Started workflow %s id=%s", workflow_name, workflow_id)
        except WorkflowAlreadyStartedError:
            logger.info("Workflow already running id=%s", workflow_id)
        except Exception as e:
            logger.exception("Failed to start workflow id=%s: %s", workflow_id, e)
            raise

    def start_workflow(
        self,
        workflow_id: str,
        workflow_name: str,
        args: list[Any],
    ) -> None:
        """Синхронная обёртка: запустить workflow (для вызова из Django view)."""
        asyncio.run(self.start_workflow_async(workflow_id, workflow_name, args))
