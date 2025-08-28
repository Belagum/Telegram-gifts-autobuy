Вот обновлённый **README.md** под текущую структуру и функциональность проекта.

---

# GiftBuyer

Небольшая веб-панель для работы с Telegram-аккаунтами (Pyrogram): добавление аккаунтов, хранение сессий, просмотр баланса звёзд, просмотр и авто-обновление **подарков** c предпросмотром **.tgs (Lottie)**.
Стек: **Flask + SQLAlchemy + Pyrogram** (backend) и **React + Vite** (frontend).

---

## Возможности

* Регистрация/логин в панели (httpOnly cookie-токен, 7 дней).
* Несколько **API-профилей** (api\_id/api\_hash) на пользователя: создать/переименовать/удалить.
* Добавление Telegram-аккаунта по телефону (код из TG, при необходимости — 2FA пароль).
* Просмотр имени/username, премиума и баланса звёзд.
* Ручное обновление аккаунта со стримом стадий (**NDJSON**).
* **Подарки (Gifts):**

  * список доступных подарков, ленивая подгрузка карточек;
  * кнопка «Обновить» и фоновое авто-обновление;
  * **SSE-стрим** обновлений от сервера;
  * предпросмотр .tgs (Lottie) с кешированием на сервере.
* **Настройки пользователя:** хранение **Bot token** (нужен для скачивания превью .tgs).
  Если токена нет, на странице «Подарки» отображается карточка с предложением открыть «Настройки».
* Аккуратные UI-мелочи: тумблер-переключатель, центрированное всплывающее окно (для /gifts и /settings).

---

## Структура проекта

```
GiftBuyer/
  backend/
    app.py
    auth.py
    db.py
    logger.py
    models.py
    requirements.txt
    routes/
      __init__.py
      auth_routes.py
      account_routes.py
      misc_routes.py
      gifts.py          # API подарков + Lottie-кеш + SSE
      settings.py       # API настроек пользователя (bot token)
    services/
      __init__.py
      accounts_service.py
      gifts_service.py  # воркер подарков, SSE-шина, merge, hash и т.д.
      settings_service.py
    sessions/           # .session файлы Pyrogram  (gitignored)
    instance/
      gifts_cache/      # кеш .tgs (gzip) по file_id / unique_id (gitignored)
    migrate_app_db.py   # миграция БД (создаёт user_settings)
  frontend/
    index.html
    src/
      api.js            # обёртка fetch + 401-хэндлер
      App.jsx
      auth.js
      main.jsx
      notify.js
      styles.css
      utils/
        openCentered.js
      ui/
        ModalStack.jsx
      pages/
        Dashboard.jsx
        GiftsPage.jsx
        SettingsPage.jsx
        Login.jsx
        Register.jsx
      components/
        AccountList.jsx
        AddApiModal.jsx
        AddAccountModal.jsx
        SelectApiProfileModal.jsx
        ConfirmModal.jsx
    package.json
    package-lock.json
```

> Папки `backend/sessions/`, `backend/instance/` (и её `gifts_cache/`), а также временные файлы данных подарков игнорируются в Git.

---

## Установка и запуск

### 1) Backend

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

**(один раз) миграция БД** — создаём таблицу `user_settings`:

```bash
python migrate_app_db.py
# по умолчанию меняет backend/app.db, если вы используете другой путь — укажите его:
# python migrate_app_db.py path/to/app.db
```

Запуск:

```bash
python -m backend.app
# слушает http://localhost:5000
```

Переменные окружения (необязательно):

* `SECRET_KEY` — секрет Flask.
* `GIFTS_DIR` — путь к JSON со снимком подарков (по умолчанию `gifts_data` в корне backend).
* `GIFTS_CACHE_DIR` — каталог кеша .tgs (по умолчанию `backend/instance/gifts_cache`).

### 2) Frontend

```bash
cd frontend
npm i
npm run dev
# http://localhost:5173
```

Для дев-режима прокси `/api` → `http://localhost:5000` задаётся в `vite.config.js` (если нужен).

---

## Быстрый старт

1. Открой `http://localhost:5173`, зарегистрируйся/войдите.
2. Создай **API-профиль** (api\_id/api\_hash из my.telegram.org).
3. Добавь аккаунт (телефон → код → при необходимости 2FA пароль).
4. Открой **Подарки**:

   * кнопка «Обновить» подтянет список;
   * включи «Автообновление», чтобы воркер периодически актуализировал данные.
5. Для превью .tgs зайди в **Настройки** и укажи **Bot token**.
   Токен используется только для скачивания и кеширования превью (Lottie JSON извлекается из `.tgs` на сервере и кешируется в `instance/gifts_cache`).

---

## Как устроены «Подарки»

* `services/gifts_service.py`

  * воркер на пользователя: собирает подарки с его аккаунтов, мёржит по `id`, пишет снимок JSON;
  * считает компактный `hash` и шлёт события в `gifts_event_bus` только при изменениях;
  * единичное обновление `refresh_once()` отдаёт свежие данные и пушит событие.
* `routes/gifts.py`

  * `GET /api/gifts` — текущий снимок;
  * `POST /api/gifts/refresh` — ручное обновление (или NDJSON-стрим по `Accept`);
  * `GET /api/gifts/sticker.lottie?file_id=...&uniq=...` — отдаёт Lottie JSON из кешированного `.tgs`
    (если кеша нет — скачивает через **Bot token** текущего пользователя; при отсутствии токена возвращает `409 {"error":"no_bot_token"}`);
  * `GET /api/gifts/stream` — SSE-стрим событий изменений.
* Кеш .tgs шардуется по SHA-1(file\_id/uniq), лежит в `instance/gifts_cache/`.

---

## Страница «Настройки»

* `SettingsPage.jsx` — простая форма с одним полем **Bot token** (type=password) и кнопкой «Сохранить» (фикс внизу, на всю ширину).
  После сохранения окно закрывается/фокус уходит.
* `routes/settings.py` / `services/settings_service.py` — получение/сохранение настроек в таблицу `user_settings`.

---

## Сборка продакшена

```bash
# фронт
cd frontend
npm ci
npm run build   # dist/

# бэкенд запускается любым WSGI/ASGI сервером, статику dist/ можно раздавать через Nginx/Caddy,
# а /api проксировать на backend.
```

---

## Полезно знать

* Токен аутентификации панели — только в httpOnly-cookie, фронт его не видит.
* Сессии Pyrogram хранятся в `backend/sessions/user_<id>/...` (gitignore).
* Если нет ни одного аккаунта — кнопки «Подарки» (в Dashboard) и элементы автообновления на Gifts скрываются.
* Предпросмотры .tgs кешируются навсегда (immutable Cache-Control); ключ — `file_unique_id`, при его отсутствии — `file_id`.

---

## Троблшутинг

* **Нет предпросмотров .tgs:** убедись, что в «Настройках» сохранён валидный Bot token.
  Запрос `/api/gifts/sticker.lottie` без токена вернёт `409 {"error":"no_bot_token"}`.
* **SQLite миграция не сработала:** запусти `python backend/migrate_app_db.py` и проверь, что файл `backend/app.db` доступен на запись.

---

## Лицензия
Apache-2.0 © 2025 Vova Orig. См. файл LICENSE. Доп. уведомления — в NOTICE.