"""Адаптеры — интеграция с внешними сервисами (Temporal, AWX)."""

from .temporal_adapter import TemporalAdapter

__all__ = ["TemporalAdapter"]
