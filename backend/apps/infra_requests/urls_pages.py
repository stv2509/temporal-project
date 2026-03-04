"""URL страниц с формами (HTML)."""

from django.urls import path

from apps.infra_requests import views_pages

app_name = "infra_requests"

urlpatterns = [
    path("", views_pages.k8s_access_list, name="k8s_access_list"),
    path("create/", views_pages.k8s_access_create, name="k8s_access_create"),
    path("<str:ticket_id>/edit/", views_pages.k8s_access_edit, name="k8s_access_edit"),
    path("<str:ticket_id>/run/", views_pages.k8s_access_run, name="k8s_access_run"),
]
