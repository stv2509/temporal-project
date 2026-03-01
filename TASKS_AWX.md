# Задачи: AWX + K8s access (чеклист)

Источник решений и деталей — [PLAN.md](PLAN.md). Здесь отмечаем выполненные пункты.

---

## Этап 1 — Инфраструктура и модель данных

- [x] **1.1** Инициализировать Django-проект в `backend/` (config/settings.py, SQLite, DRF, CORS при необходимости)
- [x] **1.2** Добавить приложение для заявок (`apps.ticket_requests` — имя `requests` конфликтует с пакетом Python)
- [x] **1.3** Модель заявки: таблица `requests` (id, ticket_id unique, source, type, status, requester, payload, normalized, workflow_id, created_at, updated_at)
- [x] **1.4** Enum для status (new, needs_manual, validated, in_progress, success, failed) и type (k8s_access)
- [x] **1.5** Индексы: ticket_id (unique), status, type, created_at
- [x] **1.6** Миграции, применить на SQLite
- [x] **1.7** Справочник CLUSTER_AWX_TEMPLATE в коде (DEV→14, GUEST→239, OFFICE→26, OSA→128, PL→21, TEST1→16, TEST3→19, TEST4→17, TEST5→18, TEST6_PG→20, TEST7→22, TEST8→241)
- [x] **1.8 Проверка:** `cd backend && python manage.py runserver` — сервер поднимается; зайти в `/admin/`, создать суперпользователя (`createsuperuser`), добавить тестовую заявку через админку и убедиться, что модель сохраняется.

---

## Этап 2 — Слой данных и сервисы

- [x] **2.1** Repository: get_by_ticket_id, upsert (ON CONFLICT по ticket_id), list_by_status, list_by_filters
- [x] **2.2** RequestService: create_or_update, validate_normalized (k8s_access: cluster, dst_host, dst_port), claim_for_run (атомарный UPDATE)
- [x] **2.3** TemporalAdapter: start_workflow(workflow_id, workflow_name, args), обработка WorkflowAlreadyStarted, хост/секреты из settings/env
- [x] **2.4 Проверка:** В `python manage.py shell` вызвать Repository (get_by_ticket_id, upsert, list_by_status) и RequestService (create_or_update, validate_normalized, claim_for_run). Убедиться, что заявка создаётся/обновляется и claim меняет статус. TemporalAdapter при отсутствии сервера может падать по подключению — достаточно проверить, что код импортируется и вызывается.

---

## Этап 3 — DRF API и сериализаторы

- [x] **3.1** RequestCreateSerializer (ticket_id, cluster, dst_host, dst_port, comment опц.; валидация порта 1–65535, cluster из списка; в validate — normalized с awx_template_id)
- [x] **3.2** RequestListSerializer и RequestDetailSerializer; get_serializer_class по action
- [x] **3.3** ViewSet заявок: list, retrieve, create (сервис + при успехе start_workflow, иначе needs_manual)
- [x] **3.4** Endpoint POST /api/requests/{ticket_id}/run (claim + start workflow), permission_classes
- [x] **3.5** Пагинация для list, единый формат ошибок
- [x] **3.6** Роутер и URL: api/requests, action run
- [x] **3.7 Проверка:** `python manage.py runserver`. Проверить: `GET /api/requests/` (список, пагинация), `POST /api/requests/` (создание заявки с ticket_id, cluster, dst_host, dst_port), `GET /api/requests/{ticket_id}/`, `POST /api/requests/{ticket_id}/run` (при status=validated). Убедиться, что ответы и ошибки валидации в ожидаемом формате. Для POST нужна авторизация: Basic Auth (`-u user:password`) или сессия после входа в /admin/.

---

## Этап 4 — Форма (Django + Bootstrap)

- [x] **4.1** Шаблон формы: номер заявки, кластер (select), dst_host, dst_port; submit → view → сервис
- [x] **4.2** После успеха — редирект на список с GET-параметрами created, status; сообщение в списке
- [x] **4.3** Страница списка заявок + кнопка Run у каждой (POST /requests/<ticket_id>/run/), отображение статуса
- [x] **4.4** (Опционально) Run pipeline — та же форма, вход по ссылке «Run pipeline (ручной запуск)» (/requests/create/?pipeline=1)
- [x] **4.5 Проверка:** `python manage.py runserver`. Войти в /admin/, открыть /requests/, заполнить форму и отправить; нажать Run у записи со статусом validated. Убедиться, что редирект/сообщения и отображение статусов работают.

---

## Этап 5 — Temporal: workflow и activities

- [x] **5.1** Workflow K8sAccessCheckWorkflow(ticket_id): get_request_data → launch_awx_job → update_request_status (success/failed)
- [x] **5.2** Activity get_request_data(ticket_id) — HTTP GET к DRF API
- [x] **5.3** Activity launch_awx_job(awx_template_id, host_dst, port_dst) — POST на AWX API (Basic Auth, extra_vars), URL/учётные данные из env
- [x] **5.4** Activity update_request_status(ticket_id, status) — HTTP PATCH к DRF API
- [x] **5.5** Worker: зарегистрировать workflow и activities, task_queue; зависимости temporalio, httpx
- [ ] **5.6 Проверка:** Запустить Temporal Server (локально или dev). Запустить Django (`runserver`). Запустить worker (`python worker/worker.py`). Создать заявку через API или форму и нажать Run (или вызвать `POST .../run`). В Temporal UI убедиться, что workflow появился и выполнился; в БД/API статус заявки обновился (in_progress → success/failed). При наличии AWX — проверить запуск job в AWX.

---

## Этап 6 — Интеграция и документация

- [ ] **6.1** Связка: при create и при /run использовать TemporalAdapter с workflow_id=ticket_id; при ошибке старта — откат status, last_error
- [ ] **6.2** README_AWX.md: запуск Django, worker, starter, форма и заявка
- [ ] **6.3** ARCHITECTURE_AWX.md: таблица заявок, статусы, поток Push, Django ↔ Temporal ↔ AWX, пример curl на awx.example.com
- [ ] **6.4** Ruff (check --fix, format), при необходимости mypy; типы по правилам проекта
- [ ] **6.5 Проверка:** Полный прогон: форма → создание заявки → Run → workflow выполняется → статус success/failed, при интеграции с AWX — job в AWX запущен. Проверить по README_AWX.md порядок запуска сервисов.

---

*Отмечать: `- [x]` при выполнении.*
