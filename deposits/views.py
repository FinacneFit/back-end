from io import StringIO

from django.core.management import call_command
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DepositProduct, SavedDeposit
from .serializers import (
    DepositProductSerializer,
    SavedDepositCreateSerializer,
    SavedDepositSerializer,
)


class DepositListView(APIView):
    """예금·적금 상품 목록 조회"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        products = DepositProduct.objects.prefetch_related('options').all()
        serializer = DepositProductSerializer(products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DepositRefreshView(APIView):
    """금융감독원 API 데이터 수동 갱신"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        out = StringIO()

        try:
            call_command('load_deposits', stdout=out)
            count = DepositProduct.objects.count()

            return Response(
                {
                    'message': out.getvalue().strip() or '갱신 완료',
                    'total': count,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return Response(
                {
                    'detail': '예금·적금 상품 갱신에 실패했습니다.',
                    'error': str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DepositSaveView(APIView):
    """예금·적금 상품 포트폴리오 담기"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SavedDepositCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(
            DepositProduct,
            pk=serializer.validated_data['product_id'],
        )

        saved_deposit, created = SavedDeposit.objects.get_or_create(
            user=request.user,
            product=product,
        )

        saved_deposit.amount = serializer.validated_data.get('amount') or 0
        saved_deposit.final_rate = serializer.validated_data.get('final_rate') or 0
        saved_deposit.memo = serializer.validated_data.get('memo') or ''
        saved_deposit.save()

        return Response(
            {
                'success': True,
                'created': created,
                'saved': SavedDepositSerializer(saved_deposit).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SavedDepositListView(APIView):
    """내 예금·적금 포트폴리오 조회"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved_deposits = (
            SavedDeposit.objects
            .filter(user=request.user)
            .select_related('product')
            .prefetch_related('product__options')
        )

        serializer = SavedDepositSerializer(saved_deposits, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SavedDepositDeleteView(APIView):
    """내 예금·적금 포트폴리오에서 삭제"""

    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        deleted_count, _ = SavedDeposit.objects.filter(
            user=request.user,
            product_id=product_id,
        ).delete()

        return Response(
            {
                'success': True,
                'deleted': deleted_count > 0,
                'product_id': product_id,
            },
            status=status.HTTP_200_OK,
        )