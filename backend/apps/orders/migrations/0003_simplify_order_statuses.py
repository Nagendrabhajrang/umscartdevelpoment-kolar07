from django.db import migrations, models


def migrate_statuses(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    History = apps.get_model('orders', 'OrderStatusHistory')
    # Neither legacy stage guarantees that packing has completed.
    Order.objects.filter(status__in=['confirmed', 'processing']).update(status='pending')
    for field in ('from_status', 'to_status'):
        History.objects.filter(**{field + '__in': ['confirmed', 'processing']}).update(**{field: 'pending'})


class Migration(migrations.Migration):
    dependencies = [('orders', '0002_alter_order_payment_method')]
    choices = [('pending', 'Pending'), ('packed', 'Packed'), ('out_for_delivery', 'Out for delivery'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('returned', 'Returned'), ('refunded', 'Refunded')]
    operations = [
        migrations.RunPython(migrate_statuses, migrations.RunPython.noop),
        migrations.AlterField(model_name='order', name='status', field=models.CharField(choices=choices, db_index=True, default='pending', max_length=20)),
        migrations.AlterField(model_name='orderstatushistory', name='from_status', field=models.CharField(blank=True, choices=choices, default='', max_length=20)),
        migrations.AlterField(model_name='orderstatushistory', name='to_status', field=models.CharField(choices=choices, max_length=20)),
    ]
