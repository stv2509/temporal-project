"""Сериализаторы DRF для заявок."""

from rest_framework import serializers  # type: ignore[import-untyped]

from apps.infra_requests.constants import CLUSTER_AWX_TEMPLATE
from apps.infra_requests.models import Request


class RequestCreateSerializer(serializers.Serializer):
    """Создание/обновление заявки (форма, API)."""

    ticket_id = serializers.CharField(max_length=255, trim_whitespace=True)
    cluster = serializers.ChoiceField(choices=list(CLUSTER_AWX_TEMPLATE.keys()))
    dst_host = serializers.CharField(max_length=255, trim_whitespace=True)
    dst_port = serializers.IntegerField(min_value=1, max_value=65535)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2048)

    def validate_ticket_id(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Номер заявки обязателен.")
        return value.strip()

    def validate_dst_host(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("dst_host обязателен.")
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        cluster = attrs["cluster"]
        attrs["normalized"] = {
            "cluster": cluster,
            "dst_host": attrs["dst_host"],
            "dst_port": attrs["dst_port"],
            "awx_template_id": CLUSTER_AWX_TEMPLATE[cluster],
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
        fields = ["status"]


class RequestRunResponseSerializer(serializers.Serializer):
    """Ответ на POST .../run."""

    status = serializers.CharField()
    workflow_id = serializers.CharField(allow_blank=True)
    message = serializers.CharField(required=False)
