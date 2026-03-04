# Архитектура Temporal и назначение файлов

## Обзор

Этот проект демонстрирует базовую архитектуру Temporal - платформы для оркестрации распределенных приложений. Temporal разделяет бизнес-логику на Workflows (оркестраторы) и Activities (единицы работы).

---

## Структура файлов проекта

### 1. `activities.py` — Бизнес-логика

**Назначение:** Содержит Activities - единицы работы, которые выполняются на worker'е.

**Особенности Activities:**

- ✅ Могут содержать недетерминированную логику
- ✅ Могут вызывать внешние API, работать с БД, обрабатывать файлы
- ✅ Могут быть перезапущены при сбое
- ✅ Выполняются на worker'е (не на сервере Temporal)

**Пример кода:**

```python
from temporalio import activity

# Декоратор, который помечает функцию как Activity
# Activity - это единица работы, которая выполняется на worker'е
@activity.defn
async def greet(name: str) -> str:
    # name - параметр, который передается из workflow
    # Возвращает приветствие с переданным именем
    return f"Hello {name}"
```

---

### 2. `workflows.py` — Оркестрация

**Назначение:** Содержит Workflows - оркестраторы, которые координируют выполнение Activities.

**Особенности Workflows:**

- ⚠️ **Должны быть детерминированными** (без случайных значений, текущего времени и т.д.)
- ✅ Хранят состояние выполнения
- ✅ Могут быть приостановлены и возобновлены
- ✅ Выполняются на сервере Temporal (не на worker'е)
- ✅ Координируют выполнение Activities

**Пример кода:**

```python
from datetime import timedelta
from temporalio import workflow
from activities import greet

# Декоратор, который помечает класс как Workflow
# Workflow - это оркестратор, который координирует выполнение Activities
@workflow.defn
class SayHelloWorkflow:
    # Декоратор, который помечает метод как точку входа в workflow
    @workflow.run
    async def run(self, name: str) -> str:
        # Выполнение Activity с передачей параметров
        return await workflow.execute_activity(
            greet,      # ← Функция activity для выполнения
            name,       # ← Аргумент, который передается в функцию greet
            schedule_to_close_timeout=timedelta(seconds=10),  # ← Таймаут выполнения activity (10 секунд)
        )
```

**Поток данных через параметр `name`:**

1. `starter.py` передает значение `"Temporal"` в workflow
2. Workflow получает его как параметр `name` в методе `run()`
3. Workflow передает `name` в activity `greet()`
4. Activity использует `name` для формирования результата `"Hello Temporal"`

---

### 3. `worker.py` — Обработчик задач

**Назначение:** Worker - это процесс, который выполняет Activities.

**Что делает Worker:**

- Подключается к серверу Temporal
- Слушает очередь задач (`task_queue`)
- Получает задачи из очереди
- Выполняет Activities, зарегистрированные в worker'е
- Может обрабатывать несколько задач параллельно

**Пример кода:**

```python
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import SayHelloWorkflow
from activities import greet

# Настройка логирования для подавления предупреждения о runtime heartbeating
logging.getLogger("temporalio_sdk_core.worker.heartbeat").setLevel(logging.ERROR)

async def main():
    # Подключение к серверу Temporal (по умолчанию localhost:7233)
    client = await Client.connect("localhost:7233")

    # Создание Worker - процесса, который выполняет Activities
    worker = Worker(
        client,                    # ← Клиент для подключения к серверу Temporal
        task_queue="my-task-queue",  # ← Очередь задач, которую слушает worker
        workflows=[SayHelloWorkflow],  # ← Список workflow, которые worker может обрабатывать
        activities=[greet],        # ← Список activities, которые worker может выполнять
    )
    print("Worker started.")
    # Запуск worker - начинает слушать очередь задач и выполнять activities
    await worker.run()

if __name__ == "__main__":
    # Запуск асинхронной функции main
    asyncio.run(main())
```

**Важно:** Worker должен работать постоянно, слушая очередь задач.

---

### 4. `starter.py` — Запуск Workflow

**Назначение:** Starter - это клиент, который запускает Workflow.

**Что делает Starter:**

- Подключается к серверу Temporal
- Отправляет запрос на выполнение Workflow
- Передает аргументы в Workflow
- Указывает очередь задач
- Ждет результат выполнения
- Выводит результат

**Пример кода:**

```python
import asyncio
import uuid
from temporalio.client import Client

async def main():
    # Подключение к серверу Temporal (по умолчанию localhost:7233)
    client = await Client.connect("localhost:7233")

    # Запуск workflow и ожидание результата
    result = await client.execute_workflow(
        "SayHelloWorkflow",        # ← Имя workflow класса для выполнения
        "Temporal",                # ← Аргумент, который передается в метод run() workflow (параметр name)
        id=f"say-hello-workflow-{uuid.uuid4()}",  # ← Уникальный ID для этого экземпляра workflow
        task_queue="my-task-queue",  # ← Очередь задач, в которую будет отправлена задача
    )
    # Вывод результата выполнения workflow
    print("Workflow result:", result)

if __name__ == "__main__":
    # Запуск асинхронной функции main
    asyncio.run(main())
```

**Важно:** Starter может быть запущен один раз или по расписанию, в зависимости от задачи.

---

## Почему нужны две команды для запуска?

Temporal использует архитектуру с разделением ответственности:

### Команда 1: `python worker.py`

- **Запускает Worker**, который выполняет Activities
- **Должен работать постоянно** (слушает очередь задач)
- Может быть запущено несколько worker'ов для масштабирования
- Worker обрабатывает задачи из очереди

### Команда 2: `python starter.py`

- **Запускает Workflow** (отправляет задачу на выполнение)
- Выполняется один раз или по расписанию
- Может быть отдельным сервисом/скриптом
- Starter инициирует выполнение workflow

---

## Как это работает вместе?

### Схема взаимодействия:

```
┌─────────────┐
│  starter.py │  ← Запускает Workflow
└──────┬──────┘
       │
       │ 1. execute_workflow("SayHelloWorkflow", "Temporal")
       ▼
┌─────────────────────┐
│  Temporal Server    │  ← Хранит состояние, координирует
│  (localhost:7233)   │
└──────┬──────────────┘
       │
       │ 2. Отправляет задачу в очередь "my-task-queue"
       ▼
┌─────────────┐
│ worker.py   │  ← Получает задачу из очереди
└──────┬──────┘
       │
       │ 3. Выполняет Activity greet("Temporal")
       ▼
┌─────────────┐
│ activities  │  ← Возвращает "Hello Temporal"
│   .greet()  │
└──────┬──────┘
       │
       │ 4. Результат возвращается обратно
       ▼
┌─────────────┐
│  starter.py │  ← Получает и выводит результат
└─────────────┘
```

### Последовательность выполнения:

1. **Запускаете `python worker.py`**

   - Worker начинает слушать очередь задач
   - Готов к выполнению Activities

2. **Запускаете `python starter.py`**

   - Отправляется запрос на выполнение Workflow
   - Workflow создается на сервере Temporal

3. **Сервер Temporal**

   - Создает экземпляр Workflow
   - Ставит задачу в очередь `"my-task-queue"`

4. **Worker получает задачу**

   - Извлекает задачу из очереди
   - Выполняет Activity `greet("Temporal")`

5. **Activity выполняется**

   - Возвращает результат `"Hello Temporal"`

6. **Workflow завершается**

   - Получает результат от Activity
   - Возвращает результат в Starter

7. **Starter получает результат**
   - Выводит `"Workflow result: Hello Temporal"`

---

## Преимущества такой архитектуры

### ✅ Надежность

- При падении worker'а задача не теряется
- Workflow может быть возобновлен с того же места
- Temporal гарантирует доставку задач

### ✅ Масштабируемость

- Можно запустить несколько worker'ов для обработки задач
- Worker'ы автоматически распределяют нагрузку
- Легко масштабировать горизонтально

### ✅ Разделение ответственности

- **Starter** - запускает процессы
- **Worker** - выполняет работу
- **Temporal Server** - координирует и хранит состояние

### ✅ Отслеживание

- Сервер Temporal хранит полную историю выполнения
- Можно отследить состояние любого workflow
- Легко отлаживать проблемы

### ✅ Отказоустойчивость

- Автоматические повторы при сбоях
- Настраиваемые таймауты
- Изоляция ошибок

---

## Ключевые понятия

### Task Queue (Очередь задач)

- Имя очереди, в которую сервер Temporal отправляет задачи
- Worker слушает конкретную очередь
- Starter указывает очередь при запуске workflow
- В этом проекте используется `"my-task-queue"`

### Workflow ID

- Уникальный идентификатор экземпляра workflow
- Позволяет отслеживать конкретный workflow
- В starter.py генерируется через `uuid.uuid4()`

### Schedule to Close Timeout

- Максимальное время выполнения Activity
- Если Activity не завершится за это время, она будет отменена
- В workflows.py установлен на 10 секунд

---

## Заключение

Эта архитектура позволяет создавать надежные, масштабируемые распределенные приложения. Temporal берет на себя управление состоянием, координацию и гарантии доставки, позволяя разработчикам сосредоточиться на бизнес-логике.

---

## Размещение Temporal в Kubernetes для кейса с Naumen/VMware/AWX

Ниже описана архитектура, ориентированная на self-hosted Temporal в Kubernetes и разбиение монолитного скрипта на несколько сервисов.

### Общая идея

- **Temporal Server** живет отдельно (кластер Temporal в K8S).
- **Temporal Worker-поды** выполняют `workflows.py` и `activities.py`.
- **FastAPI-сервисы** выступают клиентами Temporal (как улучшенный `starter.py`) и/или интеграционным слоем с Naumen.
- Вся бизнес-оркелстрация (последовательность: заявка → создание ВМ → закрытие заявки) живет в Workflow.

### Что делает каждый файл в контексте K8S

#### `workflows.py` — оркестратор процесса заявки

**Суть в твоем кейсе:**

- Описывает полный процесс:
  - прочитать данные заявки (ID, параметры ВМ);
  - вызвать Activity для создания ВМ через AWX/VMware;
  - вызвать Activity для закрытия/обновления заявки в Naumen;
  - вернуть итоговый результат/статус.

**Где находится:**

- В Docker-образе `temporal-worker-vm-provisioning`.
- Этот образ разворачивается как `Deployment` в K8S (например, `deployment/temporal-worker-vm-provisioning`).

#### `activities.py` — интеграции с Naumen, AWX, VMware

**Типичные Activities:**

- `get_ticket_details` / `wait_for_ticket` — работа с Naumen ServiceDesk;
- `create_vm_via_awx` — вызов AWX (ansible-playbook) для создания ВМ;
- `close_ticket` — закрытие заявки в Naumen.

**Где находится:**

- Там же, в образе `temporal-worker-vm-provisioning`, рядом с `workflows.py`.

**Почему именно так:**

- Activities должны быть идемпотентны и перезапускаемы.
- Temporal сам будет ретраить Activities, поэтому удобнее держать их в worker-е, а не в FastAPI-хэндлерах.

#### `worker.py` — процесс, который крутит workflows/activities

**Назначение:**

- Подключается к Temporal Server (адрес, namespace).
- Регистрирует `workflows.py` и `activities.py`.
- Слушает указанную `task_queue`.
- Выполняет поступающие задачи до бесконечности (`await worker.run()`).

**Где находится:**

- В образе `temporal-worker-vm-provisioning`.
- В `Deployment` командой запуска будет что-то вроде:
  - `command: ["python", "worker.py"]`

**Важно:**  
Этот pod **не обязан** быть FastAPI-сервисом и **не принимает** бизнес-запросы по HTTP. Он общается только с Temporal Server.

#### `starter.py` — клиентский код, который запускает Workflow

В прод-архитектуре это не отдельный standalone-скрипт, а логика, встроенная в другие сервисы:

- Вариант 1: **K8S CronJob**:

  - по расписанию обращается в FastAPI «Получатель заявок» (Service A);
  - Service A решает, какие заявки обрабатывать;
  - Service A или сам CronJob использует Temporal SDK, чтобы стартовать Workflow.

- Вариант 2: **Встроить логику старта Workflow прямо в Service A**:
  - Service A получает запрос (от Naumen по webhook или по API);
  - сразу запускает Workflow в Temporal как клиент:

```python
from temporalio.client import Client

client = await Client.connect("temporal-frontend:7233", namespace="vm-provisioning")

await client.start_workflow(
    CreateVmWorkflow.run,         # метод из workflows.py
    ticket_id, vm_params,         # аргументы (ID заявки, параметры ВМ)
    id=f"vm-ticket-{ticket_id}",  # уникальный workflow_id
    task_queue="vm-provisioning-queue",
)
```

**Вывод:**  
`starter.py` — это пример «как быть клиентом Temporal». В реальной K8S-схеме его логика переезжает:

- либо в CronJob,
- либо во FastAPI-сервис (Service A).

### Архитектура сервисов в K8S для твоего кейса

Предположим, у тебя есть:

- **Service A** — FastAPI «Получатель заявок»:

  - общается с Naumen (webhook или опрос API);
  - решает, какие заявки нужно обработать;
  - стартует Workflow в Temporal (логика из `starter.py`).

- **Service B** — FastAPI «Закрыватель заявок» (опционально):

  - если хочешь, чтобы закрытие заявки шло через отдельный микросервис;
  - тогда Activity `close_ticket` из `activities.py` будет дергать HTTP API Service B.

- **Deployment `temporal-worker-vm-provisioning`**:
  - содержит `workflows.py`, `activities.py`, `worker.py`;
  - подключается к Temporal Server, слушает `task_queue="vm-provisioning-queue"`;
  - выполняет создание ВМ (через AWX) и обновление/закрытие заявок.

### Как они общаются между собой

Логический поток:

1. **Naumen** → создаёт/обновляет заявку на создание ВМ.
2. **Service A (FastAPI)**:
   - получает событие/заявку (webhook или по расписанию);
   - формирует параметры Workflow;
   - вызывает Temporal как клиент (код из `starter.py`).
3. **Temporal Server**:
   - создаёт Workflow;
   - ставит задачи в `task_queue="vm-provisioning-queue"`.
4. **`temporal-worker-vm-provisioning` (worker.py)**:
   - вытягивает задачи из `task_queue`;
   - выполняет `CreateVmWorkflow` из `workflows.py`;
   - внутри Workflow вызывает Activities из `activities.py`:
     - `create_vm_via_awx` → AWX/VMware;
     - `close_ticket` → Naumen или Service B.
5. **Результат**:
   - заявка в Naumen закрыта;
   - Workflow завершён и его состояние/история видна в Temporal UI.

### Нужно ли делать `temporal-worker-vm-provisioning` на FastAPI?

Кратко: **нет, не нужно**.

- Worker-под — это фоновой «исполнитель задач» Temporal.
- Общение идёт через Temporal Server и `task_queue`, а не через HTTP между сервисами и worker-ами.
- Для K8S-добротности можно добавить только небольшой HTTP‑healthcheck (liveness/readiness), но бизнес-API там не требуется.

### Итог по ролям

- **`workflows.py` / `activities.py` / `worker.py`**:

  - живут в `temporal-worker-vm-provisioning` (Deployment в K8S);
  - worker слушает очередь и выполняет бизнес-процесс.

- **`starter.py` (как пример)**:

  - логика запуска Workflow переезжает в:
    - CronJob **или**
    - FastAPI‑сервис (Service A), который обращается к Temporal как клиент.

- **FastAPI‑сервисы (Service A/B)**:
  - принимают HTTP-запросы/события;
  - работают с Naumen/пользователями;
  - стартуют и, при необходимости, мониторят Workflows в Temporal.

---

## Добавление действий пользователя в pipeline (Human-in-the-Loop)

В реальных сценариях часто требуется получить данные от пользователя во время выполнения Workflow. Например, в заявке Naumen может отсутствовать IP-адрес сервера, который нужно получить от пользователя перед отправкой в AWX.

### Варианты реализации

#### Вариант 1: Temporal Signal + FastAPI/Django (Рекомендуется) ⭐

**Как работает:**

1. Workflow стартует и приостанавливается на этапе ожидания данных
2. Пользователь открывает веб-интерфейс, видит заявку
3. Пользователь заполняет форму (например, IP-адрес) и нажимает "Продолжить"
4. Веб-приложение отправляет Signal в Workflow
5. Workflow получает Signal и продолжает выполнение

**Преимущества:**

- ✅ Workflow может приостанавливаться и ждать ввода
- ✅ Гибкий UI (можно использовать React/Vue с FastAPI)
- ✅ Можно добавить таймауты ожидания
- ✅ Можно отправлять уведомления пользователю
- ✅ Хорошо интегрируется с существующими FastAPI-сервисами

**Пример реализации:**

```python
# workflows.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class CreateVmWorkflow:
    def __init__(self):
        self.ip_address = None
        self.signal_received = False

    @workflow.signal
    async def provide_ip_address(self, ip: str):
        """Signal для получения IP-адреса от пользователя"""
        self.ip_address = ip
        self.signal_received = True

    @workflow.run
    async def run(self, ticket_id: str, vm_params: dict) -> dict:
        # Шаг 1: Получить данные заявки из Naumen
        ticket_data = await workflow.execute_activity(
            get_ticket_details,
            ticket_id,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Шаг 2: Проверить, есть ли IP-адрес
        if not ticket_data.get("ip_address"):
            # Workflow приостанавливается и ждёт Signal
            # Таймаут ожидания (например, 24 часа)
            await workflow.wait_condition(
                lambda: self.signal_received,
                timeout=timedelta(hours=24)
            )

            if not self.ip_address:
                raise Exception("IP-адрес не был предоставлен в течение 24 часов")

        # Шаг 3: Создать ВМ с полученным IP
        vm_result = await workflow.execute_activity(
            create_vm_via_awx,
            {
                **vm_params,
                "ip_address": self.ip_address or ticket_data.get("ip_address"),
            },
            start_to_close_timeout=timedelta(minutes=30),
        )

        # Шаг 4: Закрыть заявку
        await workflow.execute_activity(
            close_ticket,
            ticket_id,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {"status": "success", "vm_id": vm_result["vm_id"]}
```

```python
# service_a.py (FastAPI сервис)
from fastapi import FastAPI, HTTPException
from temporalio.client import Client

app = FastAPI()

@app.post("/tickets/{ticket_id}/provide-ip")
async def provide_ip_address(ticket_id: str, ip_address: str):
    """Эндпоинт для получения IP-адреса от пользователя"""
    client = await Client.connect("temporal-frontend:7233", namespace="vm-provisioning")

    # Находим workflow по ticket_id
    workflow_id = f"vm-ticket-{ticket_id}"
    workflow_handle = client.get_workflow_handle(workflow_id)

    try:
        # Отправляем Signal в workflow
        await workflow_handle.signal("provide_ip_address", ip_address)
        return {"status": "success", "message": "IP-адрес отправлен в workflow"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tickets/{ticket_id}/status")
async def get_ticket_status(ticket_id: str):
    """Получить статус workflow для заявки"""
    client = await Client.connect("temporal-frontend:7233", namespace="vm-provisioning")
    workflow_id = f"vm-ticket-{ticket_id}"
    workflow_handle = client.get_workflow_handle(workflow_id)

    try:
        description = await workflow_handle.describe()
        return {
            "workflow_id": workflow_id,
            "status": description.status.name,
            "is_running": description.status.name == "RUNNING",
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail="Workflow не найден")
```

**Архитектура:**

```
Пользователь → FastAPI (веб-форма) → Temporal Signal → Workflow продолжается
```

---

#### Вариант 2: Temporal UI + Signal (Без отдельного фронтенда)

**Как работает:**

1. Workflow стартует и ждёт Signal
2. Пользователь открывает Temporal UI (встроенный веб-интерфейс)
3. Находит Workflow по ID (например, `vm-ticket-12345`)
4. Отправляет Signal через UI
5. Workflow продолжает выполнение

**Преимущества:**

- ✅ Не нужен отдельный фронтенд
- ✅ Встроенный UI Temporal
- ✅ Простая настройка

**Недостатки:**

- ❌ Меньше гибкости в UI
- ❌ Нужна настройка доступа к Temporal UI
- ❌ Менее удобно для конечных пользователей

**Когда использовать:**

- Для внутренних процессов
- Когда не нужен кастомный UI
- Для быстрого прототипирования

---

#### Вариант 3: Human Task Pattern через Activity с Polling

**Как работает:**

1. Workflow создаёт "human task" через Activity
2. Activity сохраняет задачу в БД со статусом "pending"
3. Веб-приложение показывает задачи со статусом "pending"
4. Пользователь заполняет форму и отправляет данные
5. Activity периодически проверяет статус задачи (polling)
6. Когда задача "completed", Activity возвращает результат

**Преимущества:**

- ✅ Workflow явно ждёт задачи
- ✅ Можно добавить статусы (pending, in_progress, completed)
- ✅ Подходит для сложных форм с множеством полей
- ✅ Можно показывать список всех pending задач

**Недостатки:**

- ❌ Нужна БД для хранения задач
- ❌ Сложнее реализация
- ❌ Polling может быть неэффективным

**Пример реализации:**

```python
# workflows.py
@workflow.defn
class CreateVmWorkflow:
    @workflow.run
    async def run(self, ticket_id: str, vm_params: dict) -> dict:
        # Создаём human task для получения IP
        ip_address = await workflow.execute_activity(
            wait_for_user_input,
            {
                "ticket_id": ticket_id,
                "field_name": "ip_address",
                "field_label": "IP-адрес сервера",
            },
            start_to_close_timeout=timedelta(hours=24),
        )

        # Продолжаем с полученным IP
        # ...
```

```python
# activities.py
@activity.defn
async def wait_for_user_input(task_data: dict) -> str:
    """Activity, которая ждёт ввода пользователя"""
    task_id = f"task-{task_data['ticket_id']}-{task_data['field_name']}"

    # Сохраняем задачу в БД
    await save_human_task(task_id, task_data, status="pending")

    # Polling: проверяем статус каждые 5 секунд
    while True:
        task = await get_human_task(task_id)
        if task["status"] == "completed":
            return task["value"]
        await asyncio.sleep(5)
```

---

#### Вариант 4: Django/FastAPI + кнопка запуска (Простой вариант)

**Как работает:**

1. Django/FastAPI показывает форму с заявкой
2. Пользователь заполняет IP-адрес и нажимает "Создать ВМ"
3. Приложение стартует Workflow с уже заполненным IP
4. Workflow сразу идёт в AWX без остановок

**Преимущества:**

- ✅ Простота реализации
- ✅ Полный контроль над UI
- ✅ Можно добавить валидацию перед запуском
- ✅ Нет сложностей с приостановкой workflow

**Недостатки:**

- ❌ Workflow стартует только после ввода IP
- ❌ Нет приостановки/возобновления workflow
- ❌ Если пользователь закроет страницу, нужно перезапускать

**Пример реализации:**

```python
# Django view
from temporalio.client import Client

def create_vm_view(request, ticket_id):
    if request.method == "POST":
        form = VmCreationForm(request.POST)
        if form.is_valid():
            ip_address = form.cleaned_data['ip_address']

            # Стартуем workflow с уже заполненным IP
            client = await Client.connect("temporal-frontend:7233")
            result = await client.execute_workflow(
                CreateVmWorkflow.run,
                ticket_id,
                {
                    "ip_address": ip_address,
                    "vm_params": form.cleaned_data,
                },
                id=f"vm-ticket-{ticket_id}",
                task_queue="vm-provisioning-queue",
            )

            return redirect('vm_status', ticket_id=ticket_id)
    else:
        # Показываем форму
        form = VmCreationForm()
    return render(request, 'create_vm.html', {'form': form})
```

---

### Сравнение вариантов

| Критерий                     | Вариант 1 (Signal) | Вариант 2 (Temporal UI) | Вариант 3 (Human Task) | Вариант 4 (Django) |
| ---------------------------- | ------------------ | ----------------------- | ---------------------- | ------------------ |
| **Гибкость UI**              | Высокая            | Низкая                  | Высокая                | Высокая            |
| **Приостановка Workflow**    | ✅ Да              | ✅ Да                   | ✅ Да                  | ❌ Нет             |
| **Сложность реализации**     | Средняя            | Низкая                  | Высокая                | Низкая             |
| **Таймауты ожидания**        | ✅ Да              | ✅ Да                   | ✅ Да                  | ❌ Нет             |
| **Интеграция с FastAPI**     | ✅ Легко           | Не требуется            | Средне                 | ✅ Легко           |
| **Уведомления пользователю** | ✅ Да              | ❌ Нет                  | ✅ Да                  | ✅ Да              |
| **Множественные поля**       | ✅ Да              | ❌ Сложно               | ✅ Да                  | ✅ Да              |

### Рекомендация

**Для твоего кейса (Naumen + VMware + AWX):**

Используй **Вариант 1 (Signal через FastAPI)**, потому что:

- ✅ Workflow может приостанавливаться и ждать ввода пользователя
- ✅ Можно добавить таймауты (например, если пользователь не ответил за 24 часа)
- ✅ Гибкий UI (можно использовать React/Vue с FastAPI)
- ✅ Можно отправлять уведомления пользователю о необходимости ввода
- ✅ Хорошо интегрируется с существующими FastAPI-сервисами

**Альтернатива:** Если нужен максимально простой вариант без приостановки workflow — используй **Вариант 4 (Django/FastAPI с кнопкой)**.

### Архитектура с Signal в K8S

```
┌─────────────────────┐
│  Service A (FastAPI)│  ← Веб-форма для ввода IP
│  /tickets/{id}/form │
└──────────┬──────────┘
           │
           │ HTTP POST /provide-ip
           │
           ▼
┌─────────────────────┐
│  Temporal Client    │  ← Отправляет Signal
│  (в Service A)      │
└──────────┬──────────┘
           │
           │ Signal: provide_ip_address
           ▼
┌─────────────────────┐
│  Temporal Server    │
└──────────┬──────────┘
           │
           │ Доставляет Signal в Workflow
           ▼
┌─────────────────────┐
│  temporal-worker     │  ← Workflow получает Signal
│  (workflows.py)      │     и продолжает выполнение
└─────────────────────┘
```

### Дополнительные возможности

1. **Уведомления пользователю:**

   - Отправлять email/SMS когда workflow ждёт ввода
   - Показывать в UI список заявок, ожидающих ввода

2. **Валидация:**

   - Проверять IP-адрес на корректность перед отправкой Signal
   - Проверять доступность IP-адреса в сети

3. **Таймауты и эскалация:**

   - Если пользователь не ответил за N часов, отправлять уведомление менеджеру
   - Автоматически отменять workflow при превышении таймаута

4. **История изменений:**
   - Логировать, кто и когда предоставил IP-адрес
   - Хранить историю всех изменений в заявке
