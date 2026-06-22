from django.conf import settings
from django.db import models


class DepositProduct(models.Model):
    """금융감독원 API 기반 예금·적금 상품"""

    PRODUCT_TYPE_CHOICES = (
        ('deposit', '예금'),
        ('saving', '적금'),
    )

    fin_co_no = models.CharField(max_length=20)
    fin_prdt_cd = models.CharField(max_length=50)
    kor_co_nm = models.CharField(max_length=100)
    fin_prdt_nm = models.CharField(max_length=200)
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES)

    join_way = models.CharField(max_length=500, blank=True)
    mtrt_int = models.TextField(blank=True)
    spcl_cnd = models.TextField(blank=True)
    join_deny = models.CharField(max_length=30, blank=True)
    join_member = models.TextField(blank=True)
    etc_note = models.TextField(blank=True)
    max_limit = models.TextField(blank=True)
    dcls_month = models.CharField(max_length=10, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('fin_co_no', 'fin_prdt_cd')
        ordering = ['kor_co_nm', 'fin_prdt_nm']

    def __str__(self):
        return f'[{self.kor_co_nm}] {self.fin_prdt_nm}'


class DepositOption(models.Model):
    """상품별 기간·금리 옵션"""

    product = models.ForeignKey(
        DepositProduct,
        on_delete=models.CASCADE,
        related_name='options',
    )

    intr_rate_type = models.CharField(max_length=5)
    intr_rate_type_nm = models.CharField(max_length=20)
    save_trm = models.IntegerField()
    intr_rate = models.FloatField(default=0)
    intr_rate2 = models.FloatField(default=0)

    class Meta:
        unique_together = ('product', 'save_trm', 'intr_rate_type')
        ordering = ['save_trm', 'intr_rate_type']

    def __str__(self):
        return f'{self.product.fin_prdt_nm} {self.save_trm}개월 {self.intr_rate_type_nm}'


class SavedDeposit(models.Model):
    """사용자가 포트폴리오에 담은 예금·적금 상품"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_deposits',
    )
    product = models.ForeignKey(
        DepositProduct,
        on_delete=models.CASCADE,
        related_name='saved_users',
    )

    amount = models.PositiveIntegerField(null=True, blank=True)
    final_rate = models.FloatField(null=True, blank=True)
    memo = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.product}'