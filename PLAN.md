# План работ: заявка на проверку сетевого доступа (K8s) + Temporal

Опирается на правила из `.cursor/rules/` (Django, DRF, typing 3.13+, Ruff) и на обсуждённую архитектуру (webhook → БД → Push-старт workflow, ручной запуск через форму).

**Чеклист задач для отметки выполнения:** [TASKS_AWX.md](TASKS_AWX.md).

---

## 1. Цель и границы MVP

- **Ручной запуск**: форма (Django + Bootstrap) → сохранение заявки в БД → запуск Temporal workflow (Push: по кнопке Run или сразу после валидации).
- **Тип заявки**: проверка сетевого доступа от кластеров K8s (поля: номер заявки, кластер, `dst_host`, `dst_port`).
- **БД**: SQLite на текущем этапе; схема заложена под последующий перенос на PostgreSQL.
- **Temporal**: workflow и activities под AWX создаются в папке `worker/`; worker и starter — отдельные процессы в папках `worker/` и `starter/`.
- **Webhook из тикет-системы**: вне MVP (оставить на следующий этап).

---

## 2. Соответствие правилам проекта

| Правило | Применение |
|--------|------------|
| **django-architecture-patterns** | Thin views; слой Service для создания/обновления заявки и старта workflow; Repository для доступа к таблице заявок; Adapter для вызова Temporal Client (и позже AWX). |
| **django-data-modeling** | Enum для статусов заявки и кодов кластеров; типизация (Python 3.13: `list`, `dict`, `X \| None`); при необходимости Pydantic для входящих webhook; `match`/`case` по статусам где уместно. |
| **django-drf-best-practices** | Отдельные сериализаторы List/Detail/Create; ViewSet или Generic APIView; явные `permission_classes`; пагинация для list; тонкий ViewSet → вызов Service. |
| **typing-cheatsheet / python-modern-syntax** | Современная типизация (без `Optional`/`List`/`Dict` из typing), `TypeVar` с default при необходимости. |
| **python-ruff-practices** | `ruff check . --fix`, `ruff format .`, при необходимости `mypy`; типы у публичных функций. |

---

## 3. Структура репозитория (предлагаемая)

```
temporal-project/
├── .cursor/
├── backend/                    # Django-проект (API + форма)
│   ├── manage.py
│   ├── config/                  # или <project_name>/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── ...
│   ├── apps/
│   │   └── requests/            # приложение заявок
│   │       ├── models.py        # Request (ticket_id, source, type, status, payload, normalized, ...)
│   │       ├── repositories/
│   │       ├── services/
│   │       ├── serializers.py
│   │       ├── views.py / viewsets.py
│   │       ├── urls.py
│   │       └── ...
│   └── requirements.txt         # Django, djangorestframework, psycopg2/sqlite, temporalio (клиент)
├── worker/                      # Temporal worker (отдельный процесс)
│   ├── worker.py
│   ├── workflows.py             # workflow для K8s access + AWX
│   ├── activities.py           # get_request_data, launch_awx_job, update_request_status
│   └── requirements.txt
├── starter/                     # Клиент для ручного/тестового запуска workflow
│   ├── starter.py
├── ARCHITECTURE.md
├── PLAN.md
├── README.md
└── requirements.txt             # общий минимум или ссылка на backend/worker
```

---

## 4. Этапы работ

### Этап 1 — Инфраструктура и модель данных

1. **Инициализация Django-проекта**
   - Создать проект (например, `backend/`), настроить `config/settings.py` (SQLite по умолчанию, DRF, CORS при необходимости).
   - Добавить приложение `requests` для заявок.

2. **Модель заявки и миграции**
   - Таблица `requests`: `id`, `ticket_id` (unique), `source`, `type`, `status`, `requester`, `payload` (JSONField), `normalized` (JSONField), `workflow_id`, `created_at`, `updated_at`.
   - Enum для `status`: new, needs_manual, validated, in_progress, success, failed.
   - Enum или справочник для `type` (пока один тип: k8s_access).
   - Индексы: `ticket_id` (unique), `status`, при необходимости `type`, `created_at`.
   - Создать миграции, применить на SQLite.

