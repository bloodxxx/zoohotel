from django.db import migrations


def deactivate(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(name='Груминг базовый').update(status='inactive')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_service_is_daily'),
    ]

    operations = [
        migrations.RunPython(deactivate, noop),
    ]
