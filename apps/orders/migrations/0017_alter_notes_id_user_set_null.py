from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0016_alter_orders_data_day'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notes',
            name='id_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_notes',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
