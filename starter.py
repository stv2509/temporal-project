import asyncio
import uuid
from temporalio.client import Client

async def main():
    # Подключение к серверу Temporal (по умолчанию localhost:7233)
    client = await Client.connect("localhost:7233")
    
    # Запуск workflow и ожидание результата
    result = await client.execute_workflow(
        "SayHelloWorkflow",        # ← Имя workflow класса для выполнения
        "Василий",                # ← Аргумент, который передается в метод run() workflow (параметр name)
        id=f"say-hello-workflow-{uuid.uuid4()}",  # ← Уникальный ID для этого экземпляра workflow
        task_queue="my-task-queue",  # ← Очередь задач, в которую будет отправлена задача
    )
    # Вывод результата выполнения workflow
    print("Workflow result:", result)

if __name__ == "__main__":
    # Запуск асинхронной функции main
    asyncio.run(main())
