"""Сервис заявок: создание, валидация, захват для запуска workflow."""

from apps.infra_requests.constants import CLUSTER_AWX_TEMPLATE
from apps.infra_requests.models import Request, RequestStatus, RequestType
from apps.infra_requests.repositories import RequestRepository


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
        match request_type:
            case RequestType.K8S_ACCESS:
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
                return 1 <= port <= 65535
            case _:
                return False

    def claim_for_run(self, ticket_id: str, workflow_id: str = "") -> Request | None:
        """Атомарно перевести заявку из validated в in_progress. Возвращает заявку или None."""
        return self.repository.claim_for_run(ticket_id, workflow_id or ticket_id)

    def update_status(self, ticket_id: str, status: str, workflow_id: str = "") -> int:
        """Обновить статус заявки. Возвращает число обновлённых строк."""
        return self.repository.update_status(ticket_id, status, workflow_id)

    def get_by_ticket_id(self, ticket_id: str) -> Request | None:
        """Получить заявку по ticket_id."""
        return self.repository.get_by_ticket_id(ticket_id)

    def prepare_create_from_form(
        self,
        ticket_id: str,
        cluster: str,
        dst_host: str,
        dst_port_str: str,
        comment: str = "",
    ) -> tuple[dict, dict, list[str]]:
        """Валидация полей формы и подготовка normalized/payload. Возвращает (normalized, payload, errors)."""
        errors: list[str] = []
        if not ticket_id:
            errors.append("Номер заявки обязателен.")
        if not cluster:
            errors.append("Выберите кластер.")
        elif cluster not in CLUSTER_AWX_TEMPLATE:
            errors.append("Недопустимый кластер.")
        if not dst_host:
            errors.append("dst_host обязателен.")
        try:
            dst_port = int(dst_port_str) if dst_port_str else None
        except ValueError:
            dst_port = None
        if dst_port is None or not (1 <= dst_port <= 65535):
            errors.append("dst_port: число от 1 до 65535.")

        normalized: dict = {}
        payload: dict = {
            "ticket_id": ticket_id,
            "cluster": cluster,
            "dst_host": dst_host,
            "dst_port": dst_port,
            "comment": comment,
        }
        if not errors and cluster in CLUSTER_AWX_TEMPLATE and dst_port is not None:
            normalized = {
                "cluster": cluster,
                "dst_host": dst_host,
                "dst_port": dst_port,
                "awx_template_id": CLUSTER_AWX_TEMPLATE[cluster],
            }
            if comment:
                normalized["comment"] = comment
        return (normalized, payload, errors)
