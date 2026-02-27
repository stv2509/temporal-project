from temporalio import activity

# Декоратор, который помечает функцию как Activity
# Activity - это единица работы, которая выполняется на worker'е
@activity.defn
async def greet(name: str) -> str:
    # name - параметр, который передается из workflow
    # Возвращает приветствие с переданным именем
    return f"Hello {name}"
