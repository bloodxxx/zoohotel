from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import CustomUser, Client, Animal, AnimalDocument, Room, RoomImage, Service, Booking, Task, Payment


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Логин"}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Пароль"}))


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput(attrs={"class": "form-control"}))
    agree = forms.BooleanField(label="Я согласен с условиями использования сервиса", widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    class Meta:
        model = CustomUser
        fields = ["username", "first_name", "last_name", "email", "phone"]
        labels = {"username": "Логин", "first_name": "Имя", "last_name": "Фамилия", "email": "Email", "phone": "Телефон"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Пароли не совпадают")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.role = "client"
        if commit:
            user.save()
            Client.objects.create(
                user=user,
                full_name=f'{user.last_name} {user.first_name}'.strip() or user.username,
                phone=user.phone,
                email=user.email,
            )
        return user


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["full_name", "phone", "email"]
        labels = {"full_name": "ФИО", "phone": "Телефон", "email": "Email"}
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = ["name", "species", "breed", "birth_date", "special_needs"]
        labels = {"name": "Кличка", "species": "Вид", "breed": "Порода", "birth_date": "Дата рождения", "special_needs": "Особые отметки"}
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "species": forms.Select(attrs={"class": "form-select"}),
            "breed": forms.TextInput(attrs={"class": "form-control"}),
            "birth_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "special_needs": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class AnimalDocumentForm(forms.ModelForm):
    class Meta:
        model = AnimalDocument
        fields = ["document_type", "file"]
        labels = {"document_type": "Тип документа", "file": "Файл"}
        widgets = {"document_type": forms.TextInput(attrs={"class": "form-control"})}


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "type", "description", "price_per_day", "status", "image"]
        labels = {"name": "Название", "type": "Тип", "description": "Описание", "price_per_day": "Цена за сутки", "status": "Статус"}
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "price_per_day": forms.NumberInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "image": forms.FileInput(attrs={"class": "form-control"}),
        }


class RoomImageForm(forms.ModelForm):
    class Meta:
        model = RoomImage
        fields = ['image', 'caption', 'order']
        labels = {'image': 'Фото', 'caption': 'Подпись (необязательно)', 'order': 'Порядок сортировки'}
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Вид из вольера'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'value': '0'}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "description", "category", "price", "unit", "status"]
        labels = {"name": "Название", "description": "Описание", "category": "Категория", "price": "Стоимость", "unit": "Ед. изм.", "status": "Статус"}
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "category": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class GuestBookingForm(forms.Form):
    full_name = forms.CharField(label="ФИО клиента", max_length=100, widget=forms.TextInput(attrs={"class": "form-control"}))
    phone = forms.CharField(label="Телефон", max_length=20, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+7 (xxx) xxx-xx-xx"}))
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"class": "form-control"}))
    animal_name = forms.CharField(label="Кличка животного", max_length=100, widget=forms.TextInput(attrs={"class": "form-control"}))
    animal_species = forms.ChoiceField(label="Вид животного", choices=Animal.SPECIES_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    animal_breed = forms.CharField(label="Порода", max_length=100, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    special_needs = forms.CharField(label="Особые отметки", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    check_in_date = forms.DateTimeField(label="Дата и время заезда", widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}))
    check_out_date = forms.DateTimeField(label="Дата и время выезда", widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}))
    room = forms.ModelChoiceField(label="Номер", queryset=Room.objects.filter(status="available"), widget=forms.Select(attrs={"class": "form-select", "id": "id_room"}))
    services = forms.ModelMultipleChoiceField(label="Дополнительные услуги", queryset=Service.objects.filter(status="active"), required=False, widget=forms.CheckboxSelectMultiple())

    def clean(self):
        cd = super().clean()
        ci = cd.get("check_in_date")
        co = cd.get("check_out_date")
        if ci and co:
            if ci < timezone.now():
                self.add_error("check_in_date", "Дата заезда не может быть в прошлом")
            if co <= ci:
                self.add_error("check_out_date", "Дата выезда должна быть позже даты заезда")
        return cd


class ClientBookingForm(forms.Form):
    animal = forms.ModelChoiceField(label="Животное", queryset=Animal.objects.none(), widget=forms.Select(attrs={"class": "form-select"}))
    check_in_date = forms.DateTimeField(label="Дата и время заезда", widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}))
    check_out_date = forms.DateTimeField(label="Дата и время выезда", widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}))
    room = forms.ModelChoiceField(label="Номер", queryset=Room.objects.filter(status="available"), widget=forms.Select(attrs={"class": "form-select", "id": "id_room"}))
    services = forms.ModelMultipleChoiceField(label="Дополнительные услуги", queryset=Service.objects.filter(status="active"), required=False, widget=forms.CheckboxSelectMultiple())
    notes = forms.CharField(label="Примечания", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def __init__(self, client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["animal"].queryset = client.animals.all()

    def clean(self):
        cd = super().clean()
        ci = cd.get("check_in_date")
        co = cd.get("check_out_date")
        if ci and co:
            if ci < timezone.now():
                self.add_error("check_in_date", "Дата заезда не может быть в прошлом")
            if co <= ci:
                self.add_error("check_out_date", "Дата выезда должна быть позже даты заезда")
        return cd


class AdminBookingForm(forms.ModelForm):
    services = forms.ModelMultipleChoiceField(
        label="Услуги", queryset=Service.objects.filter(status="active"),
        required=False, widget=forms.CheckboxSelectMultiple()
    )

    class Meta:
        model = Booking
        fields = ["client", "animal", "room", "check_in_date", "check_out_date", "status", "notes"]
        labels = {"client": "Клиент", "animal": "Животное", "room": "Номер",
                  "check_in_date": "Дата заезда", "check_out_date": "Дата выезда",
                  "status": "Статус", "notes": "Примечания"}
        widgets = {
            "client": forms.Select(attrs={"class": "form-select"}),
            "animal": forms.Select(attrs={"class": "form-select"}),
            "room": forms.Select(attrs={"class": "form-select"}),
            "check_in_date": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}),
            "check_out_date": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"class": "form-control", "type": "datetime-local"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["booking", "service", "assigned_to", "title", "instructions", "scheduled_time", "notes"]
        labels = {"booking": "Бронирование", "service": "Процедура", "assigned_to": "Сотрудник",
                  "title": "Название задачи", "instructions": "Инструкции",
                  "scheduled_time": "Плановое время", "notes": "Заметки"}
        widgets = {
            "booking": forms.Select(attrs={"class": "form-select"}),
            "service": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "scheduled_time": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = CustomUser.objects.filter(role__in=["caretaker", "admin"])


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["booking", "client", "amount", "payment_method", "status", "transaction_id", "payment_date"]
        labels = {"booking": "Бронирование", "client": "Клиент", "amount": "Сумма",
                  "payment_method": "Способ оплаты", "status": "Статус",
                  "transaction_id": "Номер транзакции", "payment_date": "Дата оплаты"}
        widgets = {
            "booking": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
            "payment_method": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "transaction_id": forms.TextInput(attrs={"class": "form-control"}),
            "payment_date": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        }


class StaffForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", required=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Повторите пароль", required=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))

    class Meta:
        model = CustomUser
        fields = ["username", "first_name", "last_name", "email", "phone", "role", "is_active"]
        labels = {"username": "Логин", "first_name": "Имя", "last_name": "Фамилия",
                  "email": "Email", "phone": "Телефон", "role": "Роль", "is_active": "Активен"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Пароли не совпадают")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "phone"]
        labels = {"first_name": "Имя", "last_name": "Фамилия", "email": "Email", "phone": "Телефон"}
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }
