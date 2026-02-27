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
