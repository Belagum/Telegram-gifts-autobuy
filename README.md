# GiftBuyer — README

## Назначение

Веб-панель для работы с Telegram-аккаунтами (через Pyrogram): добавление аккаунтов по телефону, сохранение сессий, просмотр имени/username и баланса звёзд. UI — React (Vite), backend — Flask + SQLAlchemy + Pyrogram.
Поддерживаются **несколько API-профилей** (api\_id/api\_hash) на пользователя: можно создавать, переименовывать, выбирать при добавлении аккаунта и удалять (если не используется).

---

## Требования

* Python 3.11+
* Node.js 20+ и npm
* Windows / macOS / Linux
  (ниже команды для Windows; на \*nix замените активацию venv и пути)

---

## Структура

```
GiftBuyer/
  backend/
    app.py              # точка входа Flask
    db.py               # engine, session, Base
    models.py           # User, SessionToken, ApiProfile, Account
    auth.py             # hash/verify, JWT-like токены, декораторы
    pyro_login.py       # логин через Pyrogram, звёзды
    routes/             # bp_auth, bp_acc, bp_misc
    sessions/           # .session файлы Pyrogram (создаётся автоматически)
    requirements.txt
    __init__.py
  frontend/
    package.json
    vite.config.js
    src/
      ui/ModalStack.jsx # стек модалок
      ...
  README.md
```

---

## Backend — установка и запуск

### 1) Зависимости

```bat
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Запуск (терминал)

Запускаем **как модуль**, чтобы корректно работали пакетные импорты:

```bat
cd ..         REM перейти в корень GiftBuyer
backend\.venv\Scripts\python.exe -m backend.app
```

Сервер: `http://localhost:5000`.

### 3) Запуск (PyCharm)

* Run → Edit Configurations… → **+ Python**

  * **Run kind**: *Module name*
  * **Module name**: `backend.app`
  * **Working directory**: путь к корню `GiftBuyer`
  * **Interpreter**: `…\GiftBuyer\backend\.venv\Scripts\python.exe`
  * Включить: *Add content roots to PYTHONPATH*, *Add source roots to PYTHONPATH*.
* OK → Run.

---

## Frontend — установка и запуск

```bat
cd frontend
npm i
npm run dev
```

Фронтенд: `http://localhost:5173`
В `vite.config.js` настроен прокси на `/api` → `http://localhost:5000`.

---

## Продакшен-деплой (минимум)

### Вариант A: один сервер (Linux), Nginx как reverse proxy

1. **Собрать фронтенд**:

```bash
cd frontend
npm ci
npm run build           # создаст dist/
```

2. **Поднять backend**:

* Linux (systemd + gunicorn):

  ```bash
  cd backend
  python -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt gunicorn
  # запуск (отладочно)
  gunicorn -w 2 -b 127.0.0.1:5000 'app:create_app()'
  ```

  Пример unit-файла `/etc/systemd/system/giftbuyer.service`:

  ```
  [Unit]
  Description=GiftBuyer backend
  After=network.target

  [Service]
  WorkingDirectory=/opt/GiftBuyer/backend
  Environment=PYTHONUNBUFFERED=1
  ExecStart=/opt/GiftBuyer/backend/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 'app:create_app()'
  Restart=on-failure
  User=www-data
  Group=www-data

  [Install]
  WantedBy=multi-user.target
  ```

  ```bash
  systemctl daemon-reload
  systemctl enable --now giftbuyer
  ```

* Windows: используйте `waitress` или NSSM:

  ```bat
  pip install waitress
  waitress-serve --listen=127.0.0.1:5000 app:create_app
  ```

3. **Nginx** (статик + прокси API):

```
server {
  listen 80;
  server_name your.domain;

  root /opt/GiftBuyer/frontend/dist;
  index index.html;

  location /api/ {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location / {
    try_files $uri /index.html;
  }
}
```

Подключите HTTPS (Certbot/Caddy — на ваш вкус).

### Вариант B: два процесса вручную (Windows)

* Backend: `backend\.venv\Scripts\python.exe -m backend.app`
* Frontend: `cd frontend && npm run build && npx serve -s dist -l 5173`
  И использовать Nginx/Apache/traefik для проксирования `/api` → `:5000`.

---

## Данные и хранение

* **БД**: SQLite `backend/app.db`.
* **Таблицы** (минимум):

  * `users`: `id`, `username`, `password_hash`.
  * `session_tokens`: один активный токен на устройство/браузер; при новом входе старые токены для этого устройства инвалидируются; `DELETE /api/auth/logout` удаляет текущий токен.
  * `api_profiles`: `id`, `user_id`, `api_id`, `api_hash`, `name`.
    Уникальность: `(user_id, api_id)` **и** `(user_id, api_hash)`.
    Нельзя создать дубликат по одному из полей. Удаление запрещено, если профиль привязан к аккаунтам.
  * `accounts`: `id`, `user_id`, `api_profile_id`, `phone`, `session_path`, `first_name`, `username`, `stars_amount`, `stars_nanos`.
