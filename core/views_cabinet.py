import uuid
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone as tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import Booking, BookingService, Animal, AnimalDocument, Service, Room, Payment
from .forms import ClientBookingForm, AnimalForm, AnimalDocumentForm, ProfileForm, ClientForm
from .decorators import client_required, log_action


def get_client(request):
    return getattr(request.user, 'client_profile', None)


@client_required
def cabinet_profile(request):
    client = get_client(request)
    if request.method == 'POST':
        pform = ProfileForm(request.POST, instance=request.user)
        cform = ClientForm(request.POST, instance=client)
        if pform.is_valid() and cform.is_valid():
            pform.save()
            c = cform.save(commit=False)
            c.full_name = f'{request.user.first_name} {request.user.last_name}'.strip() or request.user.username
            c.email = request.user.email
            c.save()
            messages.success(request, 'Профиль успешно обновлён.')
            return redirect('cabinet_profile')
    else:
        pform = ProfileForm(instance=request.user)
        cform = ClientForm(instance=client)
    return render(request, 'cabinet/profile.html', {'pform': pform, 'cform': cform, 'client': client})


@client_required
def cabinet_change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успешно изменён.')
            return redirect('cabinet_profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'cabinet/change_password.html', {'form': form})


@client_required
def cabinet_animals(request):
    client = get_client(request)
    animals = client.animals.all() if client else []
    return render(request, 'cabinet/animals.html', {'animals': animals})


@client_required
def cabinet_animal_add(request):
    client = get_client(request)
    if request.method == 'POST':
        form = AnimalForm(request.POST)
        if form.is_valid():
            animal = form.save(commit=False)
            animal.client = client
            animal.save()
            messages.success(request, f'Животное «{animal.name}» добавлено.')
            return redirect('cabinet_animals')
    else:
        form = AnimalForm()
    return render(request, 'cabinet/animal_form.html', {'form': form, 'title': 'Добавить животное'})


@client_required
def cabinet_animal_edit(request, pk):
    client = get_client(request)
    animal = get_object_or_404(Animal, pk=pk, client=client)
    if request.method == 'POST':
        form = AnimalForm(request.POST, instance=animal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные животного обновлены.')
            return redirect('cabinet_animals')
    else:
        form = AnimalForm(instance=animal)
    return render(request, 'cabinet/animal_form.html', {'form': form, 'title': 'Редактировать животное', 'animal': animal})


@client_required
def cabinet_bookings(request):
    client = get_client(request)
    all_bookings = list(client.bookings.order_by('-check_in_date').prefetch_related('booking_services__service', 'tasks__service') if client else [])
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        from datetime import date as dt
        all_bookings = [b for b in all_bookings if b.check_in_date.date() >= dt.fromisoformat(date_from)]
    if date_to:
        from datetime import date as dt
        all_bookings = [b for b in all_bookings if b.check_in_date.date() <= dt.fromisoformat(date_to)]

    # Attach all task statuses to each booking for cabinet display
    for b in all_bookings:
        tasks_by_svc = {}
        base_tasks = []
        for t in b.tasks.all():
            if t.service_id:
                tasks_by_svc.setdefault(t.service_id, []).append(t.status)
            else:
                base_tasks.append(t)

        # Доп. услуги с прогрессом
        svc_statuses = []
        for bs in b.booking_services.select_related('service').all():
            statuses = tasks_by_svc.get(bs.service_id, [])
            total = len(statuses)
            done = statuses.count('completed')
            if total == 0:
                overall = 'pending'
            elif done == total:
                overall = 'completed'
            elif done > 0 or 'in_progress' in statuses:
                overall = 'in_progress'
            else:
                overall = 'pending'
            svc_statuses.append({
                'name': bs.service.name,
                'status': overall,
                'is_daily': bs.service.is_daily,
                'done': done,
                'total': total,
                'is_service': True,
            })

        # Базовые задачи (кормление, уборка) — группируем по названию
        base_grouped = {}
        for t in base_tasks:
            key = t.title
            base_grouped.setdefault(key, []).append(t.status)
        for title, statuses in base_grouped.items():
            total = len(statuses)
            done = statuses.count('completed')
            if total == 0:
                overall = 'pending'
            elif done == total:
                overall = 'completed'
            elif done > 0 or 'in_progress' in statuses:
                overall = 'in_progress'
            else:
                overall = 'pending'
            svc_statuses.append({
                'name': title,
                'status': overall,
                'is_daily': True,
                'done': done,
                'total': total,
                'is_service': False,
            })

        b.svc_statuses = svc_statuses

    active = [b for b in all_bookings if b.status in ('pending', 'confirmed')]
    archive = [b for b in all_bookings if b.status in ('completed', 'cancelled')]
    show_archive = request.GET.get('archive') == '1'
    return render(request, 'cabinet/bookings.html', {
        'bookings': archive if show_archive else active,
        'show_archive': show_archive,
        'active_count': len(active),
        'archive_count': len(archive),
        'date_from': date_from,
        'date_to': date_to,
    })


def _find_free_room(room_type, ci, co, exclude_booking_id=None):
    """Возвращает первый свободный номер выбранного класса или None."""
    rooms = Room.objects.filter(type=room_type, status='available').order_by('name')
    for room in rooms:
        if room.is_available_for(ci, co, exclude_booking_id=exclude_booking_id):
            return room
    return None


@client_required
def cabinet_new_booking(request):
    client = get_client(request)
    if not client:
        messages.error(request, 'Профиль клиента не найден.')
        return redirect('cabinet_profile')
    if not client.animals.exists():
        messages.warning(request, 'Сначала добавьте животное в личном кабинете.')
        return redirect('cabinet_animal_add')

    services = Service.objects.filter(status='active')
    room_types = [
        {'type': 'aviary', 'label': 'Вольер', 'count': Room.objects.filter(type='aviary', status='available').count()},
        {'type': 'standard', 'label': 'Стандарт', 'count': Room.objects.filter(type='standard', status='available').count()},
        {'type': 'lux', 'label': 'Люкс', 'count': Room.objects.filter(type='lux', status='available').count()},
    ]

    if request.method == 'POST':
        form = ClientBookingForm(client, request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            ci = cd['check_in_date']
            co = cd['check_out_date']
            room_type = cd['room_type']
            room = _find_free_room(room_type, ci, co)
            if not room:
                form.add_error('room_type', 'Нет свободных номеров выбранного класса на указанные даты.')
            else:
                nights = max((co - ci).days, 1)
                svc_list = cd.get('services', [])
                svc_cost = sum(s.price * nights if s.is_daily else s.price for s in svc_list)
                total = room.price_per_day * nights + svc_cost
                booking = Booking.objects.create(
                    client=client, animal=cd['animal'], room=room,
                    check_in_date=ci, check_out_date=co,
                    status='pending', total_price=total,
                    notes=cd.get('notes', ''),
                    created_by=request.user,
                )
                for svc in svc_list:
                    qty = nights if svc.is_daily else 1
                    BookingService.objects.create(booking=booking, service=svc, quantity=qty, price=svc.price)
                Payment.objects.create(
                    booking=booking, client=client,
                    amount=total,
                    payment_method='', status='unpaid',
                )
                log_action(request, 'Создано бронирование', 'Booking', booking.pk)
                messages.success(request, f'Бронирование #{booking.pk} создано — {room.name}. К оплате: {int(total)} ₽.')
                return redirect('cabinet_bookings')
        if not form.is_valid() or form.errors:
            messages.error(request, 'Исправьте ошибки в форме.')
    else:
        form = ClientBookingForm(client)

    return render(request, 'cabinet/new_booking.html', {
        'form': form, 'services': services, 'room_types': room_types,
    })


@client_required
def cabinet_rebook(request, pk):
    client = get_client(request)
    original = get_object_or_404(Booking, pk=pk, client=client)
    from django.utils import timezone as tz
    import datetime

    services = Service.objects.filter(status='active')
    room_types = [
        {'type': 'aviary', 'label': 'Вольер', 'count': Room.objects.filter(type='aviary', status='available').count()},
        {'type': 'standard', 'label': 'Стандарт', 'count': Room.objects.filter(type='standard', status='available').count()},
        {'type': 'lux', 'label': 'Люкс', 'count': Room.objects.filter(type='lux', status='available').count()},
    ]

    if request.method == 'POST':
        form = ClientBookingForm(client, request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            ci = cd['check_in_date']
            co = cd['check_out_date']
            room_type = cd['room_type']
            room = _find_free_room(room_type, ci, co)
            if not room:
                form.add_error('room_type', 'Нет свободных номеров выбранного класса на указанные даты.')
            else:
                nights = max((co - ci).days, 1)
                svc_list = cd.get('services', [])
                svc_cost = sum(s.price * nights if s.is_daily else s.price for s in svc_list)
                total = room.price_per_day * nights + svc_cost
                booking = Booking.objects.create(
                    client=client, animal=cd['animal'], room=room,
                    check_in_date=ci, check_out_date=co,
                    status='pending', total_price=total,
                    notes=cd.get('notes', ''),
                    created_by=request.user,
                )
                for svc in svc_list:
                    qty = nights if svc.is_daily else 1
                    BookingService.objects.create(booking=booking, service=svc, quantity=qty, price=svc.price)
                Payment.objects.create(
                    booking=booking, client=client,
                    amount=total,
                    payment_method='', status='unpaid',
                )
                log_action(request, f'Повторное бронирование на основе #{pk}', 'Booking', booking.pk)
                messages.success(request, f'Бронирование #{booking.pk} создано. Статус: Ожидание.')
                return redirect('cabinet_bookings')
        return render(request, 'cabinet/new_booking.html', {
            'form': form, 'services': services, 'room_types': room_types, 'rebook': True,
        })

    service_ids = list(original.booking_services.values_list('service_id', flat=True))
    ci = tz.now().strftime('%Y-%m-%d %H:%M')
    co = (tz.now() + datetime.timedelta(days=original.nights())).strftime('%Y-%m-%d %H:%M')
    initial = {
        'animal': original.animal,
        'room_type': original.room.type,
        'check_in_date': ci,
        'check_out_date': co,
        'services': service_ids,
        'notes': original.notes,
    }
    form = ClientBookingForm(client, initial=initial)
    return render(request, 'cabinet/new_booking.html', {
        'form': form, 'services': services, 'room_types': room_types, 'rebook': True,
        'rebook_service_ids': service_ids,
        'rebook_ci': ci, 'rebook_co': co,
    })


PAYMENT_METHODS = [
    ('cash', 'Наличные при заезде'),
    ('card', 'Карта при заезде'),
]


@client_required
def cabinet_booking_delete(request, pk):
    import datetime
    client = get_client(request)
    booking = get_object_or_404(Booking, pk=pk, client=client)
    if request.method == 'POST':
        if booking.status in ('pending', 'confirmed'):
            paid_payment = booking.payments.filter(status='paid').first()
            check_in_today = booking.check_in_date.date() == tz.localtime(tz.now()).date()

            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
            log_action(request, f'Клиент отменил бронирование #{pk}', 'Booking', pk)

            if paid_payment:
                if check_in_today:
                    penalty = booking.room.price_per_day
                    messages.warning(
                        request,
                        f'Бронирование #{pk} отменено. Так как заезд был запланирован на сегодня, '
                        f'удерживается стоимость 1 суток ({int(penalty)} ₽). '
                        f'Остаток будет возвращён в течение 30 дней.'
                    )
                else:
                    messages.warning(
                        request,
                        f'Бронирование #{pk} отменено. Возврат средств будет произведён в течение 30 дней.'
                    )
            else:
                messages.success(request, f'Бронирование #{pk} отменено.')
        else:
            messages.error(request, 'Невозможно отменить бронирование с текущим статусом.')
    return redirect('cabinet_bookings')


@client_required
def cabinet_animal_delete(request, pk):
    client = get_client(request)
    animal = get_object_or_404(Animal, pk=pk, client=client)
    if request.method == 'POST':
        if animal.bookings.exists():
            messages.error(request, 'Нельзя удалить животное с историей бронирований.')
        else:
            name = animal.name
            animal.delete()
            messages.success(request, f'Животное «{name}» удалено.')
    return redirect('cabinet_animals')


def api_available_rooms(request):
    room_type = request.GET.get('type', '')
    check_in = request.GET.get('check_in', '')
    check_out = request.GET.get('check_out', '')

    rooms = Room.objects.filter(status='available')
    if room_type:
        rooms = rooms.filter(type=room_type)

    ci = co = None
    if check_in and check_out:
        from django.utils.dateparse import parse_datetime
        ci = parse_datetime(check_in)
        co = parse_datetime(check_out)

    if ci and co and ci < co:
        free_room = None
        for room in rooms:
            if room.is_available_for(ci, co):
                free_room = room
                break
        if free_room:
            return JsonResponse({'available': True, 'room_name': free_room.name, 'price': str(free_room.price_per_day)})
        return JsonResponse({'available': False})

    total = rooms.count()
    return JsonResponse({'available': total > 0, 'total': total})


@client_required
def cabinet_pay_yookassa(request, booking_pk):
    """Инициирует онлайн-оплату через ЮKassa и перенаправляет на страницу оплаты."""
    from yookassa import Configuration, Payment as YooPayment

    client = get_client(request)
    booking = get_object_or_404(Booking, pk=booking_pk, client=client)
    payment = booking.payments.filter(status__in=['unpaid', 'pending']).first()
    if not payment:
        messages.info(request, 'Нет активного платежа для этого бронирования.')
        return redirect('cabinet_bookings')

    # Всегда синхронизируем сумму платежа с актуальной стоимостью бронирования
    if payment.amount != booking.total_price:
        payment.amount = booking.total_price
        payment.save(update_fields=['amount'])

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

    return_url = request.build_absolute_uri(
        reverse('payment_return') + f'?payment_id={payment.pk}'
    )

    yoo_payment = YooPayment.create({
        'amount': {
            'value': f'{payment.amount:.2f}',
            'currency': 'RUB',
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': return_url,
        },
        'capture': True,
        'description': f'Оплата бронирования #{booking.pk} — {booking.animal.name}',
        'metadata': {
            'payment_db_id': str(payment.pk),
            'booking_id': str(booking.pk),
        },
    }, idempotency_key=str(uuid.uuid4()))

    payment.yookassa_payment_id = yoo_payment.id
    payment.payment_method = 'online'
    payment.status = 'pending'
    payment.save(update_fields=['yookassa_payment_id', 'payment_method', 'status'])

    log_action(request, 'Инициирована онлайн-оплата ЮKassa', 'Payment', payment.pk)
    return redirect(yoo_payment.confirmation.confirmation_url)


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """Получает уведомления от ЮKassa об изменении статуса платежа."""
    from yookassa import Configuration
    from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotificationFactory

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

    try:
        body = json.loads(request.body)
        notification = WebhookNotificationFactory().create(body)
        yoo_obj = notification.object

        payment = Payment.objects.filter(yookassa_payment_id=yoo_obj.id).first()
        if payment:
            if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
                payment.status = 'paid'
                payment.payment_date = tz.now()
                payment.transaction_id = yoo_obj.id
                payment.save(update_fields=['status', 'payment_date', 'transaction_id'])
                # Авто-подтверждение бронирования при успешной онлайн-оплате
                booking = payment.booking
                if booking.status == 'pending':
                    from .views_admin import _generate_tasks
                    booking.status = 'confirmed'
                    booking.save(update_fields=['status'])
                    _generate_tasks(booking)
            elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
                payment.status = 'failed'
                payment.save(update_fields=['status'])
    except Exception:
        pass

    return JsonResponse({'status': 'ok'})


@client_required
def payment_return(request):
    """Страница возврата после оплаты через ЮKassa."""
    from yookassa import Configuration, Payment as YooPayment

    payment_db_id = request.GET.get('payment_id')
    payment = None
    if payment_db_id:
        client = get_client(request)
        payment = Payment.objects.filter(pk=payment_db_id, client=client).first()

        if payment and payment.yookassa_payment_id and payment.status != 'paid':
            Configuration.account_id = settings.YOOKASSA_SHOP_ID
            Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
            try:
                yoo_payment = YooPayment.find_one(payment.yookassa_payment_id)
                if yoo_payment.status == 'succeeded':
                    payment.status = 'paid'
                    payment.payment_date = tz.now()
                    payment.transaction_id = yoo_payment.id
                    payment.save(update_fields=['status', 'payment_date', 'transaction_id'])
                    booking = payment.booking
                    if booking.status == 'pending':
                        from .views_admin import _generate_tasks
                        booking.status = 'confirmed'
                        booking.save(update_fields=['status'])
                        _generate_tasks(booking)
                elif yoo_payment.status == 'canceled':
                    payment.status = 'failed'
                    payment.save(update_fields=['status'])
            except Exception:
                pass

    return render(request, 'cabinet/payment_return.html', {'payment': payment})


@client_required
def cabinet_pay(request, booking_pk):
    client = get_client(request)
    booking = get_object_or_404(Booking, pk=booking_pk, client=client)
    payment = booking.payments.filter(status__in=['unpaid', 'pending']).first()
    if not payment:
        messages.info(request, 'Нет активного платежа для этого бронирования.')
        return redirect('cabinet_bookings')
    if request.method == 'POST':
        method = request.POST.get('payment_method', '')
        if method not in dict(PAYMENT_METHODS):
            messages.error(request, 'Выберите способ оплаты.')
        else:
            payment.payment_method = method
            payment.status = 'pending'
            payment.save(update_fields=['payment_method', 'status'])
            log_action(request, 'Клиент выбрал способ оплаты', 'Payment', payment.pk)
            messages.success(request, 'Способ оплаты выбран. Администратор подтвердит оплату.')
            return redirect('cabinet_bookings')
    return render(request, 'cabinet/pay.html', {
        'booking': booking,
        'payment': payment,
        'payment_methods': PAYMENT_METHODS,
    })
