"""URL страниц с формами (HTML)."""

from django.urls import path

from apps.infra_requests import views_pages

app_name = "infra_requests"

urlpatterns = [
    path("", views_pages.request_list, name="request_list"),
    path("create/", views_pages.request_create, name="request_create"),
    path("<str:ticket_id>/run/", views_pages.request_run, name="request_run"),
]
