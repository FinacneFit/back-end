import re

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Stock
from .serializers import StockSerializer
from .utils import fetch_stock_info


class RecommendedStocksView(APIView):
    def get(self, request):
        investment_type = request.user.investment_type
        all_stocks = list(Stock.objects.all())

        if investment_type:
            recommended = [s for s in all_stocks if investment_type in s.suitable_types]
        else:
            recommended = all_stocks

        serializer = StockSerializer(recommended[:3], many=True)
        return Response(serializer.data)


class StockSearchView(APIView):
    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response([])

        # ① DB에서 이름/코드로 검색 (한국어 이름 포함)
        db_qs = (
            Stock.objects.filter(name__icontains=q) |
            Stock.objects.filter(code__icontains=q)
        ).distinct()

        if db_qs.exists():
            return Response(StockSerializer(db_qs[:8], many=True).data)

        # ② DB에 없고 6자리 숫자 코드인 경우 → yfinance로 신규 종목 조회
        if re.fullmatch(r'\d{6}', q):
            info = fetch_stock_info(q)
            if info:
                stock, _ = Stock.objects.get_or_create(
                    code=info['code'],
                    defaults={
                        'name':          info['name'],
                        'category':      info['category'],
                        'price':         info['price'],
                        'change':        info['change'],
                        'suitable_types': [],
                    },
                )
                # 이미 존재하면 가격만 갱신
                if not _:
                    stock.price  = info['price']
                    stock.change = info['change']
                    stock.save(update_fields=['price', 'change'])

                return Response([StockSerializer(stock).data])

        return Response([])
