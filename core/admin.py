from django.contrib import admin
from .models import CustomUser, Client, Animal, AnimalDocument, Room, Service, Booking, BookingService, Task, Payment, Log

admin.site.register(CustomUser)
admin.site.register(Client)
admin.site.register(Animal)
admin.site.register(Room)
admin.site.register(Service)
admin.site.register(Booking)
admin.site.register(Task)
admin.site.register(Payment)
admin.site.register(Log)
