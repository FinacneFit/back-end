from rest_framework import serializers
from .models import DepositProduct, DepositOption


class DepositProductSerializer(serializers.ModelSerializer):
    bankName         = serializers.CharField(source='kor_co_nm')
    productName      = serializers.CharField(source='fin_prdt_nm')
    productType      = serializers.CharField(source='product_type')
    interestType     = serializers.SerializerMethodField()
    baseRate         = serializers.SerializerMethodField()
    maxRate          = serializers.SerializerMethodField()
    term             = serializers.SerializerMethodField()
    joinMethods      = serializers.SerializerMethodField()
    disclosureDate   = serializers.SerializerMethodField()
    afterMaturityRate = serializers.CharField(source='mtrt_int')
    restriction      = serializers.CharField(source='join_deny')
    target           = serializers.CharField(source='join_member')
    note             = serializers.CharField(source='etc_note')
    maxLimit         = serializers.CharField(source='max_limit')
    options          = serializers.SerializerMethodField()

    class Meta:
        model = DepositProduct
        fields = [
            'id', 'bankName', 'productName', 'productType',
            'interestType', 'baseRate', 'maxRate', 'term',
            'joinMethods', 'disclosureDate', 'afterMaturityRate',
            'restriction', 'target', 'note', 'maxLimit', 'options',
        ]

    def _opts(self, obj):
        return list(obj.options.order_by('save_trm', 'intr_rate_type'))

    def get_interestType(self, obj):
        opt = obj.options.order_by('save_trm').first()
        return opt.intr_rate_type_nm if opt else '단리'

    def get_baseRate(self, obj):
        rates = [o.intr_rate for o in self._opts(obj) if o.intr_rate]
        return round(max(rates), 2) if rates else 0.0

    def get_maxRate(self, obj):
        rates = [o.intr_rate2 for o in self._opts(obj) if o.intr_rate2]
        return round(max(rates), 2) if rates else 0.0

    def get_term(self, obj):
        opts = self._opts(obj)
        if not opts:
            return '-'
        # 최고우대금리가 가장 높은 기간 표시
        best = max(opts, key=lambda o: (o.intr_rate2 or 0))
        return f'{best.save_trm}개월'

    def get_joinMethods(self, obj):
        if not obj.join_way:
            return []
        raw = obj.join_way.replace('·', ',').replace('/', ',')
        return [m.strip() for m in raw.split(',') if m.strip()]

    def get_disclosureDate(self, obj):
        m = obj.dcls_month
        if not m or len(m) < 6:
            return m or ''
        return f'{m[:4]}-{m[4:6]}'

    def get_options(self, obj):
        seen = set()
        result = []
        for o in self._opts(obj):
            key = (o.save_trm, o.intr_rate_type)
            if key not in seen:
                seen.add(key)
                result.append({
                    'period':   f'{o.save_trm}개월',
                    'baseRate': o.intr_rate,
                    'maxRate':  o.intr_rate2,
                })
        return result
