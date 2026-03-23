"""Репозиторий заявок: единая точка доступа к данным."""

from django.db import transaction

from apps.infra_requests.models import Request, RequestStatus, RequestType


class RequestRepository:
    """Доступ к таблице requests (без бизнес-логики)."""

    def get_by_ticket_id(self, ticket_id: str) -> Request | None:
        """Получить заявку по ticket_id."""
        return Request.objects.filter(ticket_id=ticket_id).first()

    def upsert(
        self,
        ticket_id: str,
        *,
        source: str,
        type: str = RequestType.K8S_ACCESS,
        status: str = RequestStatus.NEW,
        requester: str = "",
        payload: dict,
        normalized: dict,
        workflow_id: str = "",
    ) -> Request:
        """Вставить или обновить заявку по ticket_id (ON CONFLICT по сути)."""
        obj, _ = Request.objects.update_or_create(
            ticket_id=ticket_id,
            defaults={
                "source": source,
                "type": type,
                "status": status,
                "requester": requester or "",
                "payload": payload,
                "normalized": normalized,
                "workflow_id": workflow_id or "",
            },
        )
        return obj

    def list_by_status(self, status: str, limit: int = 100) -> list[Request]:
        """Список заявок по статусу."""
        return list(Request.objects.filter(status=status).order_by("-created_at")[:limit])

    def list_by_filters(
        self,
        status: str | None = None,
        type: str | None = None,
        limit: int = 100,
    ) -> list[Request]:
        """Список заявок по опциональным фильтрам."""
        qs = Request.objects.all().order_by("-created_at")
        if status is not None:
            qs = qs.filter(status=status)
        if type is not None:
            qs = qs.filter(type=type)
        return list(qs[:limit])

    def update_status(
        self,
        ticket_id: str,
        status: str,
        workflow_id: str = "",
    ) -> int:
        """Обновить статус заявки по ticket_id. Возвращает число обновлённых строк."""
        return Request.objects.filter(ticket_id=ticket_id).update(
            status=status,
            workflow_id=workflow_id or "",
        )

    @transaction.atomic
    def claim_for_run(self, ticket_id: str, workflow_id: str) -> Request | None:
        """Атомарно «захватить» заявку: validated → in_progress. Возвращает заявку или None."""
        # select_for_update блокирует строку до конца транзакции
        request = (
            Request.objects.select_for_update()
            .filter(ticket_id=ticket_id, status=RequestStatus.VALIDATED)
            .first()
        )
        if request is None:
            return None
        request.status = RequestStatus.IN_PROGRESS
        request.workflow_id = workflow_id or ticket_id
        request.save(update_fields=["status", "workflow_id", "updated_at"])
        return request
