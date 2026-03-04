# План работ: заявки (K8s access, VM, DB) + Temporal

Опирается на правила из `.cursor/rules/` (Django, DRF, typing 3.13+, Ruff) и на обсуждённую архитектуру (webhook → БД → Push-старт workflow, ручной запуск через форму).

**Чеклист задач по этапам:** [TASKS_AWX.md](TASKS_AWX.md).  
**Архитектура и документация:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/TEMPORAL_ROLE_AND_BENEFITS.md](docs/TEMPORAL_ROLE_AND_BENEFITS.md), [docs/TICKET_ADAPTER_STARTER_NOTES.md](docs/TICKET_ADAPTER_STARTER_NOTES.md).

---

## 1. Цель и границы

### MVP (текущее состояние)

- **Ручной запуск**: форма (Django + Bootstrap) → сохранение заявки в БД → запуск Temporal workflow (Push: по кнопке Run или сразу после валидации).
- **Тип заявки (реализован):** проверка сетевого доступа от кластеров K8s (поля: номер заявки, кластер, `dst_host`, `dst_port`, комментарий).
- **БД**: SQLite на текущем этапе; схема заложена под последующий перенос на PostgreSQL.
- **Temporal**: workflow и activities под AWX в `worker/`; worker и starter — отдельные процессы.
- **Webhook из тикет-системы**: вне MVP (следующий этап).

### Дальнейшее развитие

- **Типы заявок:** те же принципы (форма → сервис → workflow) для **создания VM** и **создания DB**; шаблоны и URL по типу потока: `k8s_access/`, затем `vm/`, `db/`.
- **URL и шаблоны:** один префикс на тип потока (например `/k8s-access/`, позже `/vm/`, `/db/`), без общего `/requests/` в пути.

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

## 3. Структура репозитория (текущая)

```
temporal-project/
├── .cursor/
├── backend/                         # Django (API + формы)
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py                  # api/, api/schema/, api/docs/, k8s-access/
│   │   └── ...
│   ├── apps/
│   │   └── infra_requests/          # приложение заявок (имя requests конфликтует с пакетом Python)
│   │       ├── models.py            # Request (ticket_id, source, type, status, payload, normalized, ...)
│   │       ├── adapters/            # TemporalAdapter
│   │       ├── repositories/
│   │       ├── services/
│   │       ├── serializers.py
│   │       ├── views.py             # ViewSet API
│   │       ├── views_pages.py       # k8s_access_list, k8s_access_create, k8s_access_edit, k8s_access_run
│   │       ├── urls.py              # API роутер
│   │       ├── urls_pages.py        # k8s-access/ (list, create, edit, run)
│   │       └── templates/
│   │           └── k8s_access/      # по типу потока; позже vm/, db/
│   │               ├── list.html
│   │               └── form.html
│   └── requirements.txt             # Django, DRF, drf-spectacular, temporalio (клиент), ...
├── worker/                          # Temporal worker (отдельный процесс)
│   ├── worker.py
│   ├── workflows.py                 # K8sAccessCheckWorkflow (get_request_data → launch_awx_job → poll get_awx_job_status → update_request_status)
│   ├── activities.py                # get_request_data, launch_awx_job, get_awx_job_status, update_request_status
│   └── requirements.txt
├── starter/                         # Клиент для ручного/тестового запуска workflow
│   └── starter.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TEMPORAL_ROLE_AND_BENEFITS.md
│   └── TICKET_ADAPTER_STARTER_NOTES.md
├── PLAN.md
├── README.md
├── TASKS_AWX.md                    # чеклист по этапам
└── requirements.txt
```

---

## 4. Этапы работ

### Этап 1 — Инфраструктура и модель данных

1. **Инициализация Django-проекта**
   - Создать проект (например, `backend/`), настроить `config/settings.py` (SQLite по умолчанию, DRF, CORS при необходимости).
   - Добавить приложение заявок (в проекте: `infra_requests`).

2. **Модель заявки и миграции**
   - Таблица `requests`: `id`, `ticket_id` (unique), `source`, `type`, `status`, `requester`, `payload` (JSONField), `normalized` (JSONField), `workflow_id`, `created_at`, `updated_at`.
   - Enum для `status`: new, needs_manual, validated, in_progress, success, failed.
   - Enum или справочник для `type` (пока один тип: k8s_access).
   - Индексы: `ticket_id` (unique), `status`, при необходимости `type`, `created_at`.
   - Создать миграции, применить на SQLite.

3. **Справочник кластер → AWX template id**
   - Для MVP: константа в коде (словарь `CLUSTER_AWX_TEMPLATE`) в приложении заявок.
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
   - Роутер для заявок: `api/requests` (list, retrieve, create, PATCH, action `run`). Страницы с формами: отдельный urlconf под префиксом (например `k8s-access/` в корневом urls.py).

---

### Этап 4 — Форма (Django + Bootstrap)

10. **Шаблон формы (K8s access)**
    - Страница с формой: номер заявки (обязательный), выбор кластера (select), `dst_host`, `dst_port`, комментарий.
    - Submit → Django view (сервис); после успеха — редирект на список с параметрами `created`, `status`.
    - Шаблоны по типу потока: `k8s_access/list.html`, `k8s_access/form.html` (позже — `vm/`, `db/`).

11. **Страница списка заявок и кнопка Run**
    - Список заявок (view + repository), напротив каждой — кнопка Run (`POST /k8s-access/{ticket_id}/run/`).
    - Отображение статуса (new, needs_manual, validated, in_progress, success, failed).
    - Для заявок в статусе **needs_manual** и **new** — кнопка «Исправить» → страница редактирования (форма с подставленными полями, сохранение через тот же сервис).

