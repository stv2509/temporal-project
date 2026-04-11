"""Понятные сообщения при сбоях TCP/подключения к HTTP-сервисам из воркера."""

from urllib.parse import urlparse

import httpx
from temporalio.exceptions import ApplicationError


def http_url_hostname(url: str) -> str | None:
    """Имя хоста из http(s)://... или None."""
    try:
        h = urlparse(url).hostname
        return h if h else None
    except ValueError:
        return None


def temporal_target_hostname(target: str) -> str | None:
    """Имя хоста из TEMPORAL_ADDRESS / TEMPORAL_HOST: `host:port` или URL со схемой."""
    t = target.strip()
    if not t:
        return None
    if "://" in t:
        return http_url_hostname(t)
    # host:port (IPv6 в квадратных скобках не разбираем — редко для internal frontend)
    if t.startswith("["):
        return None
    host_part = t.rsplit(":", 1)[0] if ":" in t else t
    return host_part or None


def connect_failure_extra_hint(exc: BaseException, *, hostname: str | None = None) -> str:
    """Доп. текст при типичном сбое резолва имени (getaddrinfo / DNS в Pod)."""
    s = str(exc).lower()
    if (
        "name or service not known" in s
        or "nodename nor servname" in s
        or "failed to resolve" in s
        or ("errno -2" in s and "name" in s)
    ):
        host_part = f" Не удалось резолвить имя: {hostname!r}." if hostname else ""
        return (
            " Похоже на DNS: имя хоста не резолвится в этом контейнере."
            f"{host_part}"
            " В K8s проверьте Service (`kubectl get svc`), namespace Pod, "
            "при межnamespace — FQDN `<service>.<namespace>.svc.cluster.local`."
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
    host_from_url = http_url_hostname(url)
    host_from_base = http_url_hostname(base_url)
    host_line = ""
    if host_from_url or host_from_base:
        if host_from_url == host_from_base:
            host_line = f" Хост из URL (для резолва): {host_from_url!r}."
        else:
            host_line = (
                f" Хост из полного URL: {host_from_url!r}; из BACKEND_API_URL: {host_from_base!r}."
            )
    msg = (
        f"Не удалось подключиться к Django backend ({method} {url}). "
        f"BACKEND_API_URL (база): {base_url!r}.{host_line} "
        "Проверьте: хост резолвится, порт открыт, в K8s — Service в том же namespace, "
        "что Pod воркера (или полный DNS *.svc.cluster.local), нет блокирующей "
        "NetworkPolicy. См. .env.example (BACKEND_API_URL). "
        f"Исходная ошибка: {type(exc).__name__}: {exc}"
    )
    dns_host = host_from_url or host_from_base
    msg += connect_failure_extra_hint(exc, hostname=dns_host)
    raise ApplicationError(msg, non_retryable=True) from exc


def raise_awx_connect_failed(
    *,
    awx_base_url: str,
    method: str,
    url: str,
    exc: Exception,
) -> None:
    """Соединение с AWX не установилось — тот же DNS-хинт, что для backend."""
    host_from_url = http_url_hostname(url)
    host_from_base = http_url_hostname(awx_base_url)
    host_line = ""
    if host_from_url or host_from_base:
        if host_from_url == host_from_base:
            host_line = f" Хост из URL (для резолва): {host_from_url!r}."
        else:
            host_line = f" Хост из полного URL: {host_from_url!r}; база AWX: {host_from_base!r}."
    msg = (
        f"Не удалось подключиться к AWX ({method} {url!r}). "
        f"База URL профиля AWX: {awx_base_url!r}.{host_line} "
        "Задаётся AWX_URL_TEST / AWX_URL_PROD или AWX_URL (см. .env.example). "
        "Проверьте DNS из Pod, доступ до AWX и CA_BUNDLE_PATH. "
        f"Исходная ошибка: {type(exc).__name__}: {exc}"
    )
    dns_host = host_from_url or host_from_base
    msg += connect_failure_extra_hint(exc, hostname=dns_host)
    raise ApplicationError(msg, non_retryable=True) from exc