3. **Справочник кластер → AWX template id**
   - Для MVP: константа/Enum в коде (словарь `CLUSTER_AWX_TEMPLATE`) в `requests` app.
   - Значения: DEV→14, GUEST→239, OFFICE→26, OSA→128, PL→21, TEST1→16, TEST3→19, TEST4→17, TEST5→18, TEST6_PG→20, TEST7→22, TEST8→241.

---

### Этап 2 — Слой данных и сервисы (Repository, Service)

4. **Repository**
   - Методы: `get_by_ticket_id`, `upsert` (INSERT … ON CONFLICT DO UPDATE по `ticket_id`), `list_by_status`, `list_by_filters` (status, type). Всё через ORM, без бизнес-логики.

5. **Сервис заявок (RequestService)**
   - `create_or_update(ticket_id, source, type, payload, normalized)` → вызывает repository.upsert, возвращает модель.
   - `validate_normalized(normalized)` → проверка обязательных полей для типа `k8s_access` (cluster, dst_host, dst_port).
   - `claim_for_run(ticket_id)` → атомарный UPDATE … WHERE status='validated' RETURNING (или эквивалент ORM), возвращает запись или None.
   - Типизация (Python 3.13) для всех публичных методов.

6. **Adapter для Temporal**
   - Класс (например, `TemporalAdapter`): метод `start_workflow(workflow_id, workflow_name, args)`.
   - Внутри — подключение к Temporal (как в `starter.py`), вызов `client.start_workflow(...)`.
   - Обработка `WorkflowAlreadyStarted` (считать успехом), остальные исключения — пробрасывать или оборачивать в доменный exception.
   - Секреты/хост Temporal — из настроек Django (env/settings).

---

### Этап 3 — DRF API и сериализаторы

7. **Сериализаторы**
   - **RequestCreateSerializer**: поля `ticket_id`, `cluster`, `dst_host`, `dst_port` (и опционально `comment`). Валидация: обязательность, диапазон порта 1–65535, cluster из списка. В `validate` формировать `normalized` (cluster, dst_host, dst_port, awx_template_id).
   - **RequestListSerializer**: id, ticket_id, source, type, status, workflow_id, created_at (минимум для списка).
   - **RequestDetailSerializer**: полный набор полей + read_only для служебных.
   - По правилам DRF: разный сериализатор для list/create/retrieve.

8. **ViewSet / API**
   - ViewSet для заявок: `list`, `retrieve`, `create`; при `create` — вызов `RequestService.create_or_update` + при успешной валидации вызов `TemporalAdapter.start_workflow` (workflow_id=ticket_id), обновление status в `in_progress`. Если валидация не прошла — status `needs_manual`, вернуть ссылку на форму/редактирование.
   - Отдельный endpoint: `POST /api/requests/{ticket_id}/run` — атомарный claim через сервис + старт workflow (кнопка Run). Явные `permission_classes` (например, IsAuthenticated).
   - Пагинация для list (PageNumber или LimitOffset).
   - Единый формат ошибок (DRF exception handler или drf-standardized-errors).

9. **URL и роутер**
   - Подключить роутер для `requests`; зарегистрировать `api/requests` и action/detail для `run`.

---

### Этап 4 — Форма (Django + Bootstrap)

10. **Шаблон формы**
    - Страница с формой: номер заявки (обязательный), выбор кластера (select из списка кластеров), `dst_host`, `dst_port`.
    - Submit → POST на DRF API (например, `/api/requests/`) или на Django view, который вызывает тот же сервис.
    - После успеха — редирект или сообщение со ссылкой на заявку `/requests/{ticket_id}` и статусом.

11. **Страница списка заявок и кнопка Run**
    - Список заявок (данные с API или через Django view), напротив каждой — кнопка Run (вызов `POST /api/requests/{ticket_id}/run`).
    - Отображение статуса (new, validated, in_progress, success, failed, needs_manual).

12. **Страница RunPipeline (опционально для MVP)**
    - Отдельная страница для ручного запуска pipeline (та же форма создания заявки) + при желании массовый запуск/история — можно отложить на след. итерацию.

---

### Этап 5 — Temporal: workflow и activity для K8s access

