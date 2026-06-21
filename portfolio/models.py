from django.conf import settings
from django.db import models


class PortfolioHolding(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='holdings')
    stock = models.ForeignKey('stocks.Stock', on_delete=models.CASCADE)
    qty = models.PositiveIntegerField()
    buy_price = models.PositiveIntegerField()

    class Meta:
        unique_together = ('user', 'stock')

    def __str__(self):
        return f'{self.user.nickname} - {self.stock.name} x{self.qty}'
