# Temporal Worker (K8s access check + AWX)

## Структура каталога `worker/`

```
worker/
  worker.py              # точка входа (python worker/worker.py из корня репо)
  runner.py              # load_dotenv, Client.connect, Worker(...)
  registry.py            # реестр доменов: очередь, workflows, activities
  requirements.txt
  shared/
    backend_api.py       # URL/Auth для DRF API
    awx_profiles.py      # AWX test/prod по AWX_ENV
  domains/
    k8s_access/
      activities.py      # get_request_data, AWX, update_request_status
      workflows.py       # K8sAccessCheckWorkflow
```

Код workflow/activity лежит **только** под `domains/<домен>/`. В корне `worker/` нет `activities.py` / `workflows.py`.

---

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
| `WORKER_DOMAIN` | Домен worker из реестра (`k8s_access`) | `k8s_access` |
| `TEMPORAL_TASK_QUEUE_K8S_ACCESS` | Очередь для домена `k8s_access` | `awx-task-queue` |
| `AWX_ENV` | Контур AWX (`test`/`prod`; `dev` маппим на test) | `test` |
| `BACKEND_API_URL` | URL Django API | `http://localhost:8000` |
| `BACKEND_API_USER` | Basic Auth для API | — |
| `BACKEND_API_PASSWORD` | Basic Auth для API | — |
| `AWX_URL_TEST` | URL AWX test | — |
| `AWX_USERNAME_TEST` | Basic Auth AWX test | — |
| `AWX_PASSWORD_TEST` | Basic Auth AWX test | — |
| `AWX_URL_PROD` | URL AWX prod | — |
| `AWX_USERNAME_PROD` | Basic Auth AWX prod | — |
| `AWX_PASSWORD_PROD` | Basic Auth AWX prod | — |

Без корректных `AWX_*` для выбранного `AWX_ENV`, workflow выполнит get_request_data и
update_request_status, а на launch_awx_job упадёт и переведёт заявку в статус `failed`.

## Реестр доменов

- Реестр находится в `worker/registry.py`.
- Текущий домен: `k8s_access`.
- `vm_create` добавлен как закомментированная заготовка в реестре.
