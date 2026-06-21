from django.contrib import admin
from .models import PortfolioHolding


@admin.register(PortfolioHolding)
class PortfolioHoldingAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock', 'qty', 'buy_price')
    list_filter = ('user',)
