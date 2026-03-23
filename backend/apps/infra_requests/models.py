"""Модели заявок."""

from django.db import models


class RequestStatus(models.TextChoices):
    """Статус заявки."""

    NEW = "new", "New"
    NEEDS_MANUAL = "needs_manual", "Needs manual"
    VALIDATED = "validated", "Validated"
    IN_PROGRESS = "in_progress", "In progress"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class RequestType(models.TextChoices):
    """Тип заявки."""

    K8S_ACCESS = "k8s_access", "K8s access check"
    # VM_CREATE = "vm_create", "VM create"


class Request(models.Model):
    """Заявка (единый источник правды по ticket_id)."""

    ticket_id = models.CharField(  # type: ignore[var-annotated]
        "Ticket ID", max_length=255, unique=True, db_index=True
    )
    source = models.CharField("Source", max_length=64)  # type: ignore[var-annotated]  # manual, webhook, ticket
    type = models.CharField(  # type: ignore[var-annotated]
        "Type",
        max_length=32,
        choices=RequestType.choices,
        default=RequestType.K8S_ACCESS,
        db_index=True,
    )
    status = models.CharField(  # type: ignore[var-annotated]
        "Status",
        max_length=32,
        choices=RequestStatus.choices,
        default=RequestStatus.NEW,
        db_index=True,
    )
    requester = models.CharField("Requester", max_length=255, blank=True)  # type: ignore[var-annotated]
    payload = models.JSONField("Payload (raw)", default=dict, blank=True)
    normalized = models.JSONField("Normalized fields", default=dict, blank=True)
    workflow_id = models.CharField("Temporal workflow ID", max_length=255, blank=True)  # type: ignore[var-annotated]
    created_at = models.DateTimeField("Created", auto_now_add=True)  # type: ignore[var-annotated]
    updated_at = models.DateTimeField("Updated", auto_now=True)  # type: ignore[var-annotated]

    class Meta:
        db_table = "requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["type"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Request"
        verbose_name_plural = "Requests"

    def __str__(self) -> str:
        return f"{self.ticket_id} ({self.status})"
