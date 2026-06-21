from django.db import models


class Stock(models.Model):
    name           = models.CharField(max_length=100)
    code           = models.CharField(max_length=10, unique=True)
    market         = models.CharField(max_length=10, default='KOSPI')  # KOSPI / KOSDAQ / KONEX
    category       = models.CharField(max_length=30)
    price          = models.PositiveIntegerField(default=0)
    change         = models.FloatField(default=0.0)
    suitable_types = models.JSONField(default=list)

    def __str__(self):
        return f'[{self.market}] {self.name} ({self.code})'
