from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.is_blocked:
                messages.error(request, 'Ваш аккаунт заблокирован.')
                return redirect('login')
            if request.user.role not in roles:
                messages.error(request, 'Недостаточно прав доступа.')
                return redirect('home')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_or_manager(view_func):
    return role_required('admin')(view_func)


def admin_only(view_func):
    return role_required('admin')(view_func)


def client_required(view_func):
    return role_required('client')(view_func)


def caretaker_required(view_func):
    return role_required('caretaker', 'admin')(view_func)


def log_action(request, action, entity_type='', entity_id=None, result='ok'):
    from .models import Log
    Log.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
    )
