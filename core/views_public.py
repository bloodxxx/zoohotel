from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.utils import timezone
from .models import Room, RoomImage, Service, Booking, BookingService, Client, Animal, Payment, PasswordResetToken
from .forms import LoginForm, RegisterForm, GuestBookingForm
from .decorators import log_action
import secrets


def home(request):
    rooms = Room.objects.filter(status='available')[:3]
    services = Service.objects.filter(status='active')[:6]
    return render(request, 'public/home.html', {'rooms': rooms, 'services': services})


def rooms_list(request):
    rooms = Room.objects.exclude(status='maintenance')
    from itertools import groupby
    type_labels = dict(Room.TYPE_CHOICES)
    type_order = ['economy', 'standard', 'lux']
    grouped = []
    for t in type_order:
        group = [r for r in rooms if r.type == t]
        if group:
            grouped.append({'type': t, 'label': type_labels[t], 'rooms': group, 'count': len(group)})
    return render(request, 'public/rooms.html', {'rooms': rooms, 'grouped': grouped})


def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk, status__in=['available', 'occupied', 'booked'])
    images = room.images.all()
    return render(request, 'public/room_detail.html', {'room': room, 'images': images})


def services_list(request):
    services = Service.objects.filter(status='active')
    categories = services.values_list('category', flat=True).distinct()
    return render(request, 'public/services.html', {'services': services, 'categories': categories})


def booking_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'client_profile'):
        return redirect('cabinet_new_booking')

    rooms = Room.objects.filter(status='available')
    services = Service.objects.filter(status='active')

    if request.method == 'POST':
        form = GuestBookingForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # find or create client
            client, _ = Client.objects.get_or_create(
                email=cd['email'],
                defaults={'full_name': cd['full_name'], 'phone': cd['phone']}
            )
            if not _:
                client.full_name = cd['full_name']
                client.phone = cd['phone']
                client.save()
            # create animal
            animal = Animal.objects.create(
                client=client,
                name=cd['animal_name'],
                species=cd['animal_species'],
                breed=cd['animal_breed'],
                special_needs=cd.get('special_needs', ''),
            )
            room = cd['room']
            ci = cd['check_in_date']
            co = cd['check_out_date']
            nights = max((co - ci).days, 1)
            room_cost = room.price_per_day * nights
            services_sel = cd.get('services', [])
            svc_cost = sum(s.price * nights if s.is_daily else s.price for s in services_sel)
            total = room_cost + svc_cost
            booking = Booking.objects.create(
                client=client, animal=animal, room=room,
                check_in_date=ci, check_out_date=co,
                status='pending', total_price=total,
                created_by=request.user if request.user.is_authenticated else None,
            )
            for svc in services_sel:
                qty = nights if svc.is_daily else 1
                BookingService.objects.create(booking=booking, service=svc, quantity=qty, price=svc.price)
            Payment.objects.create(
                booking=booking,
                client=client,
                amount=total,
                payment_method='',
                status='unpaid',
            )
            log_action(request, 'Создано бронирование', 'Booking', booking.pk)
            request.session['last_booking_pk'] = booking.pk
            messages.success(request, f'Заявка на бронирование #{booking.pk} успешно создана! Статус: Ожидание.')
            return redirect('booking_success')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = GuestBookingForm()

    selected_room_id = request.GET.get('room', '')
    return render(request, 'public/booking.html', {
        'form': form,
        'rooms': rooms,
        'services': services,
        'selected_room_id': selected_room_id,
    })


def booking_success(request):
    PAYMENT_METHODS = [
        ('cash', 'Наличные при заезде'),
        ('card', 'Карта при заезде'),
    ]
    booking_pk = request.session.get('last_booking_pk')
    booking = None
    payment = None
    if booking_pk:
        try:
            booking = Booking.objects.select_related('client', 'animal', 'room').get(pk=booking_pk)
            payment = booking.payments.filter(status__in=['unpaid', 'pending']).first()
        except Booking.DoesNotExist:
            pass

    if request.method == 'POST' and payment:
        method = request.POST.get('payment_method', '')
        if method in dict(PAYMENT_METHODS):
            payment.payment_method = method
            payment.status = 'pending'
            payment.save(update_fields=['payment_method', 'status'])
            del request.session['last_booking_pk']
            return render(request, 'public/booking_success.html', {
                'booking': booking, 'payment': payment,
                'method_label': dict(PAYMENT_METHODS)[method],
                'done': True,
            })

    return render(request, 'public/booking_success.html', {
        'booking': booking,
        'payment': payment,
        'payment_methods': PAYMENT_METHODS,
        'done': False,
    })


