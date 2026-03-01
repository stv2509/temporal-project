"""Сервис заявок: создание, валидация, захват для запуска workflow."""

from apps.ticket_requests.constants import CLUSTER_AWX_TEMPLATE
from apps.ticket_requests.models import Request, RequestStatus, RequestType
from apps.ticket_requests.repositories import RequestRepository


class RequestService:
    """Оркестрация операций с заявками."""

    def __init__(self, repository: RequestRepository | None = None) -> None:
        self.repository = repository or RequestRepository()

    def create_or_update(
        self,
        ticket_id: str,
        source: str,
        request_type: str,
        payload: dict,
        normalized: dict,
        *,
        requester: str = "",
    ) -> Request:
        """Создать или обновить заявку (UPSERT по ticket_id)."""
        status = (
            RequestStatus.VALIDATED
            if self.validate_normalized(request_type, normalized)
            else RequestStatus.NEEDS_MANUAL
        )
        return self.repository.upsert(
            ticket_id,
            source=source,
            type=request_type,
            status=status,
            requester=requester,
            payload=payload,
            normalized=normalized,
        )

    def validate_normalized(self, request_type: str, normalized: dict) -> bool:
        """Проверка обязательных полей для типа заявки. Для k8s_access: cluster, dst_host, dst_port."""
        if request_type == RequestType.K8S_ACCESS:
            cluster = normalized.get("cluster")
            dst_host = normalized.get("dst_host")
            dst_port = normalized.get("dst_port")
            if not cluster or not dst_host or dst_port is None:
                return False
            if cluster not in CLUSTER_AWX_TEMPLATE:
                return False
            try:
                port = int(dst_port)
            except (TypeError, ValueError):
                return False
            if not (1 <= port <= 65535):
                return False
            return True
        return False

    def claim_for_run(self, ticket_id: str, workflow_id: str = "") -> Request | None:
        """Атомарно перевести заявку из validated в in_progress. Возвращает заявку или None."""
        return self.repository.claim_for_run(ticket_id, workflow_id or ticket_id)

    def update_status(
        self, ticket_id: str, status: str, workflow_id: str = ""
    ) -> int:
        """Обновить статус заявки. Возвращает число обновлённых строк."""
        return self.repository.update_status(ticket_id, status, workflow_id)

    def get_by_ticket_id(self, ticket_id: str) -> Request | None:
        """Получить заявку по ticket_id."""
        return self.repository.get_by_ticket_id(ticket_id)
