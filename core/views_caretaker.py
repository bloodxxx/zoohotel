from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Task
from .decorators import caretaker_required, log_action


@caretaker_required
def caretaker_tasks(request):
    today = timezone.now().date()
    tasks = Task.objects.filter(
        assigned_to=request.user,
    ).select_related('booking__animal__client', 'booking__room', 'service').prefetch_related('booking__booking_services__service').order_by('scheduled_time')

    if 'date' in request.GET:
        date_filter = request.GET.get('date', '')
        if date_filter:
            request.session['caretaker_date_filter'] = date_filter
        else:
            request.session.pop('caretaker_date_filter', None)
    else:
        date_filter = request.session.get('caretaker_date_filter', today.strftime('%Y-%m-%d'))

    if date_filter:
        tasks = tasks.filter(scheduled_time__date=date_filter)

    status_filter = request.GET.get('status', '')
    counts = {
        'pending': tasks.filter(status='pending').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'completed': tasks.filter(status='completed').count(),
    }
    if status_filter in ('pending', 'completed'):
        tasks = tasks.filter(status=status_filter)

    return render(request, 'caretaker/tasks.html', {
        'tasks': tasks,
        'today': today,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'count_pending': counts['pending'],
        'count_in_progress': counts['in_progress'],
        'count_completed': counts['completed'],
    })


@caretaker_required
def task_start(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    date_param = request.POST.get('date', '')
    status_param = request.POST.get('status_filter', '')
    if request.method == 'POST' and task.status == 'pending':
        task.status = 'in_progress'
        task.start_time = timezone.now()
        task.save(update_fields=['status', 'start_time'])
        messages.success(request, 'Задача начата.')
    url = redirect('caretaker_tasks').url
    params = []
    if date_param: params.append(f'date={date_param}')
    if status_param: params.append(f'status={status_param}')
    return redirect(f"{url}?{'&'.join(params)}" if params else url)


@caretaker_required
def task_complete(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    date_param = request.POST.get('date', '')
    status_param = request.POST.get('status_filter', '')
    if request.method == 'POST' and task.status in ('pending', 'in_progress'):
        task.status = 'completed'
        task.end_time = timezone.now()
        notes = request.POST.get('notes', '')
        if notes:
            task.notes = notes
        task.save(update_fields=['status', 'end_time', 'notes'])
        messages.success(request, 'Задача выполнена.')
    url = redirect('caretaker_tasks').url
    params = []
    if date_param: params.append(f'date={date_param}')
    if status_param: params.append(f'status={status_param}')
    return redirect(f"{url}?{'&'.join(params)}" if params else url)


@caretaker_required
def task_note(request, pk):
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    date_param = request.POST.get('date', '')
    if request.method == 'POST':
        task.notes = request.POST.get('notes', task.notes)
        task.save(update_fields=['notes'])
        messages.success(request, 'Заметка сохранена.')
    if date_param:
        return redirect(f"{redirect('caretaker_tasks').url}?date={date_param}")
    return redirect('caretaker_tasks')