def booking_pay_online(request, payment_pk):
    """Инициирует онлайн-оплату через ЮKassa для гостевого бронирования."""
    import uuid
    from yookassa import Configuration, Payment as YooPayment
    from django.conf import settings
    from django.urls import reverse

    payment = get_object_or_404(Payment, pk=payment_pk, status__in=['unpaid', 'pending'])
    booking = payment.booking

    if payment.amount != booking.total_price:
        payment.amount = booking.total_price
        payment.save(update_fields=['amount'])

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

    return_url = request.build_absolute_uri(
        reverse('booking_payment_return') + f'?payment_id={payment.pk}'
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

    return redirect(yoo_payment.confirmation.confirmation_url)


def booking_payment_return(request):
    """Страница возврата после оплаты через ЮKassa (для гостевых бронирований)."""
    from yookassa import Configuration, Payment as YooPayment
    from django.conf import settings
    from django.utils import timezone as tz

    payment_pk = request.GET.get('payment_id')
    payment = None
    if payment_pk:
        try:
            payment = Payment.objects.select_related('booking__animal', 'booking__room').get(pk=payment_pk)
            if payment.yookassa_payment_id and payment.status != 'paid':
                Configuration.account_id = settings.YOOKASSA_SHOP_ID
                Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
                try:
                    yoo = YooPayment.find_one(payment.yookassa_payment_id)
                    if yoo.status == 'succeeded':
                        payment.status = 'paid'
                        payment.payment_date = tz.now()
                        payment.transaction_id = yoo.id
                        payment.save(update_fields=['status', 'payment_date', 'transaction_id'])
                        booking = payment.booking
                        if booking.status == 'pending':
                            from .views_admin import _generate_tasks
                            booking.status = 'confirmed'
                            booking.save(update_fields=['status'])
                            _generate_tasks(booking)
                    elif yoo.status == 'canceled':
                        payment.status = 'failed'
                        payment.save(update_fields=['status'])
                except Exception:
                    pass
        except Payment.DoesNotExist:
            pass

    return render(request, 'public/booking_payment_return.html', {'payment': payment})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_blocked:
                messages.error(request, 'Ваш аккаунт заблокирован. Обратитесь к администратору.')
                return redirect('login')
            login(request, user)
            log_action(request, 'Вход в систему', result='ok')
            if user.role == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'caretaker':
                return redirect('caretaker_tasks')
            else:
                return redirect('cabinet_profile')
        else:
            messages.error(request, 'Неверный логин или пароль.')
    else:
        form = LoginForm(request)
    return render(request, 'public/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        from .models import CustomUser
        try:
            user = CustomUser.objects.get(email=email)
            token = secrets.token_urlsafe(32)
            PasswordResetToken.objects.create(user=user, token=token)
            reset_url = request.build_absolute_uri(f'/reset-password/{token}/')
            from django.core.mail import send_mail
            try:
                send_mail(
                    'Сброс пароля — ZooHotel',
                    f'Для сброса пароля перейдите по ссылке:\n{reset_url}\n\nСсылка действительна 24 часа.',
                    None,
                    [email],
                    fail_silently=False,
                )
            except Exception:
                pass
        except CustomUser.DoesNotExist:
            pass
        messages.success(request, 'Если аккаунт с таким email существует, инструкции по сбросу пароля отправлены.')
        return redirect('login')
    return render(request, 'public/password_reset_request.html')


def password_reset_confirm(request, token):
    reset = get_object_or_404(PasswordResetToken, token=token, used=False)
    import datetime
    if timezone.now() - reset.created_at > datetime.timedelta(hours=24):
        messages.error(request, 'Ссылка для сброса пароля устарела.')
        return redirect('login')
    if request.method == 'POST':
        p1 = request.POST.get('password1', '')
        p2 = request.POST.get('password2', '')
        if not p1 or p1 != p2:
            messages.error(request, 'Пароли не совпадают или пустые.')
        elif len(p1) < 8:
            messages.error(request, 'Пароль должен содержать минимум 8 символов.')
        else:
            reset.user.set_password(p1)
            reset.user.save()
            reset.used = True
            reset.save()
            messages.success(request, 'Пароль успешно изменён. Войдите с новым паролем.')
            return redirect('login')
    return render(request, 'public/password_reset_confirm.html', {'token': token})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать!')
            return redirect('cabinet_profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = RegisterForm()
    return render(request, 'public/register.html', {'form': form})
