from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
import datetime, openpyxl
from .models import (Booking, BookingService, Client, Animal, AnimalDocument,
                     Room, RoomImage, Service, Task, Payment, CustomUser, Log)
from .forms import (AdminBookingForm, ClientForm, AnimalForm, AnimalDocumentForm,
                    RoomForm, RoomImageForm, ServiceForm, TaskForm, PaymentForm, StaffForm)
from .decorators import admin_or_manager, admin_only, log_action


@admin_or_manager
def dashboard(request):
    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.datetime.combine(today, datetime.time.min))
    today_end = timezone.make_aware(datetime.datetime.combine(today, datetime.time.max))

    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='available').count()
    occupied = Booking.objects.filter(
        status__in=['confirmed', 'pending'],
        check_in_date__lte=today_end,
        check_out_date__gte=today_start
    ).count()

    today_checkins = Booking.objects.filter(
        check_in_date__date=today,
        status__in=['confirmed', 'pending']
    ).select_related('client', 'animal', 'room')

    pending_bookings = Booking.objects.filter(status='pending').count()
    active_tasks = Task.objects.filter(status__in=['pending', 'in_progress']).count()

    revenue_today = Payment.objects.filter(
        status='paid'
    ).filter(
        Q(payment_date__date=today) | Q(payment_date__isnull=True, created_at__date=today)
    ).aggregate(total=Sum('amount'))['total'] or 0

    revenue_month = Payment.objects.filter(
        status='paid'
    ).filter(
        Q(payment_date__year=today.year, payment_date__month=today.month) |
        Q(payment_date__isnull=True, created_at__year=today.year, created_at__month=today.month)
    ).aggregate(total=Sum('amount'))['total'] or 0

    recent_bookings = Booking.objects.select_related('client', 'animal', 'room').order_by('-created_at')[:5]

    occupancy = round(occupied / total_rooms * 100) if total_rooms else 0

    return render(request, 'admin_panel/dashboard.html', {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied': occupied,
        'occupancy': occupancy,
        'today_checkins': today_checkins,
        'pending_bookings': pending_bookings,
        'active_tasks': active_tasks,
        'revenue_today': revenue_today,
        'revenue_month': revenue_month,
        'recent_bookings': recent_bookings,
    })


