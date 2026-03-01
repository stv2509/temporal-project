"""ViewSet заявок: list, retrieve, create, action run."""

import logging

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ticket_requests.adapters import TemporalAdapter
from apps.ticket_requests.models import Request, RequestStatus, RequestType
from apps.ticket_requests.serializers import (
    RequestCreateSerializer,
    RequestDetailSerializer,
    RequestListSerializer,
    RequestStatusUpdateSerializer,
)
from apps.ticket_requests.services import RequestService

logger = logging.getLogger(__name__)


class RequestViewSet(viewsets.ModelViewSet):
    """API заявок: list, retrieve, create; action run для запуска workflow."""

    permission_classes = [IsAuthenticated]
    lookup_field = "ticket_id"
    lookup_url_kwarg = "ticket_id"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        return Request.objects.all().order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return RequestListSerializer
        if self.action in ("create",):
            return RequestCreateSerializer
        if self.action in ("update", "partial_update"):
            return RequestStatusUpdateSerializer
        return RequestDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = RequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload = dict(request.data)
        normalized = data["normalized"]
        ticket_id = data["ticket_id"]
        requester = getattr(request.user, "username", "") or ""

        service = RequestService()
        req = service.create_or_update(
            ticket_id=ticket_id,
            source="manual",
            request_type=RequestType.K8S_ACCESS,
            payload=payload,
            normalized=normalized,
            requester=requester,
        )

        workflow_name = getattr(
            settings, "TEMPORAL_WORKFLOW_K8S_ACCESS", "K8sAccessCheckWorkflow"
        )
        if req.status == RequestStatus.VALIDATED:
            try:
                adapter = TemporalAdapter()
                adapter.start_workflow(
                    workflow_id=ticket_id,
                    workflow_name=workflow_name,
                    args=[ticket_id],
                )
                service.update_status(
                    ticket_id, RequestStatus.IN_PROGRESS, workflow_id=ticket_id
                )
                req.refresh_from_db()
            except Exception as e:
                logger.exception("Temporal start_workflow failed: %s", e)
                service.update_status(ticket_id, RequestStatus.VALIDATED)

        return Response(
            RequestDetailSerializer(req).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, ticket_id=None):
        """Атомарно захватить заявку (validated → in_progress) и запустить workflow."""
        service = RequestService()
        claimed = service.claim_for_run(ticket_id)
        if not claimed:
            req = service.get_by_ticket_id(ticket_id)
            if not req:
                return Response(
                    {"status": "not_found", "message": "Заявка не найдена."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {
                    "status": req.status,
                    "workflow_id": req.workflow_id or "",
                    "message": "Заявка уже выполняется или не в статусе validated.",
                },
                status=status.HTTP_200_OK,
            )

        workflow_name = getattr(
            settings, "TEMPORAL_WORKFLOW_K8S_ACCESS", "K8sAccessCheckWorkflow"
        )
        try:
            adapter = TemporalAdapter()
            adapter.start_workflow(
                workflow_id=ticket_id,
                workflow_name=workflow_name,
                args=[ticket_id],
            )
            return Response(
                {
                    "status": "started",
                    "workflow_id": ticket_id,
                    "message": "Workflow запущен.",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("Temporal start_workflow failed: %s", e)
            service.update_status(ticket_id, RequestStatus.VALIDATED)
            return Response(
                {
                    "status": "error",
                    "workflow_id": "",
                    "message": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
