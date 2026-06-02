# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python manage.py runserver          # запуск сервера разработки
python manage.py migrate            # применить миграции
python manage.py makemigrations core  # создать миграцию после изменения models.py
python manage.py collectstatic --noinput  # собрать статику (для продакшна)
python manage.py createsuperuser    # создать admin-пользователя
python manage.py seed_data          # заполнить БД тестовыми данными
python manage.py check_no_shows     # отметить незаехавших как no-show
```

## Секреты и конфигурация

Все чувствительные данные — в `local_settings.py` (файл в `.gitignore`, не коммитится):
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`

`zoohotel/settings.py` содержит только безопасные дефолты и в конце делает `from local_settings import *`.

## Архитектура

### Роли и вью-модули

Три роли пользователей (`CustomUser.role`): `admin`, `caretaker`, `client`. Каждой роли соответствует отдельный вью-модуль и набор URL-префиксов:

| Роль | Вью-модуль | URL-префикс | Декоратор |
|------|-----------|-------------|-----------|
| admin | `views_admin.py` | `/panel/` | `@admin_only` |
| caretaker | `views_caretaker.py` | `/caretaker/` | `@caretaker_required` |
| client | `views_cabinet.py` | `/cabinet/` | `@client_required` |
| гость | `views_public.py` | `/` | без декоратора |

`@caretaker_required` пропускает и роль `admin`. Декораторы — в `core/decorators.py`.

### Модели (core/models.py)

Цепочка зависимостей: `CustomUser` → `Client` → `Animal` → `Booking` → `Payment` / `Task` / `BookingService`.

- `Client` — отдельная модель от `CustomUser`, связана через `OneToOne` (`client_profile`). Гостевые бронирования создают `Client` без привязки к `CustomUser`.
- `Booking.total_price` вычисляется при создании: `room.price_per_day × nights + sum(services)`.
- `Payment` создаётся автоматически при создании `Booking`. Поле `yookassa_payment_id` хранит ID платежа в ЮKassa.

### Платежи (ЮKassa)

Две точки входа в оплату:
1. **Авторизованный клиент** (`cabinet/bookings/`) → `cabinet_pay_yookassa` в `views_cabinet.py`
2. **Гость** (`booking/success/`) → `booking_pay_online` в `views_public.py`

Вебхук от ЮKassa: `POST /payment/webhook/` — `@csrf_exempt`, обновляет `Payment.status`.
После оплаты ЮKassa делает редирект на `/payment/return/` (клиент) или `/booking/payment/return/` (гость).

### Логирование

`log_action(request, action, entity_type, entity_id)` из `decorators.py` — пишет в модель `Log`. Вызывается вручную в каждом вью при значимых действиях.

### Шаблоны

Три базовых шаблона: `base.html` (публичный), `base_admin.html` (панель), `base_cabinet.html` (личный кабинет). Шаблоны организованы в папки по роли: `templates/public/`, `templates/cabinet/`, `templates/admin_panel/`, `templates/caretaker/`.

## Деплой (PythonAnywhere)

```bash
git pull
python manage.py migrate
python manage.py collectstatic --noinput
# затем Reload в Web App
```

Static files: `/static/` → `staticfiles/`, `/media/` → `media/`.  
Virtualenv: `~/.virtualenvs/zoohotel` (Python 3.11).
