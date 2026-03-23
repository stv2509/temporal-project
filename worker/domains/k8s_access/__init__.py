"""Домен k8s_access.

Важно: не импортируем activities на уровне пакета, чтобы workflow sandbox
не тащил недетерминированные зависимости (например, httpx) при валидации.
"""

from worker.domains.k8s_access.workflows import K8sAccessCheckWorkflow

__all__ = ["K8sAccessCheckWorkflow"]
