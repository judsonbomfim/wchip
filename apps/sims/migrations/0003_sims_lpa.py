from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sims', '0002_alter_sims_operator'),
    ]

    operations = [
        migrations.AddField(
            model_name='sims',
            name='lpa',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
