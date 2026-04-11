"""Понятные сообщения при сбоях TCP/подключения к HTTP-сервисам из воркера."""

import httpx
from temporalio.exceptions import ApplicationError


def raise_backend_connect_failed(
    *,
    base_url: str,
    method: str,
    url: str,
    exc: Exception,
) -> None:
    """Соединение с Django (BACKEND_API_URL) не установилось — явная ошибка для логов/UI."""
    msg = (
        f"Не удалось подключиться к Django backend ({method} {url}). "
        f"BACKEND_API_URL (база): {base_url!r}. "
        "Проверьте: хост резолвится, порт открыт, в K8s — Service в том же namespace, "
        "что Pod воркера (или полный DNS *.svc.cluster.local), нет блокирующей "
        "NetworkPolicy. См. .env.example (BACKEND_API_URL). "
        f"Исходная ошибка: {type(exc).__name__}: {exc}"
    )
    raise ApplicationError(msg, non_retryable=True) from exc


def is_backend_connection_error(exc: Exception) -> bool:
    return isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout))
