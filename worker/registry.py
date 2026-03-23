"""Registry of worker domains, workflows and activities."""

import os
from dataclasses import dataclass
from typing import Any

from worker.domains.k8s_access.activities import (
    get_awx_job_status,
    get_request_data,
    launch_awx_job,
    update_request_status,
)
from worker.domains.k8s_access.workflows import K8sAccessCheckWorkflow


@dataclass(frozen=True)
class DomainRegistration:
    domain_key: str
    queue_env_var: str
    default_queue: str
    workflows: list[type[Any]]
    activities: list[Any]

    def resolve_task_queue(self) -> str:
        queue = os.environ.get(self.queue_env_var, "").strip()
        if queue:
            return queue
        return self.default_queue


DOMAIN_REGISTRY: dict[str, DomainRegistration] = {
    "k8s_access": DomainRegistration(
        domain_key="k8s_access",
        queue_env_var="TEMPORAL_TASK_QUEUE_K8S_ACCESS",
        default_queue="awx-task-queue",
        workflows=[K8sAccessCheckWorkflow],
        activities=[
            get_request_data,
            launch_awx_job,
            get_awx_job_status,
            update_request_status,
        ],
    ),
    # "vm_create": DomainRegistration(
    #     domain_key="vm_create",
    #     queue_env_var="TEMPORAL_TASK_QUEUE_VM_CREATE",
    #     default_queue="vm-create-task-queue",
    #     workflows=[],
    #     activities=[],
    # ),
}


def get_domain_registration(domain_key: str) -> DomainRegistration:
    registration = DOMAIN_REGISTRY.get(domain_key)
    if registration is None:
        raise ValueError(f"Unsupported worker domain: {domain_key}")
    return registration
