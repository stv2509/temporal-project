# Отчёт: соответствие проекта правилам .cursor/rules

Дата проверки: 2026-03-04.

---

## 1. django-architecture-patterns (Service / Repository / Adapter)

| Правило | Статус | Комментарий |
|--------|--------|-------------|
| **Thin Views** | ✅ | ViewSet и views_pages вызывают `RequestService` и `RequestRepository`; валидация формы вынесена в `RequestService.prepare_create_from_form`. |
| **Service Layer** | ✅ | `RequestService` — оркестрация create_or_update, validate_normalized, claim_for_run, update_status. |
| **Repository** | ✅ | `RequestRepository` — get_by_ticket_id, upsert, list_by_status, list_by_filters, update_status, claim_for_run. Список заявок в `request_list` идёт через `RequestRepository().list_by_filters(limit=100)`. |
| **Adapter** | ✅ | `TemporalAdapter` — обёртка над Temporal Client (start_workflow), обработка `WorkflowAlreadyStartedError`. |

---

## 2. django-data-modeling (Enum, typing, match/case)

| Правило | Статус | Комментарий |
|--------|--------|-------------|
| **Enum для статусов/типов** | ✅ | `RequestStatus` и `RequestType` — `models.TextChoices`; сравнения по константам. |
| **Typing для публичного API** | ✅ | Сервис, репозиторий, адаптер и activities имеют аннотации аргументов и возврата (`str \| None`, `list[...]`, `dict[...]`). |
| **match/case** | ✅ | В `RequestService.validate_normalized` используется `match request_type:` с `case RequestType.K8S_ACCESS` и `case _`. |
| **Pydantic для внешних API** | ⚪ | Не требуется для текущего MVP (DRF-сериализаторы и формы). При появлении webhook/внешних JSON — добавить по правилу. |

---

## 3. django-drf-best-practices

| Правило | Статус | Комментарий |
|--------|--------|-------------|
| **Разные сериализаторы list/create/retrieve** | ✅ | `RequestListSerializer`, `RequestDetailSerializer`, `RequestCreateSerializer`, `RequestStatusUpdateSerializer`; выбор в `get_serializer_class()` по action. |
| **ViewSet + Router** | ✅ | `RequestViewSet`, `DefaultRouter`, регистрация `api/requests`. |
| **N+1** | ✅ | Нет связей ForeignKey в списке; при появлении — добавить `select_related`/`prefetch_related` в `get_queryset()`. |
| **Permissions** | ✅ | `permission_classes = [IsAuthenticated]` заданы явно. |
| **Пагинация** | ✅ | В `settings`: `DEFAULT_PAGINATION_CLASS`, `PAGE_SIZE`: 50. |
| **Единый формат ошибок** | ⚪ | Стандартный exception handler DRF; при необходимости — `drf-standardized-errors` (правило 6). |
| **Тонкий ViewSet** | ✅ | `create` и `perform_update` делегируют логику сервису и сериализатору. |

---

## 4. python-modern-syntax / typing-cheatsheet

| Правило | Статус | Комментарий |
|--------|--------|-------------|
| **Union с `\|`** | ✅ | Везде `str \| None`, `dict \| None` и т.п.; нет `Optional`/`Union` из typing. |
| **Generic list/dict/tuple** | ✅ | Используются `list[...]`, `dict[...]`, `tuple[...]`; нет `List`/`Dict`/`Tuple` из typing. |
| **Импорты из typing** | ✅ | Только `Any` в адаптере; остальное — встроенные типы и `\|`. |
| **TypeVar/TypeIs/ReadOnly** | ⚪ | По мере появления сложных контрактов — применять по правилам. |

---

## 5. python-ruff-practices

| Правило | Статус | Комментарий |
|--------|--------|-------------|
| **ruff format / ruff check** | ✅ | Проект проходит `ruff format .` и `ruff check . --fix`. |
| **mypy** | ✅ | `mypy --check-untyped-defs backend worker` — без ошибок (с точечными type: ignore где нужно). |
| **Современный синтаксис** | ✅ | Нет устаревшего синтаксиса из правил UP006/UP007/UP035. |

---

## 6. Внесённые исправления (в рамках проверки)

1. **django-data-modeling**: в `RequestService.validate_normalized` цепочка `if request_type == ...` заменена на `match request_type:` с `case RequestType.K8S_ACCESS` и `case _`.
2. **django-architecture-patterns**:
   - Список заявок в `request_list` переведён на `RequestRepository().list_by_filters(limit=100)` вместо прямого `Request.objects.all()...`.
   - Валидация и подготовка данных формы вынесены в `RequestService.prepare_create_from_form(...)`; `request_create` вызывает сервис и рендер, без дублирования логики валидации.

---

## 7. Рекомендации (опционально)

- **Единый формат ошибок API**: при подключении фронта или мобильного клиента рассмотреть `drf-standardized-errors` и задать `EXCEPTION_HANDLER` в настройках DRF.
- **Шаблоны**: папка `templates/ticket_requests/` переименована в `infra_requests` не была; при желании единообразия с именем приложения можно переименовать и обновить пути в `render(..., "infra_requests/request_list.html")` и т.п.
- **Pydantic**: при появлении приёма webhook или сложных JSON из тикетницы — ввести DTO и валидацию по правилу C (django-data-modeling).