12. **Редактирование заявки (needs_manual)**
    - URL: `/k8s-access/{ticket_id}/edit/`. GET — форма с данными из заявки (normalized); POST — валидация и create_or_update, при успешной валидации возможен автозапуск workflow. Номер заявки при редактировании только для чтения.

13. **Страница RunPipeline (опционально)**
    - Та же форма создания, вход по ссылке с `?pipeline=1`; массовый запуск/история — на следующих итерациях.

---

### Этап 5 — Temporal: workflow и activities для K8s access

14. **Workflow**
    - `K8sAccessCheckWorkflow(ticket_id)`: получить данные заявки (activity) → запустить AWX job (activity) → цикл опроса статуса job (`workflow.sleep` + activity `get_awx_job_status`) до терминального статуса → activity «обновить статус заявки» (success/failed) с опциональным блоком `awx` (job_id, status, message) в normalized. При ошибке — обновить статус failed.

15. **Activities**
    - `get_request_data(ticket_id)` — **HTTP GET** к DRF API (`GET /api/requests/{ticket_id}/`).
    - `launch_awx_job(awx_template_id, host_dst, port_dst)` — **POST** на AWX API `.../job_templates/{id}/launch/`, Basic Auth, `extra_vars: { host_dst, port_dst }`; URL и учётные данные из env.
    - `get_awx_job_status(job_id)` — **GET** AWX `.../jobs/{id}/`, возврат status и message (для цикла опроса в workflow).
    - `update_request_status(ticket_id, status, awx=None)` — **HTTP PATCH** к DRF API с полем `status` и опционально `awx` (merge в normalized на стороне backend).
    - Идемпотентность: сохранять `awx_job_id` в заявке (через awx), при повторе при необходимости проверять статус job в AWX.

16. **Worker**
    - Зарегистрировать workflow и все activities; task_queue (например `awx-task-queue`). Зависимости: temporalio, httpx.

---

### Этап 6 — Интеграция и документация

17. **Связка Django → Temporal**
    - При create и при `POST .../run` — один и тот же `TemporalAdapter.start_workflow(workflow_id=ticket_id, ...)`.
    - При ошибке старта — откат status в `validated`, логирование; при необходимости retry (cron/management command).

18. **API и документация**
    - **drf-spectacular**: OpenAPI 3 схема (`/api/schema/`), Swagger UI (`/api/docs/`). Сериализаторы и ViewSet совместимы с DEFAULT_SCHEMA_CLASS.
    - **Документация** в `docs/`: ARCHITECTURE.md (Temporal, workflow, activities), TEMPORAL_ROLE_AND_BENEFITS.md (зачем Temporal, преимущества), TICKET_ADAPTER_STARTER_NOTES.md (интеграция с тикет-системой). README в корне — общий запуск Django, worker, форма и заявки.

19. **Качество кода**
    - `ruff check . --fix`, `ruff format .`; при необходимости `mypy`. Типы и Enum — по правилам django-data-modeling и typing-cheatsheet.

---

## 5. Зависимости (кратко)

- **Backend (Django):** Django, djangorestframework, drf-spectacular, django-cors-headers, temporalio (клиент), python-dotenv, sqlite (встроен), позже psycopg2.
- **Worker:** temporalio, httpx (вызов backend API и AWX), cryptography (Fernet для AWX_PASSWORD_ENCRYPTED при необходимости).
- **Общее:** Python 3.13+, Ruff, mypy в dev.

---

## 6. Риски и отложенные решения

- **Worker и БД:** worker — отдельный процесс от Django; activities получают и обновляют заявки **только через HTTP к DRF API** (GET/PATCH). Прямой доступ к БД из worker не используется.
- **AWX:** с первого этапа — реальный вызов AWX API; URL, логин и токен/пароль — из env (позже Vault/K8s Secrets). В примерах использовать абстрактный хост `https://awx.example.com`. Формат запроса: POST `.../job_templates/{id}/launch/` с Basic Auth и `extra_vars: { host_dst, port_dst }`.
- **Тикет-система (закрытие/комментарий):** в MVP можно не реализовывать; в workflow оставить пустую activity или заглушку.

---

## 7. Принятые решения

- **Структура репозитория:** Django в `backend/`, worker в `worker/`, starter в `starter/`. Документация в `docs/` (ARCHITECTURE.md, TEMPORAL_ROLE_AND_BENEFITS.md, TICKET_ADAPTER_STARTER_NOTES.md).
- **Приложение заявок:** имя `infra_requests` (избежание конфликта с пакетом `requests`).
- **URL и шаблоны по типу потока:** префикс в браузере без `/requests/` — сразу по типу: `/k8s-access/` (list, create, edit, run). View и URL names: `k8s_access_list`, `k8s_access_create`, `k8s_access_edit`, `k8s_access_run`. Шаблоны в `templates/k8s_access/` (list.html, form.html). Для VM и DB — аналогично `/vm/`, `/db/` и папки `vm/`, `db/`.
- **Редактирование заявки:** для статусов needs_manual и new — страница `/k8s-access/{ticket_id}/edit/` с формой (данные из normalized), сохранение через тот же сервис; при успешной валидации возможен автозапуск workflow.
- **AWX и секреты:** в коде и документации для примеров — только абстрактный хост `https://awx.example.com`. Реальные URL и учётные данные — из env, без дефолтов в репозитории.
