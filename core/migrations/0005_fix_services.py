from django.db import migrations


REMOVE_NAMES = [
    'Доп. уход',
    'Дополнительный уход',
    'Стандартное кормление',
    'Выгул 30 минут',
    'Выгул (30 минут)',
]


def deactivate_services(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    for name in REMOVE_NAMES:
        Service.objects.filter(name__icontains=name.split()[0]).filter(
            name__icontains=name.split()[-1]
        ).update(status='inactive')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_passwordresettoken'),
    ]

    operations = [
        migrations.RunPython(deactivate_services, noop),
    ]
