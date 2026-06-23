from django.contrib import admin
from .models import DepositProduct, DepositOption, SavedDeposit


class DepositOptionInline(admin.TabularInline):
    model = DepositOption
    extra = 0
    readonly_fields = (
        'intr_rate_type',
        'intr_rate_type_nm',
        'save_trm',
        'intr_rate',
        'intr_rate2',
    )


@admin.register(DepositProduct)
class DepositProductAdmin(admin.ModelAdmin):
    list_display = (
        'kor_co_nm',
        'fin_prdt_nm',
        'product_type',
        'dcls_month',
        'updated_at',
    )
    list_filter = (
        'product_type',
        'kor_co_nm',
    )
    search_fields = (
        'fin_prdt_nm',
        'kor_co_nm',
        'fin_prdt_cd',
    )
    readonly_fields = (
        'fin_co_no',
        'fin_prdt_cd',
        'updated_at',
    )
    inlines = [DepositOptionInline]


@admin.register(DepositOption)
class DepositOptionAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'save_trm',
        'intr_rate_type_nm',
        'intr_rate',
        'intr_rate2',
    )
    list_filter = (
        'intr_rate_type_nm',
        'save_trm',
    )


@admin.register(SavedDeposit)
class SavedDepositAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'product',
        'amount',
        'final_rate',
        'created_at',
    )
    search_fields = (
        'user__email',
        'user__nickname',
        'product__fin_prdt_nm',
        'product__kor_co_nm',
    )
    list_filter = (
        'product__product_type',
        'product__kor_co_nm',
    )