# Локальная статика (офлайн)

Все ресурсы скачаны для работы **без интернета** на сервере.

| Путь | Описание |
|------|----------|
| `css/bootstrap.min.css` | Bootstrap 5.3.3 |
| `js/bootstrap.bundle.min.js` | Bootstrap JS + Popper |
| `css/bootstrap-icons.min.css` | Bootstrap Icons 1.11.3 |
| `css/fonts/` | Шрифты Bootstrap Icons (woff2, woff) |
| `css/all.min.css` | Font Awesome 6.5.1 (all) |
| `webfonts/` | Шрифты Font Awesome (fa-solid-900, fa-regular-400, fa-brands-400) |

В шаблонах подключать через `{% load static %}` и `{% static 'css/...' %}`.

---

## Откуда и как скачивать

**Источники (CDN):** [jsDelivr](https://www.jsdelivr.com/) — `https://cdn.jsdelivr.net/npm/<пакет>@<версия>/...`

Выполнять команды из папки **`backend/static`** (где лежит этот README). Создать папки: `mkdir -p css/fonts webfonts` (если ещё нет).

### Bootstrap 5

- Документация: https://getbootstrap.com/
- Скачать:
  ```bash
  curl -sL -o css/bootstrap.min.css "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
  curl -sL -o js/bootstrap.bundle.min.js "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
  ```

### Bootstrap Icons

- Документация: https://icons.getbootstrap.com/
- CSS и шрифты (путь в CSS — `fonts/`, значит шрифты кладём в `css/fonts/`):
  ```bash
  curl -sL -o css/bootstrap-icons.min.css "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
  curl -sL -o css/fonts/bootstrap-icons.woff2 "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2"
  curl -sL -o css/fonts/bootstrap-icons.woff "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff"
  ```

### Font Awesome 6 (Free)

- Документация: https://fontawesome.com/docs
- CSS и webfonts (в CSS путь `../webfonts/`, значит папка `webfonts/` рядом с `css/`):
  ```bash
  curl -sL -o css/all.min.css "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/css/all.min.css"
  curl -sL -o webfonts/fa-solid-900.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-solid-900.woff2"
  curl -sL -o webfonts/fa-regular-400.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-regular-400.woff2"
  curl -sL -o webfonts/fa-brands-400.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-brands-400.woff2"
  ```

**Вариант одной командой** (из `backend/static`, bash/git-bash):

```bash
mkdir -p css/fonts webfonts
curl -sL -o css/bootstrap.min.css "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
curl -sL -o js/bootstrap.bundle.min.js "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
curl -sL -o css/bootstrap-icons.min.css "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
curl -sL -o css/fonts/bootstrap-icons.woff2 "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2"
curl -sL -o css/fonts/bootstrap-icons.woff "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff"
curl -sL -o css/all.min.css "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/css/all.min.css"
curl -sL -o webfonts/fa-solid-900.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-solid-900.woff2"
curl -sL -o webfonts/fa-regular-400.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-regular-400.woff2"
curl -sL -o webfonts/fa-brands-400.woff2 "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-brands-400.woff2"
```

После скачивания папку `static/` можно переносить на сервер без интернета. При смене версий подставьте нужные номера в URL (например, `bootstrap@5.4.0`, `bootstrap-icons@1.11.4`).
