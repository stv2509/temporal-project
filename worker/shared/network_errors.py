"""Понятные сообщения при сбоях TCP/подключения к HTTP-сервисам из воркера."""

import httpx
from temporalio.exceptions import ApplicationError


def connect_failure_extra_hint(exc: BaseException) -> str:
    """Доп. текст при типичном сбое резолва имени (getaddrinfo / DNS в Pod)."""
    s = str(exc).lower()
    if (
        "name or service not known" in s
        or "nodename nor servname" in s
        or "failed to resolve" in s
        or ("errno -2" in s and "name" in s)
    ):
        return (
            " Похоже на DNS: имя хоста из URL не резолвится в этом контейнере. "
            "В K8s проверьте имя Service (`kubectl get svc`), namespace Pod, "
            "при межnamespace — FQDN `<service>.<namespace>.svc.cluster.local` и порт в URL."
        )
    return ""


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
    msg += connect_failure_extra_hint(exc)
    raise ApplicationError(msg, non_retryable=True) from exc
