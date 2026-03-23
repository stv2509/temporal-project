# Задачи: Multi-env + Multi-type (чеклист)

Источник: текущие договорённости по `test/prod/dev`, Temporal namespaces, 10+ `Request.type`,
двум AWX (`test`/`prod`) и масштабированию через K8S/Temporal Worker Controller.

---

## Этап 1 — Конфигурация окружений (backend/worker/k8s)

- [x] **1.1** Ввести явный ключ окружения AWX (`AWX_ENV=test|prod`) отдельно от `TEMPORAL_NAMESPACE`.
- [ ] **1.2** Зафиксировать матрицу окружений:
  - `test`: `TEMPORAL_NAMESPACE=test`, `AWX_ENV=test`
  - `prod`: `TEMPORAL_NAMESPACE=prod`, `AWX_ENV=prod`
  - `dev`: `TEMPORAL_NAMESPACE=dev`, `AWX_ENV=test`
- [x] **1.3** Подготовить env/values шаблоны для backend и worker под `test/prod/dev`.
- [x] **1.4** Убрать неявные зависимости от одного `TEMPORAL_TASK_QUEUE` и перейти на per-domain очереди.
- [ ] **1.5 Проверка:** Конфигурации окружений валидны и не смешивают `prod` с `test` секретами.

---

## Этап 2 — Константы шаблонов AWX и роутинг типов заявок

- [x] **2.1** Переделать карту шаблонов из плоской `CLUSTER_AWX_TEMPLATE` в иерархическую:
  `AWX_ENV -> REQUEST_TYPE -> CLUSTER -> TEMPLATE_ID`.
- [x] **2.1.1** В `backend/apps/infra_requests/constants.py` добавить явную карту
  `CLUSTER_AWX_TEMPLATE` для `k8s_access` в `prod` (рабочая, не закомментированная).
- [ ] **2.1.2** Для `k8s_access/prod` зафиксировать обязательный минимальный набор ключей кластера:
  `PROD`, `SBP`.
- [ ] **2.1.3** Для `k8s_access/prod` заполнить вымешленные `template_id` из prod AWX по каждому ключу
  и добавить проверку на отсутствие дубликатов `template_id` (на уровне ревью/теста конфигурации).
- [ ] **2.1.4** Для `k8s_access/prod` определить политику неизвестного кластера:
  fail-fast ошибка валидации + человеко-читаемое сообщение.
- [ ] # **2.1.vm_create.test** В `constants.py` добавить закомментированную вымышленную карту
  `CLUSTER_AWX_TEMPLATE` для `vm_create` в `test`.
- [ ] # **2.1.vm_create.prod** В `constants.py` добавить закомментированную вымышленную карту
  `CLUSTER_AWX_TEMPLATE` для `vm_create` в `prod`.
- [x] **2.2** Добавить helper доступа к template-id c fail-fast ошибками при отсутствии ключа.
- [x] **2.3** Ввести routing-map для workflow:
  `REQUEST_TYPE -> workflow_name + task_queue`.
- [x] **2.4** Обеспечить единый источник правды для роутинга в `backend/config/settings.py`.
- [ ] **2.5 Проверка:** Для каждого активного `Request.type` есть route и template-map в нужном `AWX_ENV`.
- [ ] # **2.vm_create** Добавить route и template-map для вымышленного типа `vm_create` (закомментировано до реализации).

---

## Этап 3 — Доменная модель и сервисный слой

- [ ] **3.1** Расширить `RequestType` до набора 10+ типов (по утверждённому списку).
- [x] **3.2** Обновить `RequestService.validate_normalized(...)` с логикой по `request_type`.
- [x] **3.3** Обновить `prepare_create_from_form(...)`/подготовку normalized для разных типов.
- [x] **3.4** Исключить жёсткую привязку только к `k8s_access` в сервисном слое.
- [ ] **3.5 Проверка:** Невалидные комбинации `request_type/cluster/env` корректно отклоняются.
- [ ] # **3.vm_create** Добавить в сервис вымышленную ветку `vm_create` (закомментировано до реализации).

