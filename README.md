# Temporal Project — пример Workflow + Activities

Минимальный пример приложения на [Temporal](https://temporal.io/): Workflow вызывает Activity и возвращает результат.

## Требования

- Python 3.8+
- Запущенный [Temporal Server](https://docs.temporal.io/self-hosted-guide) (по умолчанию слушает `localhost:7233`)

## Установка

### 1. Виртуальное окружение (рекомендуется)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 2. Зависимости

```bash
pip install -r requirements.txt
```

## Запуск Temporal Server (локально)

### Вариант 1: Docker Compose

Если сервер ещё не запущен, можно поднять его через [Docker](https://docs.temporal.io/self-hosted-guide/docker):

```bash
git clone https://github.com/temporalio/docker-compose.git temporal-docker
cd temporal-docker
docker-compose up -d
```

После старта сервер доступен на `localhost:7233`. Для деталей см. [официальную документацию](https://docs.temporal.io/self-hosted-guide).

### Вариант 2: Temporal CLI (dev-сервер)

1. Установи [Temporal CLI](https://docs.temporal.io/cli#install).
2. В терминале выполни:

```bash
temporal server start-dev --dynamic-config-value "frontend.WorkerHeartbeatsEnabled=true"
```

**Примечание:** Флаг `--dynamic-config-value` включает поддержку runtime heartbeating на сервере, что убирает предупреждение `Worker heartbeating configured for runtime, but server version does not support it` при запуске worker.

Сервер и Web UI поднимутся локально (gRPC: `localhost:7233`, UI — порт будет указан в выводе команды). Остановка — `Ctrl+C`.

## Как запускать приложение

Нужны **два процесса**: worker (обрабатывает задачи) и starter (запускает workflow).

### 1. Запуск Worker (первым)

В первом терминале:

```bash
python worker.py
```

Должно появиться: `Worker started.` — worker слушает очередь `my-task-queue`.

### 2. Запуск Starter (во втором терминале)

Во втором терминале (в той же директории, с активированным venv):

```bash
python starter.py
```

Starter отправит один workflow; в консоли появится что-то вроде:

```
Workflow result: Hello Василий
```

(имя задаётся в `starter.py` — второй аргумент в `execute_workflow`.)

## Структура проекта

| Файл           | Назначение |
|----------------|------------|
| `workflows.py` | Описание Workflow (оркестрация) |
| `activities.py`| Activity — единица работы (например, `greet`) |
| `worker.py`    | Процесс, который выполняет workflows и activities |
| `starter.py`   | Клиент, который запускает workflow и ждёт результат |

Подробнее — в [ARCHITECTURE.md](ARCHITECTURE.md).

## Настройка подключения к Temporal

По умолчанию используется `localhost:7233`. Чтобы изменить адрес или namespace, правьте в коде:

- **worker.py**: `Client.connect("localhost:7233")` и параметры `Worker(...)`.
- **starter.py**: `Client.connect("localhost:7233")` и аргументы `execute_workflow(...)`.

Пример для другого хоста/порта:

```python
client = await Client.connect("temporal.example.com:7233", namespace="my-namespace")
```

## Возможные проблемы

- **Ошибка подключения к Temporal**  
  Убедитесь, что Temporal Server запущен и доступен по указанному адресу (по умолчанию `localhost:7233`).

- **Worker не обрабатывает задачи**  
  Сначала всегда запускайте `worker.py`, затем `starter.py`. Имена `task_queue` в worker и starter должны совпадать (`my-task-queue`).

- **Предупреждение про heartbeating**  
  В `worker.py` уже настроено подавление этого предупреждения для несовместимых версий сервера; на работу примера оно не влияет.
