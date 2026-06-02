def admin_context(request):
    if request.user.is_authenticated and request.user.role in ('admin', 'manager'):
        from core.models import Booking
        return {'pending_bookings_count': Booking.objects.filter(status='pending').count()}
    return {}
