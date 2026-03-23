"""Activities домена k8s_access: DRF API и AWX.

Переменные из `os.environ`; `.env` подгружается в `worker/runner.py` до импорта модулей.
"""

import logging

import httpx
from temporalio import activity

from worker.shared.awx_profiles import get_awx_auth, get_awx_profile_config
from worker.shared.backend_api import (
    get_backend_api_auth,
    get_backend_api_config,
    request_detail_url,
)

logger = logging.getLogger(__name__)

BACKEND_API = get_backend_api_config()
AWX_PROFILE = get_awx_profile_config()


def _api_auth() -> tuple[str, str] | None:
    return get_backend_api_auth(BACKEND_API)


def _awx_auth() -> tuple[str, str] | None:
    return get_awx_auth(AWX_PROFILE)


@activity.defn
async def get_request_data(ticket_id: str) -> dict:
    """GET request data from DRF API."""
    url = request_detail_url(BACKEND_API, ticket_id)
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
    if not AWX_PROFILE.url:
        raise ValueError("AWX_URL not set")
    auth = _awx_auth()
    if not auth:
        raise ValueError("AWX_USERNAME/AWX_PASSWORD not set")

    url = f"{AWX_PROFILE.url}/api/v2/job_templates/{awx_template_id}/launch/"
    payload = {
        "extra_vars": {
            "host_dst": host_dst,
            "port_dst": port_dst,
        }
    }
    async with httpx.AsyncClient(timeout=120.0, verify=AWX_PROFILE.verify_ssl) as client:
        response = await client.post(url, json=payload, auth=auth)
        response.raise_for_status()
    result = response.json()
    job_id = result.get("id")
    logger.info("launch_awx_job template_id=%s job_id=%s", awx_template_id, job_id)
    return {"job_id": job_id, "status": result.get("status", "pending")}


@activity.defn
async def get_awx_job_status(job_id: int) -> dict:
    """GET AWX job status: GET /api/v2/jobs/{id}/. Returns status and message."""
    if not AWX_PROFILE.url:
        raise ValueError("AWX_URL not set")
    auth = _awx_auth()
    if not auth:
        raise ValueError("AWX_USERNAME/AWX_PASSWORD not set")
    url = f"{AWX_PROFILE.url}/api/v2/jobs/{job_id}/"
    async with httpx.AsyncClient(timeout=30.0, verify=AWX_PROFILE.verify_ssl) as client:
        response = await client.get(url, auth=auth)
        response.raise_for_status()
    data = response.json()
    status_val = data.get("status", "unknown")
    message = (data.get("result_traceback") or data.get("job_explanation") or "").strip() or None
    return {"status": status_val, "message": message}


@activity.defn
async def update_request_status(
    ticket_id: str,
    status: str,
    awx: dict | None = None,
) -> None:
    """PATCH request status (and optional awx block into normalized) via DRF API."""
    url = request_detail_url(BACKEND_API, ticket_id)
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
