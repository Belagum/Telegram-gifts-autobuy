# GiftBuyer

Веб-панель для работы с Telegram-аккаунтами на базе **Flask + SQLAlchemy + Pyrogram** (backend) и **React + Vite** (frontend). Позволяет добавлять аккаунты, хранить сессии, смотреть баланс звёзд, управлять **подарками** c предпросмотром **.tgs (Lottie)**, а также вести список **каналов** с простыми фильтрами.

---

## Возможности

* Регистрация/логин (httpOnly cookie, 7 дней).
* Несколько API-профилей (api\_id/api\_hash) на пользователя.
* Добавление Telegram-аккаунтов по телефону (код, при необходимости — 2FA).
* Просмотр имени/username, статуса Premium, баланса звёзд.
* Ручное обновление данных аккаунтов со стримом стадий (NDJSON).
* **Подарки (Gifts):** список, ручное/фоновое обновление, SSE-стрим, предпросмотр .tgs (кэш Lottie на сервере).
* **Каналы:** добавление по `channel_id` (формат `-100…`), проверка членства, хранение названия и числовых диапазонов (цена/саплай), редактирование и удаление.
* Аккуратный UI (модалки, тосты, проверка вводов).

---

## Стек

* **Backend:** Python 3.11+, Flask, SQLAlchemy, Pyrogram.
* **Frontend:** React, Vite.

---

## Структура

```
GiftBuyer/
  backend/
    app.py
    auth.py
    db.py
    logger.py
    models.py
    requirements.txt
    migrate_app_db.py
    sessions/                 # .session (gitignored)
    instance/
      gifts_cache/            # .tgs gzip-кэш (gitignored)
    routes/
      __init__.py
      auth.py
      account.py
      misc.py
      gifts.py                # API подарков + Lottie-кэш + SSE
      settings.py             # API настроек пользователя (Bot token)
      channels.py             # API каналов (CRUD)
    services/
      __init__.py
      accounts_service.py
      gifts_service.py        # воркер подарков, SSE-шина
      settings_service.py
      notify_gifts_service.py
      session_locks_service.py
      tg_clients_service.py   # единый Pyrogram-клиент + tg_call/tg_shutdown
      channels_service.py     # логика каналов (нормализация id, probe, валидация)
      pyro_login.py           # добавление аккаунтов (в т.ч. Premium)
  frontend/
    index.html
    package.json
    package-lock.json
    src/
      api.js                  # fetch-обёртка + 401
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
        EditChannelModal.jsx
```

> `backend/sessions/`, `backend/instance/` и её содержимое игнорируются в Git.

---

## Установка и запуск

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python -m backend.app      # http://localhost:5000
```

Переменные окружения (необязательно):

* `SECRET_KEY` — секрет Flask.
* `GIFTS_DIR` — каталог с данными подарков (по умолчанию `gifts_data`).
* `GIFTS_CACHE_DIR` — кэш .tgs (по умолчанию `backend/instance/gifts_cache`).

### Frontend

```bash
cd frontend
npm i
npm run dev    # http://localhost:5173
```

При необходимости настройте прокси `/api` → `http://localhost:5000` во `vite.config.js`.

---

## Быстрый старт

1. Откройте `http://localhost:5173`, зарегистрируйтесь/войдите.
2. Создайте API-профиль (api\_id/api\_hash).
3. Добавьте Telegram-аккаунт (телефон → код → при необходимости пароль).
4. Зайдите на «Подарки» для просмотра/обновления и предпросмотра .tgs.
5. В «Настройках» сохраните Bot token, чтобы сервер мог скачивать превью .tgs.
6. В «Каналах» добавляйте `channel_id` вида `-100…`, задавайте диапазоны и название.

---

## Сборка продакшена

```bash
# фронтенд
cd frontend
npm ci
npm run build   # dist/

# бэкенд запускается любым WSGI/ASGI; статику dist/ можно раздавать веб-сервером,
# /api проксируется на backend.
```

---

## Примечания

* Токен аутентификации хранится в httpOnly-cookie.
* Сессии Pyrogram лежат в `backend/sessions/user_<id>/…`.
* Кэш Lottie извлекается из `.tgs` и хранится на сервере; ключи стабильные для повторного использования.
* Валидация числовых диапазонов на фронте и бэке: принимаются только целые, допускается `null`, выполняется `min ≤ max`.

---

## Лицензия

Apache-2.0 © 2025 Vova Orig. См. LICENSE и NOTICE.
