from rest_framework import serializers
from .models import DepositProduct, DepositOption, SavedDeposit


class DepositProductSerializer(serializers.ModelSerializer):
    bankName = serializers.CharField(source='kor_co_nm')
    productName = serializers.CharField(source='fin_prdt_nm')
    productType = serializers.CharField(source='product_type')

    interestType = serializers.SerializerMethodField()
    baseRate = serializers.SerializerMethodField()
    maxRate = serializers.SerializerMethodField()
    term = serializers.SerializerMethodField()
    joinMethods = serializers.SerializerMethodField()
    disclosureDate = serializers.SerializerMethodField()

    afterMaturityRate = serializers.CharField(source='mtrt_int', allow_blank=True)
    restriction = serializers.CharField(source='join_deny', allow_blank=True)
    target = serializers.CharField(source='join_member', allow_blank=True)
    note = serializers.CharField(source='etc_note', allow_blank=True)
    maxLimit = serializers.CharField(source='max_limit', allow_blank=True)

    options = serializers.SerializerMethodField()

    class Meta:
        model = DepositProduct
        fields = [
            'id',
            'bankName',
            'productName',
            'productType',
            'interestType',
            'baseRate',
            'maxRate',
            'term',
            'joinMethods',
            'disclosureDate',
            'afterMaturityRate',
            'restriction',
            'target',
            'note',
            'maxLimit',
            'options',
        ]

    def _opts(self, obj):
        return list(obj.options.order_by('save_trm', 'intr_rate_type'))

    def _best_option(self, obj):
        opts = self._opts(obj)

        if not opts:
            return None

        return max(
            opts,
            key=lambda option: (
                option.intr_rate2 or 0,
                option.intr_rate or 0,
                -option.save_trm,
            ),
        )

    def get_interestType(self, obj):
        option = self._best_option(obj)
        return option.intr_rate_type_nm if option else '단리'

    def get_baseRate(self, obj):
        option = self._best_option(obj)
        return round(option.intr_rate, 2) if option else 0.0

    def get_maxRate(self, obj):
        option = self._best_option(obj)

        if not option:
            return 0.0

        return round(option.intr_rate2 or option.intr_rate or 0, 2)

    def get_term(self, obj):
        option = self._best_option(obj)
        return f'{option.save_trm}개월' if option else '-'

    def get_joinMethods(self, obj):
        if not obj.join_way:
            return []

        raw = (
            obj.join_way
            .replace('·', ',')
            .replace('/', ',')
            .replace('+', ',')
        )

        result = []

        for item in raw.split(','):
            item = item.strip()

            if not item:
                continue

            if '영업점' in item:
                normalized = '영업점'
            elif '인터넷' in item:
                normalized = '인터넷뱅킹'
            elif '스마트' in item or '모바일' in item or '앱' in item:
                normalized = '스마트뱅킹'
            elif '전화' in item:
                normalized = '전화'
            else:
                normalized = item

            if normalized not in result:
                result.append(normalized)

        return result

    def get_disclosureDate(self, obj):
        value = obj.dcls_month

        if not value:
            return ''

        if len(value) >= 6:
            return f'{value[:4]}-{value[4:6]}'

        return value

    def get_options(self, obj):
        seen = set()
        result = []

        for option in self._opts(obj):
            key = (option.save_trm, option.intr_rate_type)

            if key in seen:
                continue

            seen.add(key)

            result.append({
                'period': f'{option.save_trm}개월',
                'baseRate': option.intr_rate,
                'maxRate': option.intr_rate2 or option.intr_rate or 0,
                'interestType': option.intr_rate_type_nm,
            })

        return result


class SavedDepositSerializer(serializers.ModelSerializer):
    product = DepositProductSerializer(read_only=True)

    class Meta:
        model = SavedDeposit
        fields = [
            'id',
            'product',
            'amount',
            'final_rate',
            'memo',
            'created_at',
        ]


class SavedDepositCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    amount = serializers.IntegerField(required=False, default=0)
    final_rate = serializers.FloatField(required=False, default=0)
    memo = serializers.CharField(required=False, allow_blank=True, default='')