from django.db import models


class Stock(models.Model):
    name           = models.CharField(max_length=100)
    code           = models.CharField(max_length=10, unique=True)
    market         = models.CharField(max_length=10, default='KOSPI')
    category       = models.CharField(max_length=30)
    price          = models.PositiveIntegerField(default=0)
    change         = models.FloatField(default=0.0)
    market_cap     = models.BigIntegerField(default=0)
    suitable_types = models.JSONField(default=list)
    sector         = models.CharField(max_length=10, null=True, blank=True)  # DART induty_code 앞 3자

    def __str__(self):
        return f'[{self.market}] {self.name} ({self.code})'


class StockFinancials(models.Model):
    stock         = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name='financials')
    per           = models.FloatField(null=True)   # 주가수익비율
    pbr           = models.FloatField(null=True)   # 주가순자산비율
    roe           = models.FloatField(null=True)   # 자기자본이익률 (%)
    debt_ratio    = models.FloatField(null=True)   # 부채비율 (%)
    current_ratio = models.FloatField(null=True)   # 유동비율 (%)
    op_margin     = models.FloatField(null=True)   # 영업이익률 (%)
    health_score  = models.FloatField(null=True)   # 건전성 점수 (0~100, 높을수록 건전)
    risk_score    = models.FloatField(null=True)   # 성장성/공격성 점수 (건전 기업에만 의미)
    updated_at    = models.DateField(null=True)

    def __str__(self):
        return f'{self.stock.name} (건전성={self.health_score}, 공격성={self.risk_score})'
