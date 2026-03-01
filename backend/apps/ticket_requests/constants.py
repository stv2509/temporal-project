"""Константы и справочники для заявок."""

# Кластер K8s → ID job template в AWX (пример: https://awx.example.com)
CLUSTER_AWX_TEMPLATE: dict[str, int] = {
    "DEV": 14,       # K8S_Access_DEV
    "GUEST": 239,    # K8S_Access_GUEST
    "OFFICE": 26,     # K8S_Access_OFFICE
    "OSA": 128,       # K8S_Access_OSA
    "PL": 21,         # K8S_Access_PL
    "TEST1": 16,      # K8S_Access_TEST1
    "TEST3": 19,      # K8S_Access_TEST3
    "TEST4": 17,      # K8S_Access_TEST4
    "TEST5": 18,      # K8S_Access_TEST5
    "TEST6_PG": 20,   # K8S_Access_TEST6/PG
    "TEST7": 22,      # K8S_Access_TEST7
    "TEST8": 241,     # K8S_Access_TEST8
}
