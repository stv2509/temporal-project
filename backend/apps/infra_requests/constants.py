"""Константы и справочники для заявок."""

from django.conf import settings

from apps.infra_requests.models import RequestType

# Карта template-id:
# AWX_ENV -> request_type -> cluster -> template_id
AWX_TEMPLATE_MAP: dict[str, dict[str, dict[str, int]]] = {
    "test": {
        RequestType.K8S_ACCESS: {
            "DEV": 14,  # K8S_Access_DEV
            "GUEST": 239,  # K8S_Access_GUEST
            "OFFICE": 26,  # K8S_Access_OFFICE
            "OSA": 128,  # K8S_Access_OSA
            "PL": 21,  # K8S_Access_PL
            "TEST1": 16,  # K8S_Access_TEST1
            "TEST3": 19,  # K8S_Access_TEST3
            "TEST4": 17,  # K8S_Access_TEST4
            "TEST5": 18,  # K8S_Access_TEST5
            "TEST6_PG": 20,  # K8S_Access_TEST6/PG
            "TEST7": 22,  # K8S_Access_TEST7
            "TEST8": 241,  # K8S_Access_TEST8
        },
        # RequestType.VM_CREATE: {
        #     "DEV": 901,  # VM_Create_DEV
        #     "TEST1": 902,  # VM_Create_TEST1
        # },
    },
    "prod": {
        RequestType.K8S_ACCESS: {
            "PROD": 1201,  # K8S_Access_PROD
            "SBP": 1202,  # K8S_Access_SBP
        },
        # RequestType.VM_CREATE: {
        #     "PROD": 1901,  # VM_Create_PROD
        #     "SBP": 1902,  # VM_Create_SBP
        # },
    },
}


def get_awx_env() -> str:
    """Вернуть активный AWX env (test/prod), dev по умолчанию маппится на test."""
    raw = str(getattr(settings, "AWX_ENV", "test")).strip().lower()
    if raw == "dev":
        return "test"
    return raw


def get_cluster_awx_template_map(request_type: str) -> dict[str, int]:
    """Вернуть карту cluster -> template_id для request_type в текущем AWX env."""
    awx_env = get_awx_env()
    env_map = AWX_TEMPLATE_MAP.get(awx_env)
    if env_map is None:
        raise ValueError(f"Unsupported AWX_ENV: {awx_env}")
    template_map = env_map.get(request_type)
    if template_map is None:
        raise ValueError(f"No template map for request_type={request_type} in AWX_ENV={awx_env}")
    return template_map


def get_awx_template_id(request_type: str, cluster: str) -> int:
    """Вернуть template_id по request_type и cluster с fail-fast ошибкой."""
    template_map = get_cluster_awx_template_map(request_type)
    try:
        return int(template_map[cluster])
    except KeyError as e:
        awx_env = get_awx_env()
        raise ValueError(
            f"Unknown cluster '{cluster}' for request_type={request_type} in AWX_ENV={awx_env}"
        ) from e
