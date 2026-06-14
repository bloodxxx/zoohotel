from django.db import migrations


def make_daily(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(name='Спецпитание').update(is_daily=True)


def revert(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.filter(name='Спецпитание').update(is_daily=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_deactivate_gruming_basic'),
    ]

    operations = [
        migrations.RunPython(make_daily, revert),
    ]
