from rest_framework import serializers
from .models import PortfolioHolding


class HoldingSerializer(serializers.ModelSerializer):
    stock_id = serializers.IntegerField(source='stock.id', read_only=True)
    name = serializers.CharField(source='stock.name', read_only=True)
    code = serializers.CharField(source='stock.code', read_only=True)
    category = serializers.CharField(source='stock.category', read_only=True)
    current_price = serializers.IntegerField(source='stock.price', read_only=True)

    class Meta:
        model = PortfolioHolding
        fields = ('id', 'stock_id', 'name', 'code', 'category', 'qty', 'buy_price', 'current_price')