13. **Workflow**
    - Новый workflow (например, `K8sAccessCheckWorkflow`): входной параметр `ticket_id`. В workflow: activity «получить данные заявки из БД» (по ticket_id), activity «запуск AWX job» (передать awx_template_id, host_dst, port_dst), при успехе — activity «обновить статус заявки в БД» (success) и при необходимости «закрыть/комментировать тикет» (заглушка). При ошибке — обновить статус failed.

14. **Activities**
    - `get_request_data(ticket_id)` — получение данных заявки через **HTTP GET к DRF API** (`GET /api/requests/{ticket_id}/`), т.к. worker — отдельный процесс от Django.
    - `launch_awx_job(awx_template_id, host_dst, port_dst)` — **реальный вызов AWX API**: POST на `{AWX_URL}/api/v2/job_templates/{id}/launch/`, Basic Auth (логин/токен из env), тело `{"extra_vars": {"host_dst": "...", "port_dst": ...}}`. URL и учётные данные — из настроек (env).
    - `update_request_status(ticket_id, status)` — обновление статуса через **HTTP PATCH к DRF API** (например, `PATCH /api/requests/{ticket_id}/` с полем status).
    - Идемпотентность: по возможности сохранять `awx_job_id` в заявке и при повторе проверять статус job в AWX.

15. **Worker**
    - Зарегистрировать новый workflow и новые activities; task_queue общий или отдельный по необходимости.
    - Зависимости: temporalio; при вызове БД/API из activity — httpx или Django/ORM (если worker в одном проекте с Django, иначе — только HTTP/клиент к backend).

---

### Этап 6 — Интеграция и порядок запуска

16. **Связка Django → Temporal**
    - В месте старта workflow (после create или по `POST .../run`) использовать один и тот же `TemporalAdapter` с `workflow_id = ticket_id`.
    - Обработка ошибок: при падении старта — откат status обратно в `validated` и запись ошибки (поле `last_error` или аналог); опционально retry по расписанию (cron/management command).

17. **Документация (отдельные файлы под AWX-кейс)**
    - Создать **README_AWX.md**: как поднять Django, как запустить worker и starter, как открыть форму и запустить заявку на проверку доступа (K8s + AWX).
    - Создать **ARCHITECTURE_AWX.md**: заявки (таблица, статусы, поток Push), взаимодействие Django ↔ Temporal ↔ AWX, пример запуска AWX job (curl на `https://awx.example.com`, extra_vars).

18. **Качество кода**
    - Прогнать `ruff check . --fix`, `ruff format .`; при необходимости `mypy` для backend и worker.
    - Типы и Enum — по правилам django-data-modeling и typing-cheatsheet.

---

## 5. Зависимости (кратко)

- **Backend (Django):** Django, djangorestframework, django-cors-headers (если нужен отдельный фронт), temporalio (клиент), sqlite (встроен), позже psycopg2.
- **Worker:** temporalio, при необходимости httpx для вызова backend API из activities.
- **Общее:** Python 3.13+, Ruff, mypy в dev.

---

## 6. Риски и отложенные решения

- **Worker и БД:** worker — отдельный процесс от Django; activities получают и обновляют заявки **только через HTTP к DRF API** (GET/PATCH). Прямой доступ к БД из worker не используется.
- **AWX:** с первого этапа — реальный вызов AWX API; URL, логин и токен/пароль — из env (позже Vault/K8s Secrets). В примерах использовать абстрактный хост `https://awx.example.com`. Формат запроса: POST `.../job_templates/{id}/launch/` с Basic Auth и `extra_vars: { host_dst, port_dst }`.
- **Тикет-система (закрытие/комментарий):** в MVP можно не реализовывать; в workflow оставить пустую activity или заглушку.

---

## 7. Принятые решения

- **Структура репозитория:** отдельные папки: Django в `backend/`, Temporal worker в `worker/`, клиент для запуска workflow в `starter/`. Файлы `starter.py`, `worker.py`, `workflows.py`, `activities.py` в корне удалены (ветка под AWX-кейс).
- **Примеры и документация по AWX:** в коде, в **README_AWX.md** и **ARCHITECTURE_AWX.md** использовать только абстрактный хост для примеров: `https://awx.example.com`. Реальный URL и учётные данные — исключительно из env, без дефолтов в репозитории.
