from django.db import models


class DepositProduct(models.Model):
    """금융감독원 API 기반 예금·적금 상품"""
    fin_co_no    = models.CharField(max_length=20)
    fin_prdt_cd  = models.CharField(max_length=50)
    kor_co_nm    = models.CharField(max_length=100)    # 금융회사명
    fin_prdt_nm  = models.CharField(max_length=200)    # 상품명
    product_type = models.CharField(max_length=10)     # 'deposit' | 'saving'
    join_way     = models.CharField(max_length=500, blank=True)   # 가입방법
    mtrt_int     = models.TextField(blank=True)        # 만기 후 이자율
    spcl_cnd     = models.TextField(blank=True)        # 우대조건
    join_deny    = models.CharField(max_length=30, blank=True)    # 가입제한
    join_member  = models.TextField(blank=True)        # 가입대상
    etc_note     = models.TextField(blank=True)        # 기타 유의사항
    max_limit    = models.TextField(blank=True)        # 최고한도
    dcls_month   = models.CharField(max_length=10, blank=True)   # 공시월 (YYYYMM)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('fin_co_no', 'fin_prdt_cd')
        ordering = ['kor_co_nm', 'fin_prdt_nm']

    def __str__(self):
        return f'[{self.kor_co_nm}] {self.fin_prdt_nm}'


class DepositOption(models.Model):
    """상품별 기간·금리 옵션"""
    product          = models.ForeignKey(
        DepositProduct, on_delete=models.CASCADE, related_name='options'
    )
    intr_rate_type   = models.CharField(max_length=5)   # S=단리, M=복리
    intr_rate_type_nm = models.CharField(max_length=20) # 단리 / 복리
    save_trm         = models.IntegerField()             # 저축기간(개월)
    intr_rate        = models.FloatField(default=0)      # 기본금리(%)
    intr_rate2       = models.FloatField(default=0)      # 최고우대금리(%)

    class Meta:
        unique_together = ('product', 'save_trm', 'intr_rate_type')
        ordering = ['save_trm', 'intr_rate_type']

    def __str__(self):
        return f'{self.product.fin_prdt_nm} {self.save_trm}개월 {self.intr_rate_type_nm}'