---

## Этап 4 — Backend запуск workflow и TemporalAdapter

- [x] **4.1** При старте workflow выбирать `task_queue` и `workflow_name` из routing-map.
- [x] **4.2** Передавать `task_queue` в `TemporalAdapter(...)` явно для каждого `Request.type`.
- [x] **4.3** Удалить legacy-fallback на старый `TEMPORAL_TASK_QUEUE`; использовать только route queue.
- [x] **4.4** Добавить защиту от запуска workflow без route-конфига.
- [ ] **4.5 Проверка:** `create/run` запускают workflow в корректной очереди для каждого типа.
- [ ] # **4.vm_create** Пробросить `vm_create` через adapter/route (закомментировано до реализации).

---

## Этап 5 — Worker реорганизация под 10+ типов

- [x] **5.1** Ввести структуру `worker/runner.py`, `worker/registry.py`, `worker/shared/*`.
- [x] **5.2** Разнести workflow/activity по доменным модулям (`worker/domains/<request_type>/...`).
  Реализация `k8s_access`: `worker/domains/k8s_access/activities.py`, `workflows.py` (импорт activities через `unsafe.imports_passed_through`). Корневые `worker/activities.py` и `worker/workflows.py` удалены.
- [x] **5.3** Реализовать реестр доменов: `domain_key`, `task_queue`, workflows, activities.
- [x] **5.4** Вынести общий backend API-клиент в `worker/shared/backend_api.py`.
- [x] **5.5** Вынести AWX profiles (`test/prod`) в `worker/shared/awx_profiles.py`.
- [ ] **5.6 Проверка:** Каждый worker-process регистрирует только нужные workflows/activities.
- [ ] # **5.vm_create** Создать доменную заготовку `worker/domains/vm_create/` (закомментировано до реализации).

---

## Этап 6 — API/Forms/UI под несколько типов

- [x] **6.1** Расширить API контракты для нескольких `Request.type` (сериализаторы/валидация).
- [x] **6.2** Обновить page/forms flow для выбора/обработки разных типов заявок.
- [x] **6.3** Добавить отображение `request_type`, route и статусных сообщений в списках/деталях.
- [ ] **6.4 Проверка:** Создание/редактирование/Run работает для нескольких типов.
- [ ] # **6.vm_create** Добавить UI/API заготовку типа `vm_create` (закомментировано до реализации).

---

## Этап 7 — Kubernetes и Temporal Worker Controller

- [ ] **7.1** Подготовить отдельные манифесты/values для `test/prod/dev`.
- [ ] **7.2** Для worker deployment задать корректный `TEMPORAL_NAMESPACE` и env secrets.
- [ ] **7.3** Подготовить шаблон `TemporalWorkerDeployment` на домен/очередь.
- [ ] **7.4** Развести rollout/pinning/rollback стратегию по окружениям.
- [ ] **7.5 Проверка:** deployment в `dev/test/prod` не конфликтуют и используют верные namespace/queues.
- [ ] # **7.vm_create** Подготовить шаблон TWD для `vm_create` (закомментировано до реализации).

---

## Этап 8 — Тесты, линт, документация

- [ ] **8.1** Unit-тесты lookup/route/template-map (включая ошибки отсутствующих ключей).
- [ ] **8.2** Интеграционные тесты create/run по минимум двум `Request.type`.
- [ ] **8.3** Обновить `README` и docs по env matrix (`test/prod/dev`) и AWX strategy.
- [ ] **8.4** Прогнать `ruff check .`, `ruff check . --fix`, `ruff format .`.
- [ ] **8.5** (Опционально) Прогнать mypy для backend/worker.
- [ ] **8.6 Проверка:** E2E сценарии проходят в `dev` (AWX test) и `prod` (AWX prod).
- [ ] # **8.vm_create** Добавить тест-кейсы для `vm_create` (закомментировано до реализации).

---

*Отмечать: `- [x]` при выполнении. Часть этапов уже реализована; оставшиеся пункты — план до запуска в прод.*
