from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='portfolio_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
