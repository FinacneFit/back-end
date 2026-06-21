from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from stocks.models import Stock
from .models import PortfolioHolding
from .serializers import HoldingSerializer


class PortfolioView(APIView):
    def get(self, request):
        holdings = PortfolioHolding.objects.filter(user=request.user).select_related('stock')
        total_invested = 0
        total_value = 0
        data = []

        for h in holdings:
            invested = h.buy_price * h.qty
            value = h.stock.price * h.qty
            total_invested += invested
            total_value += value
            data.append(HoldingSerializer(h).data)

        return_rate = round((total_value - total_invested) / total_invested * 100, 2) if total_invested else 0

        return Response({
            'holdings': data,
            'total_invested': total_invested,
            'total_value': total_value,
            'return_rate': return_rate,
        })


class HoldingListCreateView(APIView):
    def post(self, request):
        stock_id = request.data.get('stock_id')
        qty = request.data.get('qty')
        buy_price = request.data.get('buy_price')

        if not all([stock_id, qty, buy_price]):
            return Response({'detail': '필수 필드가 누락되었습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            qty = int(qty)
            buy_price = int(buy_price)
        except (ValueError, TypeError):
            return Response({'detail': 'qty, buy_price는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        if qty < 1:
            return Response({'detail': '수량은 1 이상이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        stock = get_object_or_404(Stock, pk=stock_id)
        existing = PortfolioHolding.objects.filter(user=request.user, stock=stock).first()

        if existing:
            total_qty = existing.qty + qty
            total_cost = existing.buy_price * existing.qty + buy_price * qty
            existing.buy_price = round(total_cost / total_qty)
            existing.qty = min(total_qty, 9999)
            existing.save()
            return Response(HoldingSerializer(existing).data, status=status.HTTP_200_OK)

        holding = PortfolioHolding.objects.create(
            user=request.user,
            stock=stock,
            qty=min(qty, 9999),
            buy_price=buy_price,
        )
        return Response(HoldingSerializer(holding).data, status=status.HTTP_201_CREATED)


class HoldingDetailView(APIView):
    def get_object(self, request, holding_id):
        return get_object_or_404(PortfolioHolding, pk=holding_id, user=request.user)

    def patch(self, request, holding_id):
        holding = self.get_object(request, holding_id)
        qty = request.data.get('qty')

        if qty is None:
            return Response({'detail': 'qty 값이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            qty = int(qty)
        except (ValueError, TypeError):
            return Response({'detail': 'qty는 정수여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= qty <= 9999):
            return Response({'detail': 'qty는 1 이상 9999 이하여야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        holding.qty = qty
        holding.save(update_fields=['qty'])
        return Response(HoldingSerializer(holding).data)

    def delete(self, request, holding_id):
        holding = self.get_object(request, holding_id)
        holding.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
