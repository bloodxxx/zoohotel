from django.db import migrations, models


def forward(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    Room.objects.filter(type='economy').update(type='aviary')
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(name='Спецпитание').update(is_daily=True)


def backward(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    Room.objects.filter(type='aviary').update(type='economy')
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(name='Спецпитание').update(is_daily=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_deactivate_gruming_basic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='type',
            field=models.CharField(
                choices=[('aviary', 'Вольер'), ('standard', 'Стандарт'), ('lux', 'Люкс')],
                max_length=20,
                verbose_name='Тип',
            ),
        ),
        migrations.RunPython(forward, backward),
    ]
