"""Страницы с формами (Django + Bootstrap): список заявок, форма создания, запуск workflow."""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.infra_requests.adapters import TemporalAdapter
from apps.infra_requests.constants import get_cluster_awx_template_map
from apps.infra_requests.models import Request, RequestStatus, RequestType
from apps.infra_requests.repositories import RequestRepository
from apps.infra_requests.services import RequestService

logger = logging.getLogger(__name__)


def _get_requester(request) -> str:
    return getattr(request.user, "username", "") or ""


def _get_cluster_choices(request_type: str) -> list[str]:
    try:
        template_map = get_cluster_awx_template_map(request_type)
        return list(template_map.keys())
    except ValueError:
        return []


def _get_request_type_choices() -> list[str]:
    routes = getattr(settings, "TEMPORAL_WORKFLOW_ROUTES", {})
    route_keys = set(routes.keys())
    available = [value for value, _ in RequestType.choices if value in route_keys]
    return available or [RequestType.K8S_ACCESS]


def _get_workflow_route(request_type: str) -> tuple[str, str]:
    routes = getattr(settings, "TEMPORAL_WORKFLOW_ROUTES", {})
    route = routes.get(request_type, {})
    workflow_name = str(route.get("workflow_name") or settings.TEMPORAL_WORKFLOW_K8S_ACCESS)
    task_queue = str(route.get("task_queue") or "").strip()
    if not task_queue:
        raise ValueError(f"No task_queue configured for request_type={request_type}")
    return (workflow_name, task_queue)


