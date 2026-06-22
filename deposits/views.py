from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import DepositProduct
from .serializers import DepositProductSerializer


class DepositListView(APIView):
    """예금·적금 상품 목록 조회"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = DepositProduct.objects.prefetch_related('options').all()
        serializer = DepositProductSerializer(products, many=True)
        return Response(serializer.data)


class DepositRefreshView(APIView):
    """FSS API 데이터 수동 갱신 (관리자 또는 인증된 사용자)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.management import call_command
        out = StringIO()
        try:
            call_command('load_deposits', stdout=out)
            msg = out.getvalue().strip() or '갱신 완료'
            count = DepositProduct.objects.count()
            return Response({'message': msg, 'total': count})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
