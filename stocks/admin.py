from django.contrib import admin
from .models import Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'price', 'change')
    search_fields = ('name', 'code')
    list_filter = ('category',)
