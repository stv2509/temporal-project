"""AWX profile resolution for test/prod environments."""

import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class AwxProfileConfig:
    env: str
    url: str
    username: str
    password: str
    # httpx verify value:
    # - True/False
    # - or path to a PEM CA bundle file
    verify: bool | str


def resolve_httpx_verify() -> bool | str:
    """
    Resolve httpx TLS verification setting from CA_BUNDLE_PATH.

    Allowed values for CA_BUNDLE_PATH:
    - path to PEM bundle (string)
    - true
    - false

    When unset/empty: use system default verification (True).
    """
    raw = os.environ.get("CA_BUNDLE_PATH", "").strip()
    if not raw:
        # Use system default trust store.
        return True
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    # Treat any other non-empty value as a path to CA bundle.
    return raw


def get_awx_env() -> str:
    """Resolve AWX env, mapping dev -> test."""
    raw = os.environ.get("AWX_ENV", "test").strip().lower()
    if raw == "dev":
        return "test"
    return raw


def _decrypt_password(plain: str, encrypted: str, key_b64: str) -> str:
    if encrypted and key_b64:
        try:
            fernet = Fernet(key_b64.encode())
            return fernet.decrypt(encrypted.encode()).decode()
        except (InvalidToken, ValueError):
            return plain
    return plain


def get_awx_profile_config() -> AwxProfileConfig:
    """Read AWX profile config for active AWX_ENV."""
    awx_env = get_awx_env()
    verify = resolve_httpx_verify()

    if awx_env == "prod":
        url = os.environ.get("AWX_URL_PROD", "").rstrip("/")
        username = os.environ.get("AWX_USERNAME_PROD", "")
        plain = os.environ.get("AWX_PASSWORD_PROD", "")
        encrypted = os.environ.get("AWX_PASSWORD_ENCRYPTED_PROD", "").strip()
        key_b64 = os.environ.get("ENCRYPTION_KEY_PROD", "").strip()
    else:
        test_url = os.environ.get("AWX_URL_TEST", "").rstrip("/")
        legacy_url = os.environ.get("AWX_URL", "").rstrip("/")
        url = test_url or legacy_url
        username = os.environ.get("AWX_USERNAME_TEST", "") or os.environ.get("AWX_USERNAME", "")
        plain = os.environ.get("AWX_PASSWORD_TEST", "") or os.environ.get("AWX_PASSWORD", "")
        encrypted = (
            os.environ.get("AWX_PASSWORD_ENCRYPTED_TEST", "").strip()
            or os.environ.get("AWX_PASSWORD_ENCRYPTED", "").strip()
        )
        key_b64 = (
            os.environ.get("ENCRYPTION_KEY_TEST", "").strip()
            or os.environ.get("ENCRYPTION_KEY", "").strip()
        )

    password = _decrypt_password(plain, encrypted, key_b64)
    return AwxProfileConfig(
        env=awx_env,
        url=url,
        username=username,
        password=password,
        verify=verify,
    )


def get_awx_auth(config: AwxProfileConfig) -> tuple[str, str] | None:
    """Return basic auth tuple for AWX profile."""
    if config.username and config.password:
        return (config.username, config.password)
    return None
