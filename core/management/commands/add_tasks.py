from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Добавить задачи на сегодня и завтра'

    def handle(self, *args, **kwargs):
        from core.models import CustomUser, Booking, Service, Task

        caretaker = CustomUser.objects.filter(role='caretaker').first()
        if not caretaker:
            self.stdout.write(self.style.ERROR('Сотрудник-уходчик не найден. Сначала запустите seed_data.'))
            return

        bookings = list(Booking.objects.filter(status='confirmed').select_related('animal', 'room'))
        if not bookings:
            self.stdout.write(self.style.ERROR('Нет подтверждённых бронирований. Сначала запустите seed_data.'))
            return

        services = {s.name: s for s in Service.objects.all()}
        feed = services.get('Стандартное кормление')
        walk = services.get('Выгул (30 мин)')
        vet  = services.get('Ветеринарный осмотр')
        groom = services.get('Груминг базовый')
        care = services.get('Дополнительный уход')

        now = timezone.now()

        def t(day_offset, hour, minute=0):
            return (now + datetime.timedelta(days=day_offset)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        b0 = bookings[0]
        b1 = bookings[1] if len(bookings) > 1 else bookings[0]

        tasks_to_create = [
            # --- Сегодня ---
            {'booking': b0, 'service': feed,  'title': 'Утреннее кормление',       'scheduled_time': t(0, 8),  'status': 'pending'},
            {'booking': b0, 'service': walk,  'title': 'Утренняя прогулка',        'scheduled_time': t(0, 9),  'status': 'pending'},
            {'booking': b0, 'service': vet,   'title': 'Плановый осмотр',          'scheduled_time': t(0, 11), 'status': 'pending'},
            {'booking': b1, 'service': feed,  'title': 'Дневное кормление',        'scheduled_time': t(0, 13), 'status': 'pending'},
            {'booking': b1, 'service': care,  'title': 'Уход и наблюдение',        'scheduled_time': t(0, 15), 'status': 'pending'},
            {'booking': b0, 'service': feed,  'title': 'Вечернее кормление',       'scheduled_time': t(0, 18), 'status': 'pending'},
            {'booking': b1, 'service': walk,  'title': 'Вечерняя прогулка',        'scheduled_time': t(0, 19), 'status': 'pending'},
            # --- Завтра ---
            {'booking': b0, 'service': feed,  'title': 'Утреннее кормление',       'scheduled_time': t(1, 8),  'status': 'pending'},
            {'booking': b0, 'service': walk,  'title': 'Утренняя прогулка',        'scheduled_time': t(1, 9),  'status': 'pending'},
            {'booking': b1, 'service': groom, 'title': 'Груминг (купание)',         'scheduled_time': t(1, 10), 'status': 'pending'},
            {'booking': b1, 'service': feed,  'title': 'Дневное кормление',        'scheduled_time': t(1, 13), 'status': 'pending'},
            {'booking': b0, 'service': vet,   'title': 'Контрольный осмотр',       'scheduled_time': t(1, 14), 'status': 'pending'},
            {'booking': b0, 'service': feed,  'title': 'Вечернее кормление',       'scheduled_time': t(1, 18), 'status': 'pending'},
            {'booking': b1, 'service': walk,  'title': 'Вечерняя прогулка',        'scheduled_time': t(1, 19), 'status': 'pending'},
        ]

        created_count = 0
        for td in tasks_to_create:
            _, created = Task.objects.get_or_create(
                booking=td['booking'],
                service=td['service'],
                scheduled_time=td['scheduled_time'],
                defaults={
                    'assigned_to': caretaker,
                    'title': td['title'],
                    'status': td['status'],
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Готово! Создано задач: {created_count} (сегодня и завтра).'
        ))
