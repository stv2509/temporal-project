"""URL маршруты API заявок."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter  # type: ignore[import-untyped]

from apps.infra_requests.views import RequestViewSet

router = DefaultRouter()
router.register(r"requests", RequestViewSet, basename="request")

urlpatterns = [
    path("", include(router.urls)),
]
