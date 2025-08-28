# GiftBuyer

Небольшая веб-панель для работы с Telegram-аккаунтами (через Pyrogram): добавление аккаунтов по телефону, хранение сессий, просмотр имени/username и баланса звёзд.
Стек: **Flask + SQLAlchemy + Pyrogram** (backend) и **React + Vite** (frontend).

---

## Что умеет

* Регистрация/логин в панели (cookie-токен, 7 дней).
* Несколько **API-профилей** (api\_id/api\_hash) на пользователя: создать, переименовать, удалить (если не используется).
* Добавление Telegram-аккаунта по телефону (код из TG, при необходимости — 2FA пароль).
* Чтение профиля/username и баланса звёзд.
* Фоновое «обновление по давности» и ручное обновление аккаунта (стрим событий **NDJSON**).
* Аккуратные анимации перестановки карточек в списке аккаунтов.

---

## Структура проекта

```
GiftBuyer/
  backend/
    app.py                  # создание Flask-приложения
    auth.py                 # хеширование паролей, выдача токена, @auth_required
    db.py                   # engine, scoped_session, init_db()
    logger.py               # loguru + интеграция с Flask
    models.py               # User, SessionToken, ApiProfile, Account (+ token_default_exp)
    pyro_login.py           # менеджер логина через Pyrogram (код/2FA), создание Account
    services/
      accounts_service.py   # фоновые обновления/стрим, чтение/очистка сессий
    routes/
      auth_routes.py        # /api/auth/* (register, login, logout)
      account_routes.py     # /api/* (me, accounts, refresh, apiprofiles, login flow)
      misc_routes.py        # /api/health
    sessions/               # сюда кладутся .session файлы Pyrogram
    requirements.txt
    __init__.py

  frontend/
    index.html
    src/
      api.js                # единая обёртка fetch (credentials=include, 401→событие)
      App.jsx               # защита маршрутов + реакция на 401
      main.jsx              # роутер, тосты, ModalProvider
      styles.css
      notify.js             # один «умный» тост: pending/success/error
      ui/
        ModalStack.jsx      # стек модалок (см. ниже)
      pages/
        Login.jsx           # вход (кнопка со спиннером)
        Register.jsx        # регистрация (кнопка со спиннером)
        Dashboard.jsx       # список аккаунтов + модалки добавления
      components/
        AccountList.jsx           # сетка карточек (+ анимация перестановок)
        AddApiModal.jsx           # создание API-профиля
        SelectApiProfileModal.jsx # выбор/переименование/удаление API-профиля
        AddAccountModal.jsx       # вход по телефону (код/2FA), отмена
        ConfirmModal.jsx          # подтверждение удаления
    package.json
    vite.config.js (обычно — прокси /api → http://localhost:5000)
```

> **Сессии Pyrogram** находятся в `backend/sessions/user_<user_id>/<phone>.session`. Папка добавлена в `.gitignore`.

---

## Как это работает (коротко)

* **Аутентификация панели**
  `POST /api/auth/login` проверяет username/password и **выдаёт токен** (один активный на пользователя). Токен кладётся в httpOnly-cookie `auth_token` на 7 дней. Все приватные эндпоинты помечены `@auth_required` — читаем токен из заголовка `Authorization: Bearer` **или** из cookie, валидируем по БД.

* **API-профили**
  Пользователь создаёт профиль (`api_id`, `api_hash`, опционально `name`). Внутри пользователя запрещены дубликаты по `api_id` и по `api_hash`. Профиль нельзя удалить, если он привязан к аккаунтам.

* **Добавление аккаунта**

  1. Отправляем код в Telegram (`/api/auth/send_code`).
  2. Подтверждаем код (`/api/auth/confirm_code`), при 2FA — пароль (`/api/auth/confirm_password`).
  3. Создаётся/обновляется запись `Account`, `.session` сохраняется в `backend/sessions/...`.

* **Обновление аккаунтов**

  * Фоновое: при запросе `/api/accounts?wait=1` сервер, если данные устарели, запускает обновление и либо ждёт до 25 сек, либо отвечает `{"state":"refreshing"}`.
  * Ручное: `/api/account/<id>/refresh` — стрим `application/x-ndjson` со стадиями/ошибками и финальным `{"done":true,"account":...}`. При невалидной сессии аккаунт удаляется.

* **Список аккаунтов**
  Клиент аккуратно сортирует по `last_checked_at` и анимирует перестановки (карточка «поднимается» вверх, остальные каскадно смещаются).

---

## Первый запуск (локально)

### 1) Backend

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
# (опционально) свой секрет:
# set SECRET_KEY=your-secret   # Windows CMD
# export SECRET_KEY=your-secret # bash/zsh

# Запуск как модуля (важно для импортов пакета backend)
python -m backend.app
# слушает http://localhost:5000
```

### 2) Frontend

```bash
cd frontend
npm i
npm run dev
# открой http://localhost:5173
```

> Если фронт и бэкенд на разных порталах в dev, в `vite.config.js` настрой прокси:
>
> ```js
> export default defineConfig({
>   server: { proxy: { '/api': 'http://localhost:5000' } }
> })
> ```

### 3) Проверка

1. Открой `http://localhost:5173`, зарегистрируйся/войдите.
2. Добавь **API-профиль** (api\_id/api\_hash из my.telegram.org).
3. Нажми «Добавить аккаунт», введи телефон → код → (если нужно) 2FA пароль.
4. Обновляй аккаунт кнопкой «Обновить» — смотри стрим стадий и итоговые данные.

---

## Коротко про продакшен

* Собери фронт: `cd frontend && npm ci && npm run build` (появится `dist/`).
* Подними backend (gunicorn/waitress/uvicorn — на ваш вкус).
* Любой reverse-proxy (Nginx/Caddy) раздаёт статику из `frontend/dist` и проксирует `/api` → backend.

---

## Зачем и как устроен стек модалок

**Задача:** открывать вложенные модалки (например, «Удалить?» поверх «Выбор API профиля»), чтобы:

* по **Esc** закрывалась **только верхняя** модалка,
* клики по фону не «пробивали» к нижней,
* базовая модалка **не исчезала**, а временно скрывалась.

**Реализация (`ui/ModalStack.jsx`):**

* `ModalProvider` хранит **стек** `{id, onClose}` и вешает **один** обработчик `Esc` на документ.
* `useModal(onClose)` регистрирует модалку и отдаёт:

  * `isTop` — текущая верхняя,
  * `hidden` — надо ли спрятать модалку (когда поверх открыта другая),
  * `suspendAllExceptSelf()` / `resumeAll()` — временно «заглушить» остальные.
* `ConfirmModal` рендерится через **portal** в `document.body` и на время показывает себя единственной (включает `suspendAllExceptSelf()`).

Итого: любая модалка может поверх открыть confirm — UX остаётся предсказуемым, без «двойных» обработчиков и гонок событий.

---

## Полезные заметки

* Токен хранится в **httpOnly-cookie** `auth_token`, 7 дней. Новый логин инвалидирует прежний токен пользователя.
* `/api/accounts` отдаёт `{"state":"ready","accounts":[...]}` или `{"state":"refreshing"}`.
  Клиент опрашивает «умно» (без спама), а на 401 — глобально редиректит на `/login`.
* Сессии Pyrogram и БД (`backend/app.db`) добавлены в `.gitignore`. Для «чистого» старта — удали эти файлы/папки.

---

## Быстрый чек-лист

```bash
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate  # или source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app

# Frontend
cd frontend
npm i
npm run dev
# → http://localhost:5173
```
