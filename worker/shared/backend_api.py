"""Shared backend API configuration helpers."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendApiConfig:
    base_url: str
    user: str
    password: str


def get_backend_api_config() -> BackendApiConfig:
    """Read backend API config from environment."""
    return BackendApiConfig(
        base_url=os.environ.get("BACKEND_API_URL", "http://localhost:8000").rstrip("/"),
        user=os.environ.get("BACKEND_API_USER", ""),
        password=os.environ.get("BACKEND_API_PASSWORD", ""),
    )


def get_backend_api_auth(config: BackendApiConfig) -> tuple[str, str] | None:
    """Return basic auth tuple when both values are set."""
    if config.user and config.password:
        return (config.user, config.password)
    return None


def request_detail_url(config: BackendApiConfig, ticket_id: str) -> str:
    """Build request detail API URL."""
    return f"{config.base_url}/api/requests/{ticket_id}/"
