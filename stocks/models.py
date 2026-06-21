from django.db import models


class Stock(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10, unique=True)
    category = models.CharField(max_length=30)
    price = models.PositiveIntegerField(default=0)
    change = models.FloatField(default=0.0)
    suitable_types = models.JSONField(default=list)

    def __str__(self):
        return f'{self.name} ({self.code})'
