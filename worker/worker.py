"""Backward-compatible entrypoint for worker runner."""

import asyncio
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any


def _get_run_worker() -> Callable[[], Coroutine[Any, Any, None]]:
    if __package__:
        from worker.runner import run_worker as run_worker_pkg

        return run_worker_pkg
    # Поддержка запуска как файла: python worker/worker.py
    worker_dir = Path(__file__).resolve().parent
    if str(worker_dir) not in sys.path:
        sys.path.insert(0, str(worker_dir))
    from runner import run_worker as run_worker_script  # type: ignore[import-not-found]

    return run_worker_script


run_worker = _get_run_worker()

if __name__ == "__main__":
    asyncio.run(run_worker())
