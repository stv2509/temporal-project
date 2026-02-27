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
