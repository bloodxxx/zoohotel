from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('caretaker', 'Специалист по уходу'),
        ('client', 'Клиент'),
    ]
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    is_blocked = models.BooleanField('Заблокирован', default=False)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_manager(self):
        return False

    @property
    def is_caretaker(self):
        return self.role == 'caretaker'

    @property
    def is_client_role(self):
        return self.role == 'client'

    @property
    def is_staff_member(self):
        return self.role in ('admin', 'caretaker')


class Client(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='client_profile', verbose_name='Аккаунт'
    )
    full_name = models.CharField('ФИО', max_length=100)
    phone = models.CharField('Телефон', max_length=20)
    email = models.EmailField('Email')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['full_name']

    def __str__(self):
        return self.full_name

    def has_active_bookings(self):
        return self.bookings.filter(status__in=('pending', 'confirmed')).exists()


class Animal(models.Model):
    SPECIES_CHOICES = [
        ('dog', 'Собака'),
        ('cat', 'Кошка'),
        ('other', 'Другое'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='animals', verbose_name='Владелец')
    name = models.CharField('Кличка', max_length=100)
    species = models.CharField('Вид', max_length=10, choices=SPECIES_CHOICES)
    breed = models.CharField('Порода', max_length=100, blank=True)
    birth_date = models.DateField('Дата рождения', null=True, blank=True)
    special_needs = models.TextField('Особые отметки', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Животное'
        verbose_name_plural = 'Животные'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_species_display()})'

    def age_display(self):
        if not self.birth_date:
            return '—'
        from datetime import date
        today = date.today()
        years = today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
        if years == 0:
            months = (today.year - self.birth_date.year) * 12 + today.month - self.birth_date.month
            return f'{months} мес.'
        return f'{years} лет'


class AnimalDocument(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='documents', verbose_name='Животное')
    document_type = models.CharField('Тип документа', max_length=100)
    file = models.FileField('Файл', upload_to='documents/')
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        verbose_name = 'Документ животного'
        verbose_name_plural = 'Документы животных'

    def __str__(self):
        return f'{self.document_type} — {self.animal.name}'


class Room(models.Model):
    TYPE_CHOICES = [
        ('aviary', 'Вольер'),
        ('standard', 'Стандарт'),
        ('lux', 'Люкс'),
    ]
    STATUS_CHOICES = [
        ('available', 'Доступен'),
        ('maintenance', 'На ремонте'),
    ]
    name = models.CharField('Название', max_length=50)
    type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES)
    description = models.TextField('Описание', blank=True)
    price_per_day = models.DecimalField('Цена за сутки', max_digits=10, decimal_places=2)
    image = models.ImageField('Фото', upload_to='rooms/', blank=True, null=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Номер'
        verbose_name_plural = 'Номера'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'

    def is_available_for(self, check_in, check_out, exclude_booking_id=None):
        if self.status == 'maintenance':
            return False
        qs = self.bookings.filter(
            status__in=('pending', 'confirmed'),
            check_in_date__lt=check_out,
            check_out_date__gt=check_in,
        )
        if exclude_booking_id:
            qs = qs.exclude(pk=exclude_booking_id)
        return not qs.exists()


class RoomImage(models.Model):
    room = models.ForeignKey('Room', on_delete=models.CASCADE, related_name='images', verbose_name='Номер')
    image = models.ImageField('Фото', upload_to='rooms/gallery/')
    caption = models.CharField('Подпись', max_length=120, blank=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Фото номера'
        verbose_name_plural = 'Фотографии номеров'
        ordering = ['order', 'uploaded_at']

    def __str__(self):
        return f'Фото #{self.pk} — {self.room.name}'


class Service(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('inactive', 'Неактивна'),
    ]
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    category = models.CharField('Категория', max_length=100)
    price = models.DecimalField('Стоимость', max_digits=10, decimal_places=2)
    unit = models.CharField('Единица измерения', max_length=50)
    is_daily = models.BooleanField('Начисляется за каждую ночь', default=False)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='bookings', verbose_name='Клиент')
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT, related_name='bookings', verbose_name='Животное')
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='bookings', verbose_name='Номер')
    check_in_date = models.DateTimeField('Дата заезда')
    check_out_date = models.DateTimeField('Дата выезда')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField('Итоговая стоимость', max_digits=10, decimal_places=2, default=0)
    notes = models.TextField('Примечания', blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_bookings', verbose_name='Создал'
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.animal.name} — {self.check_in_date.strftime("%d.%m.%Y")}'

    def nights(self):
        delta = self.check_out_date.date() - self.check_in_date.date()
        return max(delta.days, 1)

    def calculate_total(self):
        room_cost = self.room.price_per_day * self.nights()
        services_cost = sum(bs.price * bs.quantity for bs in self.booking_services.all())
        return room_cost + services_cost

    def status_badge_class(self):
        return {
            'pending': 'status-warning',
            'confirmed': 'status-success',
            'completed': 'status-info',
            'cancelled': 'status-danger',
        }.get(self.status, 'status-secondary')


