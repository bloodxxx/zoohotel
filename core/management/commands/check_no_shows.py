from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime
from core.models import Booking, Payment


class Command(BaseCommand):
    help = 'Списывает предоплату (1 сутки) за незаезд и отменяет бронирование'

    def handle(self, *args, **options):
        threshold = timezone.now() - datetime.timedelta(hours=24)
        no_shows = Booking.objects.filter(
            status='confirmed',
            check_in_date__lt=threshold,
        )
        count = 0
        for booking in no_shows:
            payment = booking.payments.filter(status__in=['unpaid', 'pending']).first()
            if payment:
                payment.amount = booking.room.price_per_day
                payment.status = 'paid'
                payment.payment_date = timezone.now()
                payment.save(update_fields=['amount', 'status', 'payment_date'])
            booking.status = 'cancelled'
            booking.save(update_fields=['status'])
            count += 1
        self.stdout.write(f'Обработано незаездов: {count}')
