"""Activities for K8s access check: backend API and AWX.

Переменные берутся из os.environ. Файл .env загружается в worker.py (load_dotenv)
до импорта этого модуля, поэтому к моменту чтения переменные из .env уже в os.environ.

Пароль AWX можно задать открыто (AWX_PASSWORD) или зашифрованным Fernet
(AWX_PASSWORD_ENCRYPTED + ENCRYPTION_KEY).
"""

import logging
import os

import httpx
from cryptography.fernet import Fernet, InvalidToken
from temporalio import activity

logger = logging.getLogger(__name__)

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
BACKEND_API_USER = os.environ.get("BACKEND_API_USER", "")
BACKEND_API_PASSWORD = os.environ.get("BACKEND_API_PASSWORD", "")

AWX_URL = os.environ.get("AWX_URL", "").rstrip("/")
AWX_USERNAME = os.environ.get("AWX_USERNAME", "")
AWX_VERIFY_SSL = os.environ.get("AWX_VERIFY_SSL", "true").lower() == "true"


def _decrypt_awx_password() -> str:
    """Читает AWX пароль: открытый или расшифрованный из AWX_PASSWORD_ENCRYPTED."""
    plain = os.environ.get("AWX_PASSWORD", "")
    encrypted = os.environ.get("AWX_PASSWORD_ENCRYPTED", "").strip()
    key_b64 = os.environ.get("ENCRYPTION_KEY", "").strip()
    if encrypted and key_b64:
        try:
            f = Fernet(key_b64.encode())
            return f.decrypt(encrypted.encode()).decode()
        except (InvalidToken, ValueError) as e:
            logger.warning("AWX_PASSWORD_ENCRYPTED decrypt failed: %s", e)
    return plain


AWX_PASSWORD = _decrypt_awx_password()


def _api_auth() -> tuple[str, str] | None:
    if BACKEND_API_USER and BACKEND_API_PASSWORD:
        return (BACKEND_API_USER, BACKEND_API_PASSWORD)
    return None


def _awx_auth() -> tuple[str, str] | None:
    if AWX_USERNAME and AWX_PASSWORD:
        return (AWX_USERNAME, AWX_PASSWORD)
    return None


@activity.defn
async def get_request_data(ticket_id: str) -> dict:
    """GET request data from DRF API."""
    url = f"{BACKEND_API_URL}/api/requests/{ticket_id}/"
    auth = _api_auth()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, auth=auth)
        response.raise_for_status()
    data = response.json()
    logger.info("get_request_data ticket_id=%s", ticket_id)
    return data


@activity.defn
async def launch_awx_job(
    awx_template_id: int,
    host_dst: str,
    port_dst: int,
) -> dict:
    """POST AWX job_templates/{id}/launch/ with extra_vars."""
    if not AWX_URL:
        raise ValueError("AWX_URL not set")
    auth = _awx_auth()
    if not auth:
        raise ValueError("AWX_USERNAME/AWX_PASSWORD not set")

    url = f"{AWX_URL}/api/v2/job_templates/{awx_template_id}/launch/"
    payload = {
        "extra_vars": {
            "host_dst": host_dst,
            "port_dst": port_dst,
        }
    }
    async with httpx.AsyncClient(timeout=120.0, verify=AWX_VERIFY_SSL) as client:
        response = await client.post(url, json=payload, auth=auth)
        response.raise_for_status()
    result = response.json()
    job_id = result.get("id")
    logger.info("launch_awx_job template_id=%s job_id=%s", awx_template_id, job_id)
    return {"job_id": job_id, "status": result.get("status", "pending")}


@activity.defn
async def get_awx_job_status(job_id: int) -> dict:
    """GET AWX job status: GET /api/v2/jobs/{id}/. Returns status and message."""
    if not AWX_URL:
        raise ValueError("AWX_URL not set")
    auth = _awx_auth()
    if not auth:
        raise ValueError("AWX_USERNAME/AWX_PASSWORD not set")
    url = f"{AWX_URL}/api/v2/jobs/{job_id}/"
    async with httpx.AsyncClient(timeout=30.0, verify=AWX_VERIFY_SSL) as client:
        response = await client.get(url, auth=auth)
        response.raise_for_status()
    data = response.json()
    status_val = data.get("status", "unknown")
    message = (
        data.get("result_traceback") or data.get("job_explanation") or ""
    ).strip() or None
    return {"status": status_val, "message": message}


@activity.defn
async def update_request_status(
    ticket_id: str,
    status: str,
    awx: dict | None = None,
) -> None:
    """PATCH request status (and optional awx block into normalized) via DRF API."""
    url = f"{BACKEND_API_URL}/api/requests/{ticket_id}/"
    auth = _api_auth()
    payload: dict = {"status": status}
    if awx is not None:
        payload["awx"] = awx
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(url, json=payload, auth=auth)  # type: ignore[arg-type]
        response.raise_for_status()
    logger.info(
        "update_request_status ticket_id=%s status=%s awx=%s",
        ticket_id,
        status,
        awx is not None,
    )
