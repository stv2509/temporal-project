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

### Temporal

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TEMPORAL_ADDRESS` | `host:port` фронтенда Temporal. В K8s с **temporal-worker-controller** задаётся оператором в Pod (приоритетнее `TEMPORAL_HOST`). | — |
| `TEMPORAL_HOST` | Адрес Temporal, если `TEMPORAL_ADDRESS` не задан (локальный `.env`). | `localhost:7233` |
| `TEMPORAL_NAMESPACE` | Namespace на стороне Temporal. В K8s обычно совпадает с `spec.workerOptions.temporalNamespace` у `TemporalWorkerDeployment` и подставляется контроллером. | `default` |
| `TEMPORAL_DEPLOYMENT_NAME` | Имя Worker Deployment в Temporal (генерируется контроллером из CR + namespace). | — |
| `TEMPORAL_WORKER_BUILD_ID` | Build ID версии воркера (контроллер: из образа и хеша pod template). | — |
| `WORKER_DOMAIN` | Домен worker из реестра (`k8s_access`) | `k8s_access` |
| `TEMPORAL_TASK_QUEUE_K8S_ACCESS` | Очередь для домена `k8s_access` | `awx-task-queue` |

Если заданы **обе** `TEMPORAL_DEPLOYMENT_NAME` и `TEMPORAL_WORKER_BUILD_ID`, `runner.py` включает **Worker Versioning** (`WorkerDeploymentConfig` в SDK) — воркер регистрируется как версия Worker Deployment (в т.ч. для UI). Локально без контроллера эти переменные можно не задавать или задать обе вручную для экспериментов.

Подробности про манифесты и namespace — в разделе [Kubernetes](#kubernetes).

### AWX, backend, TLS

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `AWX_ENV` | Контур AWX (`test`/`prod`; `dev` маппим на test) | `test` |
| `CA_BUNDLE_PATH` | Проверка TLS для httpx: путь к PEM, `true` / `false` | — |
| `BACKEND_API_URL` | URL Django API | `http://localhost:8000` |
| `BACKEND_API_USER` | Basic Auth для API | — |
| `BACKEND_API_PASSWORD` | Basic Auth для API | — |
| `AWX_URL_TEST` | URL AWX test | — |
| `AWX_USERNAME_TEST` | Basic Auth AWX test | — |
| `AWX_PASSWORD_TEST` | Basic Auth AWX test | — |
| `AWX_URL_PROD` | URL AWX prod | — |
| `AWX_USERNAME_PROD` | Basic Auth AWX prod | — |
| `AWX_PASSWORD_PROD` | Basic Auth AWX prod | — |

Пароли AWX можно хранить зашифрованными (`AWX_PASSWORD_ENCRYPTED_*` + `ENCRYPTION_KEY_*`) — см. `.env.example` и `worker/shared/awx_profiles.py`.

Без корректных `AWX_*` для выбранного `AWX_ENV`, workflow выполнит get_request_data и
update_request_status, а на launch_awx_job упадёт и переведёт заявку в статус `failed`.

## Kubernetes

Воркер в кластере рассчитан на **[temporal-worker-controller](https://github.com/temporalio/temporal-worker-controller)** и CR **`TemporalWorkerDeployment`** (`temporal.io/v1alpha1`), а не на обычный `Deployment` приложения.

### Что установить

1. CRD: чарт **[temporal-worker-controller-crds](https://github.com/temporalio/temporal-worker-controller/tree/main/helm/temporal-worker-controller-crds)** (без него `kubectl apply` для `TemporalConnection` / `TemporalWorkerDeployment` не сработает).
2. Оператор: чарт **temporal-worker-controller** (см. [документацию](https://docs.temporal.io/production-deployment/worker-deployments/kubernetes-controller)).
3. В целевом namespace — манифесты из `k8s/` этого репозитория (ниже).

### Манифесты в `k8s/`

| Файл | Назначение |
|------|------------|
| `worker-k8s-access-temporalconnection.yaml` | **`TemporalConnection`**: `host:port` фронтенда Temporal. Имя ресурса должно совпадать с `spec.workerOptions.connectionRef.name` в `TemporalWorkerDeployment`. |
| `worker-k8s-access-temporalworkerdeployment.yaml` | **`TemporalWorkerDeployment`**: образ воркера, `replicas`, `rollout`, обязательные `sunset` и `workerOptions` (в т.ч. `temporalNamespace`, ссылка на connection). |
| `worker-k8s-access-configmap.yaml` | Не-секретный env приложения (`WORKER_DOMAIN`, очередь, AWX, backend URL и т.д.). |

**Namespace:** `TemporalConnection` и `TemporalWorkerDeployment` — **namespaced** CR. Создавайте их в **одном и том же** namespace, где будут Pod’ы воркера: у `connectionRef` указывается **только имя** `TemporalConnection`, без поля namespace (ссылка всегда в текущем namespace).

**Порядок применения:** сначала `TemporalConnection`, затем `TemporalWorkerDeployment` и `ConfigMap` (плюс `Secret` для паролей AWX/backend — не храните их в `ConfigMap`).

Пример:

```bash
kubectl apply -f k8s/worker-k8s-access-temporalconnection.yaml -n <namespace>
kubectl apply -f k8s/worker-k8s-access-configmap.yaml -n <namespace>
kubectl apply -f k8s/worker-k8s-access-temporalworkerdeployment.yaml -n <namespace>
```

Для mTLS или API-ключа к Temporal в `TemporalConnection` используйте поля **`mutualTLSSecretRef`** / **`apiKeySecretRef`** по [CRD `temporalconnections.temporal.io`](https://github.com/temporalio/temporal-worker-controller/blob/main/helm/temporal-worker-controller-crds/templates/temporal.io_temporalconnections.yaml) (задать можно только одно из двух).

### Переменные окружения в Pod

Оператор подставляет в контейнер воркера, среди прочего: `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_DEPLOYMENT_NAME`, `TEMPORAL_WORKER_BUILD_ID`. Их **не дублируйте** в `ConfigMap`, если ими управляет контроллер (см. `k8s/worker-k8s-access-configmap.yaml`).

## Реестр доменов

- Реестр находится в `worker/registry.py`.
- Текущий домен: `k8s_access`.
- `vm_create` добавлен как закомментированная заготовка в реестре.