* **Pyrogram-сессии**: `backend/sessions/user_<user_id>/<phone>.session`.
  Если логин отменён/ошибка — временная сессия удаляется.

---

## Логика работы

### Аутентификация (панель)

* Регистрация/логин простые (username/password).
* После логина фронт хранит токен в `localStorage`, отправляет `Authorization: Bearer ...`.
* Для «одного устройства — один токен» сервер инвалидирует старый токен при новом входе с того же клиента (или при logout).

### API-профили (my.telegram.org)

* Кнопка «Добавить аккаунт» открывает выбор API-профиля.
* Модалка «Выбери API профиль»:

  * список профилей, можно переименовать (inline), удалить (с подтверждением),
  * проверка на дубликаты: нельзя повторить `api_id` или `api_hash` внутри одного пользователя,
  * кнопка «Добавить новый API» — отдельная модалка, поля `api_id`, `api_hash`, опц. `name`.
* При удалении профиль нельзя удалить, если он используется существующими аккаунтами.

### Добавление Telegram-аккаунта

1. Выбор API-профиля.
2. Ввод телефона → отправка кода (`auth.sendCode`).
3. Ввод кода:

   * если включена 2FA — запрашивается пароль,
   * в случае ошибок телеги (`PHONE_NUMBER_BANNED` и т.п.) фронт показывает код/сообщение.
4. Успех → сохраняем:

   * `.session` в `backend/sessions/...`,
   * профиль аккаунта в БД (имя, username),
   * баланс звёзд (через `payments.GetStarsStatus`).
5. Отмена/ошибка → сессия удаляется.

---

## Стек модалок (почему и как)

Задача: когда открывается модалка подтверждения (например, «Удалить API профиль?»), она должна:

* рендериться **поверх** текущей модалки,
* закрываться по **Esc** и клику по фону,
* **не** закрывать родительскую модалку насовсем и **не** ловить её обработчики.

Решение: собственный стек модалок.

### Компоненты

* `ModalProvider` (контекст):

  * хранит `stack` открытых модалок (`[{id, onClose}]`),
  * глобально обрабатывает `Esc`: закрывается **верхняя** модалка,
  * поле `suspender`: id модалки, которая «скрывает» остальные (не демонтирует, а говорит им не рендериться).

* `useModal(onClose)`:

  * регистрирует модалку в стеке, возвращает:

    * `isTop` — текущая модалка верхняя,
    * `hidden` — модалку нужно временно спрятать (когда поверх открылась confirm),
    * `suspendAllExceptSelf()` / `resumeAll()` — включить/снять «приглушение» остальных.

* `ConfirmModal`:

  * отрисовывается **через портал** (`createPortal`) в `document.body`,
  * при маунте делает `suspendAllExceptSelf()`, при размонте — `resumeAll()`.

* Базовые модалки (`SelectApiProfileModal`, `AddApiModal`, `AddAccountModal`):

  * используют `useModal`,
  * при `hidden` — не рендерятся (или частично, если внутри них открыт `ConfirmModal` — это учтено).

Итог: ESC закрывает только верхнюю, клик по фону — тоже. При открытии Confirm базовая модалка «замораживается» и не мешает.

---

## Уведомления

Используется `react-toastify`. Обёртка `showPromise(p, pending, success, error)` отображает тосты «в процессе/успех/ошибка» для промиса.
Ошибки от Telegram (например, `PHONE_NUMBER_BANNED`) проходят до фронта и показываются пользователю.

---

## Частые проблемы

* **Не открывается модалка подтверждения / всё пропадает.**
  Проверьте, что `ModalProvider` оборачивает всё приложение (`main.jsx`) и **нет дублей** `ModalProvider/useModal` в других файлах. `ConfirmModal` должен импортировать `useModal` только из `ui/ModalStack.jsx` и рендериться через портал.
* **Бесконечные рендеры / Maximum update depth exceeded.**
  В `ModalProvider.register` обязательно проверяется наличие id в стеке, а обработчик `keydown` один, без зависимостей на весь `ctx`.
* **`Table 'users' is already defined` при запуске.**
  Запускайте `python -m backend.app`, проверьте `backend/__init__.py`, удалите `__pycache__`.
* **`PhoneNumberBanned` и т.п. при логине Telegram.**
  В тосте показывается код и текст ошибки. Сессия удаляется, аккаунт не добавляется.
* **Windows asyncio loop.**
  В `pyro_login.py` на Windows выставляется `WindowsSelectorEventLoopPolicy`, чтобы Pyrogram корректно создавал event loop.

---

## Сброс/очистка

* Удалить все сессии Pyrogram: удалить папку `backend/sessions/`.
* Сбросить БД: удалить `backend/app.db` (все данные будут потеряны).

---

## Быстрый чек-лист

```bat
REM Backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cd ..
backend\.venv\Scripts\python.exe -m backend.app

REM Frontend
cd frontend
npm i
npm run dev
```

Открыть `http://localhost:5173`, зарегистрироваться, добавить API-профиль, добавить аккаунт, проверить список.
