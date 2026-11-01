# Система бронирования помещений — ПИРИП ЛР-02

Flask-приложение с PostgreSQL для бронирования помещений. Реализованы: регистрация/вход/выход, создание заявок, смена статусов администратором, оставление отзывов.

---

## Стек технологий

| Компонент | Версия |
|-----------|--------|
| Python    | 3.10+  |
| Flask     | ≥ 2.3  |
| psycopg2  | ≥ 2.9  |
| PostgreSQL | 14+   |
| Tailwind CSS | CDN |

---

## Быстрый старт

### 1. Клонировать / распаковать проект

```
project/
├── sql/
│   ├── schema.sql
│   └── seed.sql
├── src/
│   ├── app.py
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html
│       ├── admin.html
│       └── 403.html
├── requirements.txt
└── README.md
```

### 2. Создать и активировать виртуальное окружение

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Создать базу данных PostgreSQL

```bash
psql -U postgres -c "CREATE DATABASE venue_db;"
psql -U postgres -d venue_db -f sql/schema.sql
psql -U postgres -d venue_db -f sql/seed.sql
```

> **Примечание:** seed.sql содержит хеши паролей для демо-аккаунтов. Если хеши не совпадают с вашей версией Werkzeug — зарегистрируйте аккаунты вручную через /register, затем обновите роль администратора в БД:
> ```sql
> UPDATE users SET role = 'admin' WHERE login = 'Conf2027';
> ```

### 5. Переменные окружения (опционально)

По умолчанию приложение подключается к:
- host: `localhost`
- port: `5432`
- database: `venue_db`
- user: `postgres`
- password: `postgres`

Переопределить через переменные окружения:

```bash
# Windows (PowerShell)
$env:DB_HOST     = "localhost"
$env:DB_PORT     = "5432"
$env:DB_NAME     = "venue_db"
$env:DB_USER     = "postgres"
$env:DB_PASSWORD = "your_password"
$env:SECRET_KEY  = "your-secret-key"

# Linux / macOS
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=venue_db
export DB_USER=postgres
export DB_PASSWORD=your_password
export SECRET_KEY=your-secret-key
```

### 6. Запустить приложение

```bash
cd src
python app.py
```

Откройте в браузере: **http://127.0.0.1:5000**

---

## Демо-аккаунты

| Роль | Логин | Пароль |
|------|-------|--------|
| Администратор | `Conf2027` | `Demo77` |
| Клиент | `client01` | `ClientPass123!` |

---

## Маршруты API

| Метод | URL | Защита | Описание |
|-------|-----|--------|----------|
| GET | `/` | — | Редирект на `/login` или `/dashboard` |
| GET | `/register` | — | Форма регистрации |
| POST | `/register` | — | Создание аккаунта |
| GET | `/login` | — | Форма входа |
| POST | `/login` | — | Аутентификация |
| GET | `/logout` | — | Выход |
| GET | `/dashboard` | `@login_required` | Личный кабинет |
| POST | `/reservation/new` | `@login_required` | Создание заявки |
| POST | `/reservation/<id>/status` | `@admin_required` | Смена статуса заявки |
| POST | `/review/new` | `@login_required` | Оставить отзыв |
| GET | `/admin-panel` | `@admin_required` | Панель администратора |

---

## Правила бизнес-логики

- **Регистрация:** логин — только латиница/цифры ≥6 символов; ФИО — только кириллица; телефон — формат `8(XXX)XXX-XX-XX`; email — стандартный.
- **Заявки:** `start_time` должен быть раньше `end_time`.
- **Статусы:** строгая последовательность `Новая → Мероприятие назначено → Завершено`. Откат невозможен.
- **Отзывы:** только для заявок со статусом `Завершено`, только автор заявки, только один отзыв на заявку.
- **403:** возвращается JSON `{"status": 403, "error": "AccessDenied", "detail": "Missing admin privilege"}` при попытке доступа к маршрутам администратора без прав.

---

## Валидация на сервере

```
LOGIN_REGEX : ^[a-zA-Z0-9]{6,}$
FIO_REGEX   : ^[А-Яа-яЁё\s]+$
PHONE_REGEX : ^8\(\d{3}\)\d{3}-\d{2}-\d{2}$
EMAIL_REGEX : стандартный email
```

---

## Безопасность

- Пароли хешируются через `werkzeug.security.generate_password_hash` (pbkdf2:sha256).
- Все SQL-запросы параметризованы (защита от SQL-инъекций).
- Сессия хранит только: `user_id`, `login`, `role`, `full_name`.
- `SECRET_KEY` задаётся через переменную окружения в production.
