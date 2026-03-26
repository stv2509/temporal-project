# Temporal Project — Django + Temporal + AWX

Проект для заявок на инфраструктурные операции:
- backend на Django/DRF;
- workflow orchestration в Temporal;
- запуск job в AWX из worker activities.

Поддерживается routing по `request_type`, окружения `test/prod/dev` и разделение AWX через `AWX_ENV`.

## Требования

- Python 3.13+
- Temporal Server (`localhost:7233` по умолчанию)
- (опционально) AWX для выполнения job templates

## Установка

```bash
python -m venv .venv
# Windows (git-bash)
source .venv/Scripts/activate
pip install -r requirements.txt
pip install -r worker/requirements.txt
```

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните значения.

Ключевые переменные:

- `TEMPORAL_HOST` — адрес Temporal.
- `TEMPORAL_NAMESPACE` — namespace Temporal (`test`, `prod`, `dev`).
- `DB_ENGINE` — режим БД: `sqlite` (локально) или `postgres`.
- `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_SCHEMA` — параметры PostgreSQL (используются при `DB_ENGINE=postgres`).
- `AWX_ENV` — контур AWX (`test`/`prod`), где `dev` обычно маппится на `test`.
- `CA_BUNDLE_PATH` — CA bundle для TLS verification в worker (httpx). Допустимые значения:
  - путь к PEM-файлу с CA bundle
  - `true` / `false`
- `TEMPORAL_TASK_QUEUE_K8S_ACCESS` — очередь для `k8s_access`.
- `AWX_URL_TEST`/`AWX_URL_PROD` и соответствующие креды.

Принятая матрица окружений:
- `test`: `TEMPORAL_NAMESPACE=test`, `AWX_ENV=test`
- `prod`: `TEMPORAL_NAMESPACE=prod`, `AWX_ENV=prod`
- `dev`: `TEMPORAL_NAMESPACE=dev`, `AWX_ENV=test`

### Режимы базы данных (dual-mode)

- `DB_ENGINE=sqlite` — локальная разработка, используется файл `backend/db.sqlite3`.
- `DB_ENGINE=postgres` — подключение к PostgreSQL.
- Для PostgreSQL выставляется `search_path` как `POSTGRES_SCHEMA,public` (по умолчанию схема `portal`).

## Запуск

Нужны 3 процесса: backend, worker и Temporal Server.

### 1) Temporal Server

Через CLI:

```bash
temporal server start-dev --dynamic-config-value "frontend.WorkerHeartbeatsEnabled=true"
```

### 2) Django backend

```bash
cd backend
python manage.py migrate
python manage.py runserver
```

UI формы: `http://localhost:8000/k8s-access/`  
API: `http://localhost:8000/api/requests/`  
Swagger: `http://localhost:8000/api/docs/`

### 3) Worker

Из **корня репозитория** (чтобы подтянулись импорты `worker.*` и `.env` из корня):

```bash
python worker/worker.py
```

**Что делает процесс.** `worker/worker.py` — тонкий entrypoint; реальный запуск в `worker/runner.py`: загрузка `.env`, подключение к Temporal, выбор домена и регистрация workflows/activities из `worker/registry.py`.

**Домен воркера — через `WORKER_DOMAIN`.** Одна и та же команда, разные процессы:

| Переменная | Назначение | По умолчанию |
|------------|------------|--------------|
| `WORKER_DOMAIN` | Ключ из `worker/registry.py` (`k8s_access`, позже `vm_create`) | `k8s_access` |
| `TEMPORAL_TASK_QUEUE_K8S_ACCESS` | Очередь, если домен `k8s_access` | `awx-task-queue` |
| `TEMPORAL_HOST`, `TEMPORAL_NAMESPACE` | Куда подключаться | см. `.env.example` |

Очередь воркера **должна совпадать** с `task_queue` в `TEMPORAL_WORKFLOW_ROUTES` для соответствующего `request_type`, иначе задачи зависнут без исполнителя.

**Несколько воркеров (разные домены / очереди).** Запускайте **отдельные процессы** (или контейнеры) с разным `WORKER_DOMAIN` и своими `TEMPORAL_TASK_QUEUE_*`:

```bash
# Воркер только для k8s_access
WORKER_DOMAIN=k8s_access python worker/worker.py
```

```bash
# Когда появится домен vm_create в registry — второй процесс
WORKER_DOMAIN=vm_create TEMPORAL_TASK_QUEUE_VM_CREATE=vm-create-task-queue python worker/worker.py
```

Сейчас в реестре активен **только** `k8s_access`; блок `vm_create` — заготовка. Пока домен не зарегистрирован и не реализован под `worker/domains/vm_create/`, второй процесс с `WORKER_DOMAIN=vm_create` не нужен.

## Docker

Добавлены отдельные Dockerfile для backend и worker:

- `docker/backend/Dockerfile`
- `docker/worker/Dockerfile`

Оба образа используют базу `registry.red-soft.ru/ubi8/ubi-minimal:8.0.2-260324`, устанавливают `uv`, Python (по умолчанию `3.14.3`) и зависимости из соответствующих `requirements.txt`.

Сборка образов:

```bash
docker build -f docker/backend/Dockerfile -t temporal-backend:dev .
docker build -f docker/worker/Dockerfile -t temporal-worker:dev .
```

Смена версии Python при сборке:

```bash
docker build -f docker/backend/Dockerfile --build-arg PYTHON_VERSION=3.13.9 -t temporal-backend:dev .
docker build -f docker/worker/Dockerfile --build-arg PYTHON_VERSION=3.13.9 -t temporal-worker:dev .
```

Worker-образ один для всех доменов. Нужный домен выбирается env-переменной `WORKER_DOMAIN` (`k8s_access`, позже `vm_create`).

## Как работает роутинг

- Backend выбирает `workflow_name` и `task_queue` из `TEMPORAL_WORKFLOW_ROUTES` в `backend/config/settings.py`.
- Для `k8s_access` используется route `k8s_access -> K8sAccessCheckWorkflow + TEMPORAL_TASK_QUEUE_K8S_ACCESS`.
- В `constants.py` template-id выбирается по схеме:
  `AWX_ENV -> request_type -> cluster -> template_id`.
- Для `vm_create` оставлены закомментированные заготовки (`# ...`) в конфиге и реестре.

## Worker архитектура

- `worker/runner.py` — запуск worker по домену (`WORKER_DOMAIN`).
- `worker/registry.py` — реестр доменов (очередь, workflows, activities).
- `worker/shared/backend_api.py` — общий backend API config/auth.
- `worker/shared/awx_profiles.py` — выбор AWX профиля по `AWX_ENV`.
- `worker/domains/k8s_access/*` — доменная обвязка `k8s_access`.

## Проверки качества

```bash
ruff check .
ruff format .
python -m mypy --check-untyped-defs .
```

## Частые проблемы

- **Workflow не стартует**
  - проверьте, что worker запущен;
  - проверьте `task_queue` в `TEMPORAL_WORKFLOW_ROUTES` и env.

- **AWX launch падает**
  - проверьте `AWX_ENV` и соответствующие `AWX_URL_*`/креды;
  - убедитесь, что для `request_type + cluster` есть template-id в `constants.py`.

- **Неправильный namespace**
  - проверьте `TEMPORAL_NAMESPACE` для конкретного окружения (`test/prod/dev`).
