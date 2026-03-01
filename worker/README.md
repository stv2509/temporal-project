# Temporal Worker (K8s access check + AWX)

Запуск из корня репозитория:

```bash
pip install -r worker/requirements.txt
python worker/worker.py
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TEMPORAL_HOST` | Адрес Temporal | `localhost:7233` |
| `TEMPORAL_NAMESPACE` | Namespace | `default` |
| `TEMPORAL_TASK_QUEUE` | Очередь задач | `awx-task-queue` |
| `BACKEND_API_URL` | URL Django API | `http://localhost:8000` |
| `BACKEND_API_USER` | Basic Auth для API | — |
| `BACKEND_API_PASSWORD` | Basic Auth для API | — |
| `AWX_URL` | URL AWX (например `https://awx.example.com`) | — |
| `AWX_USERNAME` | Basic Auth AWX | — |
| `AWX_PASSWORD` | Basic Auth AWX | — |

Без `AWX_*` workflow выполнит get_request_data и update_request_status, а на launch_awx_job упадёт и переведёт заявку в статус `failed`.
