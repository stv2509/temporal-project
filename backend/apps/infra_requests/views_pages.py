"""Страницы с формами (Django + Bootstrap): список заявок, форма создания, Run."""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from apps.infra_requests.adapters import TemporalAdapter
from apps.infra_requests.constants import CLUSTER_AWX_TEMPLATE
from apps.infra_requests.models import RequestStatus, RequestType
from apps.infra_requests.repositories import RequestRepository
from apps.infra_requests.services import RequestService

logger = logging.getLogger(__name__)


def _get_requester(request) -> str:
    return getattr(request.user, "username", "") or ""


@login_required
@require_GET
def request_list(request):
    """Список заявок с кнопкой Run."""
    requests = RequestRepository().list_by_filters(limit=100)
    return render(
        request,
        "ticket_requests/request_list.html",
        {"requests": requests, "cluster_choices": list(CLUSTER_AWX_TEMPLATE.keys())},
    )


@login_required
@require_http_methods(["GET", "POST"])
def request_create(request):
    """Форма создания заявки. POST → сервис → редирект на список или сообщение."""
    if request.method == "GET":
        return render(
            request,
            "ticket_requests/request_form.html",
            {
                "cluster_choices": list(CLUSTER_AWX_TEMPLATE.keys()),
                "is_pipeline": request.GET.get("pipeline") == "1",
            },
        )

    ticket_id = (request.POST.get("ticket_id") or "").strip()
    cluster = (request.POST.get("cluster") or "").strip()
    dst_host = (request.POST.get("dst_host") or "").strip()
    dst_port_str = (request.POST.get("dst_port") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    service = RequestService()
    normalized, payload, errors = service.prepare_create_from_form(
        ticket_id, cluster, dst_host, dst_port_str, comment
    )
    if errors:
        return render(
            request,
            "ticket_requests/request_form.html",
            {
                "cluster_choices": list(CLUSTER_AWX_TEMPLATE.keys()),
                "errors": errors,
                "form_data": {
                    "ticket_id": ticket_id,
                    "cluster": cluster,
                    "dst_host": dst_host,
                    "dst_port": dst_port_str,
                    "comment": comment,
                },
                "is_pipeline": False,
            },
            status=400,
        )

    req = service.create_or_update(
        ticket_id=ticket_id,
        source="manual",
        request_type=RequestType.K8S_ACCESS,
        payload=payload,
        normalized=normalized,
        requester=_get_requester(request),
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

    url = (
        reverse("infra_requests:request_list")
        + f"?created={ticket_id}&status={req.status}"
    )
    return redirect(url)


@login_required
@require_POST
def request_run(request, ticket_id: str):
    """POST: запуск workflow для заявки (кнопка Run). Разрешён повторный запуск для любых статусов."""
    service = RequestService()
    req = service.get_by_ticket_id(ticket_id)
    if not req:
        url = reverse("infra_requests:request_list") + f"?run={ticket_id}&msg=not_found"
        return redirect(url)

    previous_status = req.status
    # validated: атомарный claim; остальные (success, failed, needs_manual, new): просто ставим in_progress и стартуем
    if req.status == RequestStatus.VALIDATED:
        claimed = service.claim_for_run(ticket_id)
        if not claimed:
            url = (
                reverse("infra_requests:request_list")
                + f"?run={ticket_id}&msg=already_running_or_invalid"
            )
            return redirect(url)
    else:
        service.update_status(
            ticket_id, RequestStatus.IN_PROGRESS, workflow_id=ticket_id
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
        msg = "started"
    except Exception as e:
        logger.exception("Temporal start_workflow failed: %s", e)
        service.update_status(ticket_id, previous_status)
        msg = "error"
    url = reverse("infra_requests:request_list") + f"?run={ticket_id}&msg={msg}"
    return redirect(url)
