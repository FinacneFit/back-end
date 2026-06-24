import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0002_post_portfolio_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='replies',
                to='community.comment',
            ),
        ),
    ]
