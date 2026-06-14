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
- `Booking.total_price` вычисляется при создании: `room.price_per_day × nights + sum(services)`. Ежедневные услуги (`Service.is_daily=True`) умножаются на количество ночей.
- `Payment` создаётся автоматически при создании `Booking` с `amount = total_price`. Поле `yookassa_payment_id` хранит ID платежа в ЮKassa. При инициации оплаты `payment.amount` всегда синхронизируется с `booking.total_price`.

### Услуги (Service)

Активные услуги (4 штуки):
- **Спецпитание** — ежедневная (`is_daily=True`), тарифицируется × сутки
- **Дополнительный выгул** — ежедневная (`is_daily=True`), тарифицируется × сутки
- **Ветеринарный осмотр** — разовая
- **Груминг стрижка** — разовая

Поле `Service.is_daily` определяет тарификацию и генерацию задач: ежедневные → задача каждый день, разовые → одна задача.

Неактивные (не показываются при бронировании): Стандартное кормление, Выгул (30 мин), Дополнительный уход, Груминг базовый.

### Задачи (Task)

Задачи генерируются автоматически при переводе брони в статус `confirmed` функцией `_generate_tasks` в `views_admin.py`.

Базовые задачи на каждый день: 08:00 кормление, 10:00 уборка вольера, 13:00 кормление, 18:00 кормление.

Поле `Task.period` ('morning'/'day'/'evening'/'night') выводится автоматически из `scheduled_time` в `Task.save()`. Названия типовых задач (кормление/прогулка/уборка/осмотр) согласуются с периодом суток автоматически — «Вечернее кормление», «Утренняя прогулка» и т.д. `bulk_create` обходит `save()`, поэтому в `_generate_tasks` период и название проставляются вручную перед вставкой.

`Task.is_overdue` / `Task.overdue_label` — вычисляемые свойства, не пишут в БД.

Фильтр «В работе» в разделе caretaker намеренно убран — только «Ожидает» и «Готово».

### Платежи (ЮKassa)

Две точки входа в оплату:
1. **Авторизованный клиент** (`cabinet/bookings/`) → `cabinet_pay_yookassa` в `views_cabinet.py`
2. **Гость** (`booking/success/`) → `booking_pay_online` в `views_public.py`

Вебхук от ЮKassa: `POST /payment/webhook/` — `@csrf_exempt`, обновляет `Payment.status`.
После оплаты ЮKassa делает редирект на `/payment/return/` (клиент) или `/booking/payment/return/` (гость).

### Личный кабинет клиента

В списке бронирований (`cabinet/bookings/`) клиент видит все активности по брони:
- Базовые задачи (кормление, уборка) — сгруппированы по названию с прогрессом `(2/5)`
- Доп. услуги — статус и прогресс выполнения задач
- Иконки: ⏰ ожидает / ⟳ выполняется / ✓ оказано

При бронировании клиент выбирает **класс** (Вольер/Стандарт/Люкс), система автоматически назначает свободный номер в этом классе (`_find_free_room`). Номеров: 5 вольеров, 4 стандарта, 2 люкса. Проверка занятости через `api_available_rooms` → `Room.is_available_for()`.

Бронь автоматически переходит в статус `completed`, когда сотрудник отмечает последнюю задачу выполненной (`task_complete` в `views_caretaker.py`).

### Логирование

`log_action(request, action, entity_type, entity_id)` из `decorators.py` — пишет в модель `Log`. Вызывается вручную в каждом вью при значимых действиях.

### Шаблоны

Три базовых шаблона: `base.html` (публичный), `base_admin.html` (панель), `base_cabinet.html` (личный кабинет). Шаблоны организованы в папки по роли: `templates/public/`, `templates/cabinet/`, `templates/admin_panel/`, `templates/caretaker/`.

## Деплой (PythonAnywhere)

```bash
cd ~/zoohotel && git pull && python manage.py migrate && python manage.py collectstatic --noinput
# затем Reload в Web App
```

Static files: `/static/` → `staticfiles/`, `/media/` → `media/`.  
Virtualenv: `~/.virtualenvs/zoohotel` (Python 3.11).