class BookingService(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_services')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField('Количество', default=1)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Услуга в бронировании'
        verbose_name_plural = 'Услуги в бронировании'

    def __str__(self):
        return f'{self.service.name} x{self.quantity}'


class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('in_progress', 'Выполняется'),
        ('completed', 'Выполнено'),
    ]
    PERIOD_CHOICES = [
        ('morning', 'Утро'),
        ('day', 'День'),
        ('evening', 'Вечер'),
        ('night', 'Ночь'),
    ]
    # Прилагательное периода в трёх родах: (мужской, женский, средний)
    # утренн-ий/яя/ее, днев-ной/ная/ное, вечерн-ий/яя/ее, ноч-ной/ная/ное
    PERIOD_ADJECTIVES = {
        'morning': ('Утренний', 'Утренняя', 'Утреннее'),
        'day': ('Дневной', 'Дневная', 'Дневное'),
        'evening': ('Вечерний', 'Вечерняя', 'Вечернее'),
        'night': ('Ночной', 'Ночная', 'Ночное'),
    }
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='tasks', verbose_name='Бронирование')
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Услуга'
    )
    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks', verbose_name='Сотрудник'
    )
    title = models.CharField('Название задачи', max_length=255)
    instructions = models.TextField('Инструкции', blank=True)
    scheduled_time = models.DateTimeField('Плановое время')
    period = models.CharField('Период суток', max_length=10, choices=PERIOD_CHOICES, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    start_time = models.DateTimeField('Время начала', null=True, blank=True)
    end_time = models.DateTimeField('Время окончания', null=True, blank=True)
    notes = models.TextField('Заметки сотрудника', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Задача ухода'
        verbose_name_plural = 'Задачи ухода'
        ordering = ['scheduled_time']

    def __str__(self):
        return f'{self.title} — {self.booking.animal.name}'

    def status_badge_class(self):
        return {
            'pending': 'status-warning',
            'in_progress': 'status-primary',
            'completed': 'status-success',
        }.get(self.status, 'status-secondary')

    @staticmethod
    def period_for_hour(hour):
        """Период суток по часу планового времени."""
        if 5 <= hour < 12:
            return 'morning'
        if 12 <= hour < 17:
            return 'day'
        if 17 <= hour < 22:
            return 'evening'
        return 'night'

    # Базовые названия, которые согласуются с периодом, и их род:
    # 'f' — женский (прогулка, уборка), 'n' — средний (кормление), 'm' — мужской (осмотр)
    SYNCABLE_TITLES = {
        'кормление': ('кормление', 'n'),
        'прогулка': ('прогулка', 'f'),
        'уборка': ('уборка вольера', 'f'),
        'осмотр': ('осмотр', 'm'),
    }

    def _detect_syncable(self):
        """Если название содержит согласуемое ключевое слово, вернуть (базовое_название, род)."""
        low = self.title.lower()
        for keyword, (base, gender) in self.SYNCABLE_TITLES.items():
            if keyword in low:
                return base, gender
        return None

    def synced_title(self):
        """Название, согласованное с периодом суток (или исходное, если согласовать нельзя)."""
        detected = self._detect_syncable()
        if not detected or not self.period:
            return self.title
        base, gender = detected
        gender_index = {'m': 0, 'f': 1, 'n': 2}[gender]
        adjective = self.PERIOD_ADJECTIVES[self.period][gender_index]
        return f'{adjective} {base}'

    def save(self, *args, **kwargs):
        # Период всегда выводится из планового времени — единый источник правды.
        if self.scheduled_time:
            self.period = self.period_for_hour(timezone.localtime(self.scheduled_time).hour)
        # Согласуем название с периодом для типовых задач (кормление/прогулка/уборка/осмотр).
        self.title = self.synced_title()
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Задача просрочена: плановое время прошло, а она ещё не выполнена."""
        if self.status == 'completed':
            return False
        return self.scheduled_time < timezone.now()

    @property
    def overdue_label(self):
        """Человекочитаемая длительность просрочки, напр. '4 ч 20 мин'."""
        if not self.is_overdue:
            return ''
        delta = timezone.now() - self.scheduled_time
        total_minutes = int(delta.total_seconds() // 60)
        days, rem = divmod(total_minutes, 1440)
        hours, minutes = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f'{days} дн')
        if hours:
            parts.append(f'{hours} ч')
        if minutes and not days:
            parts.append(f'{minutes} мин')
        return ' '.join(parts) or 'только что'


class Payment(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Не оплачено'),
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('refunded', 'Возврат'),
        ('failed', 'Ошибка оплаты'),
    ]
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name='payments', verbose_name='Бронирование')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='payments', verbose_name='Клиент')
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    payment_method = models.CharField('Способ оплаты', max_length=50)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='unpaid')
    transaction_id = models.CharField('Номер транзакции', max_length=100, blank=True)
    yookassa_payment_id = models.CharField('YooKassa ID', max_length=100, blank=True)
    payment_date = models.DateTimeField('Дата оплаты', null=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']

    def __str__(self):
        return f'Платеж #{self.pk} — {self.client} — {self.amount} руб.'

    def status_badge_class(self):
        return {
            'unpaid': 'status-secondary',
            'pending': 'status-warning',
            'paid': 'status-success',
            'refunded': 'status-info',
            'failed': 'status-danger',
        }.get(self.status, 'status-secondary')


class Log(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Пользователь'
    )
    action = models.CharField('Действие', max_length=255)
    entity_type = models.CharField('Тип объекта', max_length=100, blank=True)
    entity_id = models.PositiveIntegerField('ID объекта', null=True, blank=True)
    result = models.CharField('Результат', max_length=50, default='success')
    created_at = models.DateTimeField('Дата и время', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал действий'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} — {self.created_at.strftime("%d.%m.%Y %H:%M")}'


def write_log(user, action, entity_type='', entity_id=None, result='success'):
    Log.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
    )


class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Токен сброса пароля'
        verbose_name_plural = 'Токены сброса пароля'