@login_required
@require_GET
def k8s_access_list(request):
    """Список заявок с кнопкой «Запуск»."""
    requests = RequestRepository().list_by_filters(limit=100)
    return render(
        request,
        "k8s_access/list.html",
        {"requests": requests, "cluster_choices": _get_cluster_choices(RequestType.K8S_ACCESS)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def k8s_access_create(request):
    """Форма создания заявки. POST → сервис → редирект на список или сообщение."""
    if request.method == "GET":
        request_type_choices = _get_request_type_choices()
        selected_request_type = request.GET.get("request_type", RequestType.K8S_ACCESS)
        if selected_request_type not in request_type_choices:
            selected_request_type = RequestType.K8S_ACCESS
        return render(
            request,
            "k8s_access/form.html",
            {
                "request_type_choices": request_type_choices,
                "selected_request_type": selected_request_type,
                "cluster_choices": _get_cluster_choices(selected_request_type),
                "is_pipeline": request.GET.get("pipeline") == "1",
            },
        )

    request_type_choices = _get_request_type_choices()
    request_type = (request.POST.get("request_type") or "").strip() or RequestType.K8S_ACCESS
    if request_type not in request_type_choices:
        request_type = RequestType.K8S_ACCESS
    ticket_id = (request.POST.get("ticket_id") or "").strip()
    cluster = (request.POST.get("cluster") or "").strip()
    dst_host = (request.POST.get("dst_host") or "").strip()
    dst_port_str = (request.POST.get("dst_port") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    service = RequestService()
    normalized, payload, errors = service.prepare_create_from_form(
        ticket_id, request_type, cluster, dst_host, dst_port_str, comment
    )
    if errors:
        return render(
            request,
            "k8s_access/form.html",
            {
                "request_type_choices": request_type_choices,
                "selected_request_type": request_type,
                "cluster_choices": _get_cluster_choices(request_type),
                "errors": errors,
                "form_data": {
                    "request_type": request_type,
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
        request_type=request_type,
        payload=payload,
        normalized=normalized,
        requester=_get_requester(request),
    )

    workflow_name, task_queue = _get_workflow_route(req.type)
    if req.status == RequestStatus.VALIDATED:
        try:
            adapter = TemporalAdapter(task_queue=task_queue)
            adapter.start_workflow(
                workflow_id=ticket_id,
                workflow_name=workflow_name,
                args=[ticket_id],
            )
            service.update_status(ticket_id, RequestStatus.IN_PROGRESS, workflow_id=ticket_id)
            req.refresh_from_db()
        except Exception as e:
            logger.exception("Temporal start_workflow failed: %s", e)
            service.update_status(ticket_id, RequestStatus.VALIDATED)

    url = reverse("infra_requests:k8s_access_list") + f"?created={ticket_id}&status={req.status}"
    return redirect(url)


def _form_data_from_request(req: Request) -> dict:
    """Собрать form_data для шаблона из заявки (normalized + ticket_id)."""
    n = req.normalized or {}
    port = n.get("dst_port")
    return {
        "request_type": req.type,
        "ticket_id": req.ticket_id,
        "cluster": n.get("cluster") or "",
        "dst_host": n.get("dst_host") or "",
        "dst_port": str(port) if port is not None else "",
        "comment": n.get("comment") or "",
    }


@login_required
@require_GET
def k8s_access_view(request, ticket_id: str):
    """Просмотр заявки: те же поля, что при редактировании, без возможности изменить."""
    req = get_object_or_404(Request, ticket_id=ticket_id)
    return render(
        request,
        "k8s_access/form.html",
        {
            "request_type_choices": _get_request_type_choices(),
            "selected_request_type": req.type,
            "cluster_choices": _get_cluster_choices(req.type),
            "form_data": _form_data_from_request(req),
            "is_readonly": True,
            "edit_ticket_id": ticket_id,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def k8s_access_edit(request, ticket_id: str):
    """Редактирование заявки для needs_manual / new.

    Форма с подставленными полями, сохранение через сервис.
    """
    req = get_object_or_404(Request, ticket_id=ticket_id)

    if request.method == "GET":
        return render(
            request,
            "k8s_access/form.html",
            {
                "request_type_choices": _get_request_type_choices(),
                "selected_request_type": req.type,
                "cluster_choices": _get_cluster_choices(req.type),
                "form_data": _form_data_from_request(req),
                "is_edit": True,
                "edit_ticket_id": ticket_id,
            },
        )

    # POST: те же поля, ticket_id не меняем (берём из URL)
    cluster = (request.POST.get("cluster") or "").strip()
    dst_host = (request.POST.get("dst_host") or "").strip()
    dst_port_str = (request.POST.get("dst_port") or "").strip()
    comment = (request.POST.get("comment") or "").strip()

    service = RequestService()
    normalized, payload, errors = service.prepare_create_from_form(
        ticket_id, req.type, cluster, dst_host, dst_port_str, comment
    )
    if errors:
        return render(
            request,
            "k8s_access/form.html",
            {
                "request_type_choices": _get_request_type_choices(),
                "selected_request_type": req.type,
                "cluster_choices": _get_cluster_choices(req.type),
                "errors": errors,
                "form_data": {
                    "request_type": req.type,
                    "ticket_id": ticket_id,
                    "cluster": cluster,
                    "dst_host": dst_host,
                    "dst_port": dst_port_str,
                    "comment": comment,
                },
                "is_edit": True,
                "edit_ticket_id": ticket_id,
            },
            status=400,
        )

    updated = service.create_or_update(
        ticket_id=ticket_id,
        source=req.source,
        request_type=req.type,
        payload=payload,
        normalized=normalized,
        requester=_get_requester(request),
    )

    workflow_name, task_queue = _get_workflow_route(updated.type)
    if updated.status == RequestStatus.VALIDATED:
        try:
            adapter = TemporalAdapter(task_queue=task_queue)
            adapter.start_workflow(
                workflow_id=ticket_id,
                workflow_name=workflow_name,
                args=[ticket_id],
            )
            service.update_status(ticket_id, RequestStatus.IN_PROGRESS, workflow_id=ticket_id)
            updated.refresh_from_db()
        except Exception as e:
            logger.exception("Temporal start_workflow failed: %s", e)
            service.update_status(ticket_id, RequestStatus.VALIDATED)

    url = reverse("infra_requests:k8s_access_list") + f"?edited={ticket_id}&status={updated.status}"
    return redirect(url)


@login_required
@require_POST
def k8s_access_run(request, ticket_id: str):
    """POST: запуск workflow для заявки (кнопка «Запуск»).

    Разрешён повторный запуск для любых статусов.
    """
    service = RequestService()
    req = service.get_by_ticket_id(ticket_id)
    if not req:
        url = reverse("infra_requests:k8s_access_list") + f"?run={ticket_id}&msg=not_found"
        return redirect(url)

    previous_status = req.status
    # validated: атомарный claim;
    # остальные (success, failed, needs_manual, new):
    # просто ставим in_progress и стартуем
    if req.status == RequestStatus.VALIDATED:
        claimed = service.claim_for_run(ticket_id)
        if not claimed:
            url = (
                reverse("infra_requests:k8s_access_list")
                + f"?run={ticket_id}&msg=already_running_or_invalid"
            )
            return redirect(url)
    else:
        service.update_status(ticket_id, RequestStatus.IN_PROGRESS, workflow_id=ticket_id)

    workflow_name, task_queue = _get_workflow_route(req.type)
    try:
        adapter = TemporalAdapter(task_queue=task_queue)
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
    url = reverse("infra_requests:k8s_access_list") + f"?run={ticket_id}&msg={msg}"
    return redirect(url)
