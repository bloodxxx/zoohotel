from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Заполнить базу данных демонстрационными данными'

    def handle(self, *args, **kwargs):
        from core.models import (CustomUser, Client, Animal, Room, Service,
                                  Booking, BookingService, Task, Payment)

        self.stdout.write('Создание пользователей...')

        admin, _ = CustomUser.objects.get_or_create(username='admin', defaults={
            'first_name': 'Иван', 'last_name': 'Петров',
            'email': 'admin@zoohotel.ru', 'phone': '+7 (3412) 11-11-11',
            'role': 'admin', 'is_staff': True, 'is_superuser': True,
        })
        if _: admin.set_password('admin123'); admin.save()

        manager, _ = CustomUser.objects.get_or_create(username='manager', defaults={
            'first_name': 'Мария', 'last_name': 'Сидорова',
            'email': 'manager@zoohotel.ru', 'phone': '+7 (3412) 22-22-22',
            'role': 'manager',
        })
        if _: manager.set_password('manager123'); manager.save()

        caretaker, _ = CustomUser.objects.get_or_create(username='caretaker', defaults={
            'first_name': 'Алексей', 'last_name': 'Козлов',
            'email': 'caretaker@zoohotel.ru', 'phone': '+7 (3412) 33-33-33',
            'role': 'caretaker',
        })
        if _: caretaker.set_password('care123'); caretaker.save()

        client_user, _ = CustomUser.objects.get_or_create(username='client', defaults={
            'first_name': 'Анна', 'last_name': 'Иванова',
            'email': 'client@zoohotel.ru', 'phone': '+7 (3412) 44-44-44',
            'role': 'client',
        })
        if _: client_user.set_password('client123'); client_user.save()

        self.stdout.write('Создание клиентов...')
        clients_data = [
            {'user': client_user, 'full_name': 'Иванова Анна Сергеевна', 'phone': '+7 (912) 111-11-11', 'email': 'ivanova@mail.ru'},
            {'full_name': 'Смирнов Дмитрий Александрович', 'phone': '+7 (912) 222-22-22', 'email': 'smirnov@mail.ru'},
            {'full_name': 'Козлова Екатерина Владимировна', 'phone': '+7 (912) 333-33-33', 'email': 'kozlova@mail.ru'},
        ]
        clients = []
        for cd in clients_data:
            user = cd.pop('user', None)
            c, _ = Client.objects.get_or_create(email=cd['email'], defaults=cd)
            if user and not c.user:
                c.user = user; c.save()
            clients.append(c)

        self.stdout.write('Создание животных...')
        animals_data = [
            {'client': clients[0], 'name': 'Барсик', 'species': 'cat', 'breed': 'Британская короткошёрстная', 'birth_date': datetime.date(2020, 3, 15), 'special_needs': 'Аллергия на корм с рыбой'},
            {'client': clients[0], 'name': 'Рекс', 'species': 'dog', 'breed': 'Немецкая овчарка', 'birth_date': datetime.date(2019, 7, 20)},
            {'client': clients[1], 'name': 'Мурка', 'species': 'cat', 'breed': 'Сиамская', 'birth_date': datetime.date(2021, 1, 10)},
            {'client': clients[1], 'name': 'Бобик', 'species': 'dog', 'breed': 'Лабрадор', 'birth_date': datetime.date(2018, 11, 5), 'special_needs': 'Принимает таблетки от аллергии — 1 таб. утром'},
            {'client': clients[2], 'name': 'Кеша', 'species': 'other', 'breed': 'Попугай', 'birth_date': datetime.date(2022, 6, 1)},
        ]
        animals = []
        for ad in animals_data:
            a, _ = Animal.objects.get_or_create(client=ad['client'], name=ad['name'], defaults=ad)
            animals.append(a)

        self.stdout.write('Создание номеров...')
        rooms_data = [
            {'name': 'Вольер №1', 'type': 'aviary', 'description': 'Стандартный вольер для небольших животных. Площадь 4 кв.м.', 'price_per_day': 800},
            {'name': 'Вольер №2', 'type': 'aviary', 'description': 'Стандартный вольер для небольших животных. Площадь 4 кв.м.', 'price_per_day': 800},
            {'name': 'Вольер №3', 'type': 'aviary', 'description': 'Стандартный вольер для небольших животных. Площадь 4 кв.м.', 'price_per_day': 800},
            {'name': 'Вольер №4', 'type': 'aviary', 'description': 'Стандартный вольер для небольших животных. Площадь 4 кв.м.', 'price_per_day': 800},
            {'name': 'Вольер №5', 'type': 'aviary', 'description': 'Стандартный вольер для небольших животных. Площадь 4 кв.м.', 'price_per_day': 800},
            {'name': 'Стандарт №1', 'type': 'standard', 'description': 'Просторный номер с мягкой подстилкой, игрушками и окном. Площадь 8 кв.м.', 'price_per_day': 1500},
            {'name': 'Стандарт №2', 'type': 'standard', 'description': 'Просторный номер с мягкой подстилкой, игрушками и окном. Площадь 8 кв.м.', 'price_per_day': 1500},
            {'name': 'Стандарт №3', 'type': 'standard', 'description': 'Просторный номер с мягкой подстилкой, игрушками и окном. Площадь 8 кв.м.', 'price_per_day': 1500},
            {'name': 'Стандарт №4', 'type': 'standard', 'description': 'Просторный номер с мягкой подстилкой, игрушками и окном. Площадь 8 кв.м.', 'price_per_day': 1500},
            {'name': 'Люкс №1 "Королевский"', 'type': 'lux', 'description': 'VIP-номер с видом на сад. Индивидуальный уход, премиум питание, ежедневный груминг. Площадь 16 кв.м.', 'price_per_day': 3500},
            {'name': 'Люкс №2 "Премиум"', 'type': 'lux', 'description': 'VIP-номер с зимним садом. Полный спа-уход и персональный смотритель. Площадь 20 кв.м.', 'price_per_day': 4500},
        ]
        rooms = []
        for rd in rooms_data:
            status = rd.pop('status', 'available')
            r, _ = Room.objects.get_or_create(name=rd['name'], defaults={**rd, 'status': status})
            rooms.append(r)

        self.stdout.write('Создание услуг...')
        services_data = [
            {'name': 'Стандартное кормление', 'category': 'Питание', 'price': 150, 'unit': 'раз', 'description': 'Кормление сухим кормом 2 раза в день'},
            {'name': 'Спецпитание', 'category': 'Питание', 'price': 350, 'unit': 'день', 'description': 'Индивидуальный рацион по требованиям владельца'},
            {'name': 'Выгул (30 мин)', 'category': 'Активность', 'price': 200, 'unit': 'прогулка', 'description': 'Выгул собаки на территории'},
            {'name': 'Дополнительный выгул', 'category': 'Активность', 'price': 300, 'unit': 'прогулка', 'description': 'Дополнительная прогулка по запросу'},
            {'name': 'Ветеринарный осмотр', 'category': 'Ветеринария', 'price': 500, 'unit': 'осмотр', 'description': 'Профилактический осмотр ветеринаром'},
            {'name': 'Груминг базовый', 'category': 'Груминг', 'price': 800, 'unit': 'процедура', 'description': 'Купание, сушка, расчёсывание'},
            {'name': 'Груминг стрижка', 'category': 'Груминг', 'price': 1500, 'unit': 'процедура', 'description': 'Полный груминг со стрижкой'},
            {'name': 'Дополнительный уход', 'category': 'Уход', 'price': 250, 'unit': 'день', 'description': 'Дополнительное внимание и игры'},
        ]
        services = []
        for sd in services_data:
            s, _ = Service.objects.get_or_create(name=sd['name'], defaults=sd)
            services.append(s)

        self.stdout.write('Создание бронирований...')
        now = timezone.now()
        # rooms[0..4]=вольеры, rooms[5..8]=стандарт, rooms[9..10]=люкс
        bookings_data = [
            {'client': clients[0], 'animal': animals[0], 'room': rooms[5], 'check_in': now - datetime.timedelta(days=3), 'check_out': now + datetime.timedelta(days=4), 'status': 'confirmed', 'svcs': [services[0], services[4]]},
            {'client': clients[0], 'animal': animals[1], 'room': rooms[0], 'check_in': now + datetime.timedelta(days=1), 'check_out': now + datetime.timedelta(days=5), 'status': 'pending', 'svcs': [services[2]]},
            {'client': clients[1], 'animal': animals[2], 'room': rooms[6], 'check_in': now - datetime.timedelta(days=10), 'check_out': now - datetime.timedelta(days=5), 'status': 'completed', 'svcs': [services[0], services[5]]},
            {'client': clients[1], 'animal': animals[3], 'room': rooms[9], 'check_in': now - datetime.timedelta(days=1), 'check_out': now + datetime.timedelta(days=6), 'status': 'confirmed', 'svcs': [services[1], services[2], services[6]]},
            {'client': clients[2], 'animal': animals[4], 'room': rooms[1], 'check_in': now + datetime.timedelta(days=3), 'check_out': now + datetime.timedelta(days=7), 'status': 'pending', 'svcs': []},
            {'client': clients[0], 'animal': animals[0], 'room': rooms[5], 'check_in': now - datetime.timedelta(days=30), 'check_out': now - datetime.timedelta(days=25), 'status': 'completed', 'svcs': [services[0]]},
        ]
        bookings = []
        for i, bd in enumerate(bookings_data):
            svcs = bd.pop('svcs')
            ci, co = bd.pop('check_in'), bd.pop('check_out')
            nights = max((co - ci).days, 1)
            svc_cost = sum(s.price for s in svcs)
            total = bd['room'].price_per_day * nights + svc_cost
            b, created = Booking.objects.get_or_create(
                client=bd['client'], animal=bd['animal'], check_in_date=ci,
                defaults={**bd, 'check_in_date': ci, 'check_out_date': co, 'total_price': total, 'created_by': admin}
            )
            if created:
                b.check_out_date = co
                b.total_price = total
                b.save()
                for svc in svcs:
                    BookingService.objects.create(booking=b, service=svc, quantity=1, price=svc.price)
            bookings.append(b)

        self.stdout.write('Создание задач ухода...')
        task_times = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=12, minute=0, second=0, microsecond=0),
            now.replace(hour=18, minute=0, second=0, microsecond=0),
            (now - datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0),
            (now + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        ]
        tasks_data = [
            {'booking': bookings[0], 'service': services[0], 'assigned_to': caretaker, 'scheduled_time': task_times[0], 'status': 'completed', 'notes': 'Съел весь корм, активен'},
            {'booking': bookings[0], 'service': services[4], 'assigned_to': caretaker, 'scheduled_time': task_times[1], 'status': 'in_progress', 'notes': ''},
            {'booking': bookings[0], 'service': services[0], 'assigned_to': caretaker, 'scheduled_time': task_times[2], 'status': 'pending'},
            {'booking': bookings[3], 'service': services[2], 'assigned_to': caretaker, 'scheduled_time': task_times[0], 'status': 'completed', 'notes': 'Прогулка прошла отлично'},
            {'booking': bookings[3], 'service': services[1], 'assigned_to': caretaker, 'scheduled_time': task_times[1], 'status': 'pending'},
            {'booking': bookings[3], 'service': services[6], 'assigned_to': caretaker, 'scheduled_time': task_times[4], 'status': 'pending'},
            {'booking': bookings[2], 'service': services[0], 'assigned_to': caretaker, 'scheduled_time': task_times[3], 'status': 'completed'},
            {'booking': bookings[1], 'service': services[2], 'assigned_to': caretaker, 'scheduled_time': task_times[4], 'status': 'pending'},
        ]
        for td in tasks_data:
            status = td.get('status', 'pending')
            t, created = Task.objects.get_or_create(
                booking=td['booking'], service=td.get('service'),
                scheduled_time=td['scheduled_time'],
                defaults={**td}
            )
            if created and status == 'completed':
                t.start_time = td['scheduled_time']
                t.end_time = td['scheduled_time'] + datetime.timedelta(minutes=30)
                t.save()

        self.stdout.write('Создание платежей...')
        payments_data = [
            {'booking': bookings[2], 'client': clients[1], 'amount': bookings[2].total_price, 'method': 'Карта', 'status': 'paid', 'days_ago': 8},
            {'booking': bookings[5], 'client': clients[0], 'amount': bookings[5].total_price, 'method': 'Наличные', 'status': 'paid', 'days_ago': 25},
            {'booking': bookings[0], 'client': clients[0], 'amount': bookings[0].total_price / 2, 'method': 'Карта', 'status': 'paid', 'days_ago': 3},
            {'booking': bookings[3], 'client': clients[1], 'amount': bookings[3].total_price, 'method': 'Переводом', 'status': 'pending', 'days_ago': 0},
            {'booking': bookings[1], 'client': clients[0], 'amount': bookings[1].total_price, 'method': 'Карта', 'status': 'unpaid', 'days_ago': 0},
        ]
        for pd in payments_data:
            days = pd.pop('days_ago', 0)
            method = pd.pop('method')
            status = pd.pop('status')
            pdate = now - datetime.timedelta(days=days) if days else None
            Payment.objects.get_or_create(
                booking=pd['booking'], client=pd['client'],
                defaults={**pd, 'payment_method': method, 'status': status, 'payment_date': pdate if status == 'paid' else None}
            )

        self.stdout.write(self.style.SUCCESS('\nДемонстрационные данные успешно созданы!'))
        self.stdout.write('\nТестовые аккаунты:')
        self.stdout.write('  Администратор: admin / admin123')
        self.stdout.write('  Менеджер:      manager / manager123')
        self.stdout.write('  Уходчик:       caretaker / care123')
        self.stdout.write('  Клиент:        client / client123')
