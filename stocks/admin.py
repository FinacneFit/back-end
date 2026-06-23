from django.contrib import admin
from .models import Stock, StockFinancials


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'price', 'change')
    search_fields = ('name', 'code')
    list_filter = ('category',)


@admin.register(StockFinancials)
class StockFinancialsAdmin(admin.ModelAdmin):
    list_display = ('stock', 'risk_score', 'per', 'pbr', 'roe', 'debt_ratio', 'current_ratio', 'op_margin', 'updated_at')
    search_fields = ('stock__name', 'stock__code')
    ordering = ('risk_score',)
