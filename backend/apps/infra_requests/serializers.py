"""Сериализаторы DRF для заявок."""

from rest_framework import serializers  # type: ignore[import-untyped]

from apps.infra_requests.constants import get_awx_template_id, get_cluster_awx_template_map
from apps.infra_requests.models import Request, RequestType


class RequestCreateSerializer(serializers.Serializer):
    """Создание/обновление заявки (форма, API)."""

    request_type = serializers.ChoiceField(
        choices=RequestType.choices,
        default=RequestType.K8S_ACCESS,
    )
    ticket_id = serializers.CharField(max_length=255, trim_whitespace=True)
    cluster = serializers.ChoiceField(choices=[])
    dst_host = serializers.CharField(max_length=255, trim_whitespace=True)
    dst_port = serializers.IntegerField(min_value=1, max_value=65535)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2048)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request_type = str(RequestType.K8S_ACCESS)
        initial = getattr(self, "initial_data", None)
        if isinstance(initial, dict):
            request_type = str(initial.get("request_type") or RequestType.K8S_ACCESS)
        try:
            cluster_map = get_cluster_awx_template_map(request_type)
        except ValueError:
            cluster_map = {}
        self.fields["cluster"].choices = list(cluster_map.keys())

    def validate_ticket_id(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Номер заявки обязателен.")
        return value.strip()

    def validate_dst_host(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("dst_host обязателен.")
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        request_type = str(attrs.get("request_type") or RequestType.K8S_ACCESS)
        cluster = attrs["cluster"]
        try:
            awx_template_id = get_awx_template_id(request_type, cluster)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e
        attrs["normalized"] = {
            "cluster": cluster,
            "dst_host": attrs["dst_host"],
            "dst_port": attrs["dst_port"],
            "awx_template_id": awx_template_id,
        }
        if attrs.get("comment"):
            attrs["normalized"]["comment"] = attrs["comment"]
        return attrs


class RequestListSerializer(serializers.ModelSerializer):
    """Список заявок — минимум полей."""

    class Meta:
        model = Request
        fields = [
            "id",
            "ticket_id",
            "source",
            "type",
            "status",
            "workflow_id",
            "created_at",
        ]


class RequestDetailSerializer(serializers.ModelSerializer):
    """Детали заявки + read_only служебные поля."""

    class Meta:
        model = Request
        fields = [
            "id",
            "ticket_id",
            "source",
            "type",
            "status",
            "requester",
            "payload",
            "normalized",
            "workflow_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ticket_id",
            "source",
            "type",
            "status",
            "payload",
            "normalized",
            "workflow_id",
            "created_at",
            "updated_at",
        ]


class RequestStatusUpdateSerializer(serializers.ModelSerializer):
    """Статус и опционально awx (merge в normalized) — для PATCH из worker."""

    awx = serializers.DictField(required=False, allow_null=True)

    class Meta:
        model = Request
        fields = ["status", "awx"]


class RequestRunResponseSerializer(serializers.Serializer):
    """Ответ на POST .../run."""

    status = serializers.CharField()
    workflow_id = serializers.CharField(allow_blank=True)
    message = serializers.CharField(required=False)