# ── BOOKINGS ──
@admin_or_manager
def bookings_list(request):
    qs = Booking.objects.select_related('client', 'animal', 'room').order_by('-check_in_date')
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if q:
        qs = qs.filter(Q(client__full_name__icontains=q) | Q(animal__name__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(check_in_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(check_out_date__date__lte=date_to)
    return render(request, 'admin_panel/bookings.html', {
        'bookings': qs, 'q': q, 'status_filter': status,
        'date_from': date_from, 'date_to': date_to,
        'status_choices': Booking.STATUS_CHOICES,
    })


@admin_or_manager
def booking_detail(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    tasks = booking.tasks.select_related('assigned_to', 'service')
    payments = booking.payments.all()
    return render(request, 'admin_panel/booking_detail.html', {
        'booking': booking, 'tasks': tasks, 'payments': payments
    })


@admin_or_manager
def booking_create(request):
    if request.method == 'POST':
        form = AdminBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.created_by = request.user
            ci = booking.check_in_date
            co = booking.check_out_date
            nights = max((co - ci).days, 1)
            svc_list = form.cleaned_data.get('services', [])
            booking.total_price = booking.room.price_per_day * nights + sum(s.price for s in svc_list)
            booking.save()
            for svc in svc_list:
                BookingService.objects.create(booking=booking, service=svc, quantity=1, price=svc.price)
            Payment.objects.create(
                booking=booking, client=booking.client,
                amount=booking.room.price_per_day,
                payment_method='', status='unpaid',
            )
            log_action(request, 'Создано бронирование', 'Booking', booking.pk)
            messages.success(request, f'Бронирование #{booking.pk} создано.')
            return redirect('booking_detail', pk=booking.pk)
    else:
        form = AdminBookingForm()
    return render(request, 'admin_panel/booking_form.html', {'form': form, 'title': 'Новое бронирование'})


@admin_or_manager
def booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        form = AdminBookingForm(request.POST, instance=booking)
        if form.is_valid():
            b = form.save(commit=False)
            nights = max((b.check_out_date - b.check_in_date).days, 1)
            svc_list = form.cleaned_data.get('services', [])
            b.total_price = b.room.price_per_day * nights + sum(s.price for s in svc_list)
            b.save()
            BookingService.objects.filter(booking=booking).delete()
            for svc in svc_list:
                BookingService.objects.create(booking=booking, service=svc, quantity=1, price=svc.price)
            log_action(request, 'Изменено бронирование', 'Booking', booking.pk)
            messages.success(request, 'Бронирование обновлено.')
            return redirect('booking_detail', pk=pk)
    else:
        existing_svcs = list(booking.booking_services.values_list('service_id', flat=True))
        form = AdminBookingForm(instance=booking, initial={'services': existing_svcs})
    return render(request, 'admin_panel/booking_form.html', {
        'form': form, 'title': 'Редактировать бронирование', 'booking': booking,
        'selected_service_ids': list(booking.booking_services.values_list('service_id', flat=True)),
    })


@admin_or_manager
def booking_status(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(Booking.STATUS_CHOICES):
        old = booking.get_status_display()
        booking.status = new_status
        booking.save(update_fields=['status'])
        log_action(request, f'Статус брони #{pk} изменён на {new_status}', 'Booking', pk)
        messages.success(request, f'Статус изменён: {old} → {booking.get_status_display()}')
        if new_status == 'confirmed':
            prepayment = booking.payments.filter(status='unpaid').first()
            if prepayment:
                prepayment.amount = booking.total_price
                prepayment.status = 'pending'
                prepayment.save(update_fields=['amount', 'status'])
            elif not booking.payments.exists():
                Payment.objects.create(
                    booking=booking,
                    client=booking.client,
                    amount=booking.total_price,
                    payment_method='',
                    status='pending',
                )
            _generate_tasks(booking)
    return redirect('booking_detail', pk=pk)


def _generate_tasks(booking):
    caretaker = CustomUser.objects.filter(role='caretaker').first()
    if not caretaker:
        return
    if booking.tasks.exists():
        return

    ci = booking.check_in_date
    co = booking.check_out_date

    base_tasks = [
        (8, 0, 'Утреннее кормление'),
        (10, 0, 'Уборка вольера'),
        (13, 0, 'Дневное кормление'),
        (18, 0, 'Вечернее кормление'),
    ]

    tasks = []
    day = ci.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < co:
        for hour, minute, title in base_tasks:
            scheduled = day.replace(hour=hour, minute=minute)
            if scheduled >= ci and scheduled < co:
                tasks.append(Task(
                    booking=booking,
                    assigned_to=caretaker,
                    title=title,
                    scheduled_time=scheduled,
                    status='pending',
                ))
        day += datetime.timedelta(days=1)

    # Доп. услуги: выгул — каждый день, остальные (груминг и т.д.) — 1 раз
    for bs in booking.booking_services.select_related('service').all():
        svc_name_lower = bs.service.name.lower()
        is_daily = 'выгул' in svc_name_lower or 'walk' in svc_name_lower

        if is_daily:
            day = ci.replace(hour=0, minute=0, second=0, microsecond=0)
            while day < co:
                scheduled = day.replace(hour=11, minute=0, second=0, microsecond=0)
                if scheduled >= ci and scheduled < co:
                    tasks.append(Task(
                        booking=booking,
                        assigned_to=caretaker,
                        service=bs.service,
                        title=bs.service.name,
                        instructions=f'Доп. услуга для {booking.animal.name}',
                        scheduled_time=scheduled,
                        status='pending',
                    ))
                day += datetime.timedelta(days=1)
        else:
            # Один раз — в первый день в 11:00
            scheduled = ci.replace(hour=11, minute=0, second=0, microsecond=0)
            if scheduled < ci:
                scheduled += datetime.timedelta(days=1)
            tasks.append(Task(
                booking=booking,
                assigned_to=caretaker,
                service=bs.service,
                title=bs.service.name,
                instructions=f'Доп. услуга для {booking.animal.name}',
                scheduled_time=scheduled,
                status='pending',
            ))

    # bulk_create обходит Task.save(), поэтому период и согласованное
    # с временем название проставляем вручную.
    for t in tasks:
        t.period = Task.period_for_hour(timezone.localtime(t.scheduled_time).hour)
        t.title = t.synced_title()

    Task.objects.bulk_create(tasks)


@admin_only
def booking_delete(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        log_action(request, f'Удалено бронирование #{pk}', 'Booking', pk)
        booking.payments.all().delete()
        booking.tasks.all().delete()
        booking.booking_services.all().delete()
        booking.delete()
        messages.success(request, f'Бронирование #{pk} удалено.')
        return redirect('bookings_admin')
    return redirect('booking_detail', pk=pk)


@admin_or_manager
def payment_mark_paid(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        method = request.POST.get('payment_method', '').strip()
        payment.payment_method = method
        payment.status = 'paid'
        payment.payment_date = timezone.now()
        payment.save(update_fields=['payment_method', 'status', 'payment_date'])
        log_action(request, f'Платёж #{pk} отмечен оплаченным', 'Payment', pk)
        messages.success(request, f'Платёж #{pk} отмечен как оплаченный.')
    return redirect('booking_detail', pk=payment.booking_id)


# ── CLIENTS ──
@admin_or_manager
def clients_list(request):
    qs = Client.objects.all()
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    return render(request, 'admin_panel/clients.html', {'clients': qs, 'q': q})


@admin_or_manager
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные клиента обновлены.')
            return redirect('client_detail', pk=pk)
    else:
        form = ClientForm(instance=client)
    return render(request, 'admin_panel/client_detail.html', {
        'client': client, 'form': form,
        'animals': client.animals.all(),
        'bookings': client.bookings.order_by('-created_at')[:10],
    })


# ── ANIMALS ──
@admin_or_manager
def animals_list(request):
    qs = Animal.objects.select_related('client').all()
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(client__full_name__icontains=q))
    return render(request, 'admin_panel/animals.html', {'animals': qs, 'q': q})


@admin_or_manager
def animal_detail(request, pk):
    animal = get_object_or_404(Animal, pk=pk)
    if request.method == 'POST':
        form = AnimalForm(request.POST, instance=animal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Карточка животного обновлена.')
            return redirect('animal_detail', pk=pk)
    else:
        form = AnimalForm(instance=animal)
    doc_form = AnimalDocumentForm()
    return render(request, 'admin_panel/animal_detail.html', {
        'animal': animal, 'form': form, 'doc_form': doc_form,
        'documents': animal.documents.all(),
    })


@admin_or_manager
def animal_document_upload(request, pk):
    animal = get_object_or_404(Animal, pk=pk)
    if request.method == 'POST':
        form = AnimalDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.animal = animal
            doc.save()
            messages.success(request, 'Документ загружен.')
    return redirect('animal_detail', pk=pk)


# ── ROOMS ──
@admin_only
def rooms_list_admin(request):
    rooms = Room.objects.all()
    return render(request, 'admin_panel/rooms.html', {'rooms': rooms})


@admin_only
def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            room = form.save()
            messages.success(request, f'Номер «{room.name}» добавлен.')
            return redirect('rooms_admin')
    else:
        form = RoomForm()
    return render(request, 'admin_panel/room_form.html', {'form': form, 'title': 'Добавить номер'})


@admin_only
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'Номер обновлён.')
            return redirect('rooms_admin')
    else:
        form = RoomForm(instance=room)
    images = room.images.all()
    return render(request, 'admin_panel/room_form.html', {'form': form, 'title': 'Редактировать номер', 'room': room, 'images': images, 'img_form': RoomImageForm()})


@admin_only
def room_delete(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        has_active = Booking.objects.filter(room=room, status__in=['pending', 'confirmed']).exists()
        if has_active:
            messages.error(request, 'Нельзя удалить номер с активными бронированиями.')
        else:
            room.delete()
            messages.success(request, 'Номер удалён.')
    return redirect('rooms_admin')


# ── ROOM IMAGES ──
@admin_only
def room_image_upload(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomImageForm(request.POST, request.FILES)
        if form.is_valid():
            img = form.save(commit=False)
            img.room = room
            img.save()
            messages.success(request, 'Фото добавлено.')
        else:
            messages.error(request, 'Ошибка загрузки фото.')
    return redirect('room_edit', pk=pk)


@admin_only
def room_image_delete(request, pk):
    img = get_object_or_404(RoomImage, pk=pk)
    room_pk = img.room_id
    img.image.delete(save=False)
    img.delete()
    messages.success(request, 'Фото удалено.')
    return redirect('room_edit', pk=room_pk)


# ── SERVICES ──
@admin_or_manager
def services_list_admin(request):
    services = Service.objects.all()
    return render(request, 'admin_panel/services.html', {'services': services})


@admin_or_manager
def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            svc = form.save()
            messages.success(request, f'Услуга «{svc.name}» добавлена.')
            return redirect('services_admin')
    else:
        form = ServiceForm()
    return render(request, 'admin_panel/service_form.html', {'form': form, 'title': 'Добавить услугу'})


@admin_or_manager
def service_edit(request, pk):
    svc = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=svc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Услуга обновлена.')
            return redirect('services_admin')
    else:
        form = ServiceForm(instance=svc)
    return render(request, 'admin_panel/service_form.html', {'form': form, 'title': 'Редактировать услугу', 'svc': svc})


# ── TASKS ──
@admin_or_manager
def tasks_list(request):
    qs = Task.objects.select_related('booking__animal', 'assigned_to', 'service').order_by('-booking__check_in_date', 'scheduled_time')
    status = request.GET.get('status', '')
    date = request.GET.get('date', '')
    show_archive = request.GET.get('archive') == '1'
    if status:
        qs = qs.filter(status=status)
    elif not show_archive:
        qs = qs.exclude(status='completed')
    if date:
        qs = qs.filter(scheduled_time__date=date)
    return render(request, 'admin_panel/tasks.html', {
        'tasks': qs, 'status_filter': status, 'date_filter': date,
        'status_choices': Task.STATUS_CHOICES,
        'show_archive': show_archive,
    })


@admin_or_manager
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            entered_title = form.cleaned_data.get('title', '')
            task = form.save()
            if task.title != entered_title:
                messages.info(request, f'Название согласовано с временем: «{task.title}».')
            messages.success(request, f'Задача #{task.pk} создана.')
            return redirect('tasks_admin')
    else:
        form = TaskForm()
    return render(request, 'admin_panel/task_form.html', {'form': form, 'title': 'Новая задача'})


@admin_or_manager
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            entered_title = form.cleaned_data.get('title', '')
            task = form.save()
            if task.title != entered_title:
                messages.info(request, f'Название согласовано с временем: «{task.title}».')
            messages.success(request, 'Задача обновлена.')
            return redirect('tasks_admin')
    else:
        form = TaskForm(instance=task)
    return render(request, 'admin_panel/task_form.html', {'form': form, 'title': 'Редактировать задачу', 'task': task})


# ── PAYMENTS ──
@admin_or_manager
def payments_list(request):
    qs = Payment.objects.select_related('booking', 'client').order_by('-created_at')
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(payment_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(payment_date__date__lte=date_to)
    total = qs.filter(status='paid').aggregate(t=Sum('amount'))['t'] or 0
    return render(request, 'admin_panel/payments.html', {
        'payments': qs, 'status_filter': status,
        'date_from': date_from, 'date_to': date_to,
        'status_choices': Payment.STATUS_CHOICES, 'total': total,
    })


@admin_or_manager
def payment_create(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            p = form.save()
            log_action(request, 'Создан платёж', 'Payment', p.pk)
            messages.success(request, f'Платёж #{p.pk} добавлен.')
            return redirect('payments_admin')
    else:
        form = PaymentForm()
    return render(request, 'admin_panel/payment_form.html', {'form': form, 'title': 'Новый платёж'})


@admin_or_manager
def payment_edit(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            log_action(request, 'Изменён платёж', 'Payment', pk)
            messages.success(request, 'Платёж обновлён.')
            return redirect('payments_admin')
    else:
        form = PaymentForm(instance=payment)
    return render(request, 'admin_panel/payment_form.html', {'form': form, 'title': 'Редактировать платёж', 'payment': payment})


# ── STAFF ──
@admin_only
def staff_list(request):
    staff = CustomUser.objects.filter(role__in=['admin', 'caretaker'])
    return render(request, 'admin_panel/staff.html', {'staff': staff})


@admin_only
def staff_create(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            u = form.save()
            messages.success(request, f'Сотрудник «{u.get_full_name() or u.username}» добавлен.')
            return redirect('staff_admin')
    else:
        form = StaffForm()
    return render(request, 'admin_panel/staff_form.html', {'form': form, 'title': 'Добавить сотрудника'})


@admin_only
def staff_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные сотрудника обновлены.')
            return redirect('staff_admin')
    else:
        form = StaffForm(instance=user)
    return render(request, 'admin_panel/staff_form.html', {'form': form, 'title': 'Редактировать сотрудника', 'staff_user': user})


@admin_only
def staff_toggle_block(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user.is_blocked = not user.is_blocked
        user.save(update_fields=['is_blocked'])
        action = 'заблокирован' if user.is_blocked else 'разблокирован'
        log_action(request, f'Сотрудник {user.username} {action}', 'CustomUser', pk)
        messages.success(request, f'Сотрудник {action}.')
    return redirect('staff_admin')


# ── REPORTS ──
@admin_or_manager
def reports(request):
    today = timezone.now().date()
    date_from = request.GET.get('date_from', '') or (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    date_to = request.GET.get('date_to', '') or today.strftime('%Y-%m-%d')
    report_type = request.GET.get('report_type', 'financial')

    ctx = {'date_from': date_from, 'date_to': date_to, 'report_type': report_type}

    if report_type == 'financial':
        payments = Payment.objects.filter(
            payment_date__date__gte=date_from,
            payment_date__date__lte=date_to
        ).select_related('booking', 'client')
        total = payments.filter(status='paid').aggregate(t=Sum('amount'))['t'] or 0
        ctx.update({'payments': payments, 'total': total})

    elif report_type == 'occupancy':
        rooms = Room.objects.all()
        room_data = []
        for room in rooms:
            bookings = Booking.objects.filter(
                room=room,
                status__in=['confirmed', 'completed'],
                check_in_date__date__gte=date_from,
                check_out_date__date__lte=date_to,
            )
            days = sum(b.nights() for b in bookings)
            period_days = (datetime.date.fromisoformat(date_to) - datetime.date.fromisoformat(date_from)).days + 1
            pct = round(days / period_days * 100) if period_days else 0
            room_data.append({'room': room, 'days': days, 'pct': pct})
        ctx['room_data'] = room_data

    elif report_type == 'staff':
        staff_data = []
        for user in CustomUser.objects.filter(role__in=['caretaker', 'admin']):
            tasks_qs = Task.objects.filter(
                assigned_to=user,
                scheduled_time__date__gte=date_from,
                scheduled_time__date__lte=date_to,
            )
            total_t = tasks_qs.count()
            done = tasks_qs.filter(status='completed').count()
            staff_data.append({'user': user, 'total': total_t, 'done': done, 'pending': total_t - done})
        ctx['staff_data'] = staff_data

    elif report_type == 'animals':
        animals = Animal.objects.filter(
            bookings__check_in_date__date__gte=date_from,
            bookings__check_in_date__date__lte=date_to,
        ).distinct().select_related('client')
        ctx['animals'] = animals

    return render(request, 'admin_panel/reports.html', ctx)


@admin_or_manager
def reports_export(request):
    import datetime as dt
    today = timezone.now().date()
    date_from = request.GET.get('date_from', '') or (today - dt.timedelta(days=30)).strftime('%Y-%m-%d')
    date_to = request.GET.get('date_to', '') or today.strftime('%Y-%m-%d')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Финансовый отчёт'
    ws.append(['Дата', 'Бронь №', 'Клиент', 'Сумма', 'Статус', 'Способ оплаты'])

    payments = Payment.objects.filter(
        payment_date__date__gte=date_from,
        payment_date__date__lte=date_to,
    ).select_related('booking', 'client')
    for p in payments:
        ws.append([
            p.payment_date.strftime('%d.%m.%Y %H:%M') if p.payment_date else '—',
            f'#{p.booking.pk}',
            p.client.full_name,
            float(p.amount),
            p.get_status_display(),
            p.payment_method,
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="report_{date_from}_{date_to}.xlsx"'
    wb.save(response)
    return response


@admin_or_manager
def logs_list(request):
    logs = Log.objects.select_related('user').order_by('-created_at')[:200]
    return render(request, 'admin_panel/logs.html', {'logs': logs})


@admin_or_manager
def api_client_animals(request):
    client_id = request.GET.get('client_id', '')
    if not client_id:
        return JsonResponse({'animals': []})
    animals = Animal.objects.filter(client_id=client_id).values('id', 'name', 'species')
    result = [{'id': a['id'], 'name': f"{a['name']} ({dict(Animal.SPECIES_CHOICES).get(a['species'], a['species'])})"} for a in animals]
    return JsonResponse({'animals': result})
