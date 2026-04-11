"""Понятные сообщения при сбоях TCP/подключения к HTTP-сервисам из воркера."""

import httpx
from temporalio.exceptions import ApplicationError


def raise_backend_http_400_hint(*, method: str, url: str, exc: httpx.HTTPStatusError) -> None:
    """HTTP 400 от Django: часто DisallowedHost для внутреннего Host (имя K8s Service)."""
    host = exc.request.headers.get("host", "")
    msg = (
        f"Django вернул HTTP 400 ({method} {url!r}, Host={host!r}). "
        "Если воркер ходит на backend по внутреннему URL кластера (`http://autoops-backend/...`), "
        "заголовок Host совпадает с именем Service — его нужно разрешить в Django: "
        "добавьте имя Service в ALLOWED_HOSTS Django (см. .env.example)."
    )
    body = (exc.response.text or "").strip()
    if body:
        msg += f" Фрагмент ответа: {body[:600]!r}"
    raise ApplicationError(msg, non_retryable=True) from exc


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
