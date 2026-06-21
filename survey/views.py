from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Choice, Question
from .serializers import QuestionSerializer

RESULT_TYPES = [
    (15,  35, '안정형',     '원금 손실을 거의 원하지 않고, 예금이나 적금 수준의 안정성을 가장 중요하게 생각하는 유형입니다.'),
    (36,  55, '안정추구형', '안정성을 우선하지만 예·적금보다 높은 수익을 위해 일부 변동성은 감수할 수 있는 유형입니다.'),
    (56,  75, '위험중립형', '투자에는 위험이 따른다는 점을 이해하고 있으며, 수익과 안정성의 균형을 추구하는 유형입니다.'),
    (76,  95, '적극투자형', '일정 수준의 손실을 감수하더라도 시장 평균 이상의 수익을 추구하는 유형입니다.'),
    (96, 120, '공격투자형', '높은 수익을 위해 큰 변동성과 손실 가능성도 적극적으로 감수할 수 있는 유형입니다.'),
]


def get_result_type(score):
    for min_s, max_s, type_name, description in RESULT_TYPES:
        if min_s <= score <= max_s:
            return type_name, description
    return '위험중립형', '위험과 수익 사이의 균형을 추구합니다.'


class QuestionListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        questions = Question.objects.prefetch_related('choices').order_by('order')
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)


class SubmitView(APIView):
    def post(self, request):
        answers = request.data.get('answers', [])

        if len(answers) != 15:
            return Response(
                {'detail': '15개 문항 모두 응답해야 합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_score = 0
        for answer in answers:
            choice_id = answer.get('choice_id')
            if not choice_id:
                return Response(
                    {'detail': 'choice_id 값이 누락되었습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                choice = Choice.objects.get(pk=choice_id)
                total_score += choice.score
            except Choice.DoesNotExist:
                return Response(
                    {'detail': f'선택지 ID {choice_id}가 존재하지 않습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        result_type, description = get_result_type(total_score)
        request.user.risk_score = total_score
        request.user.investment_type = result_type
        request.user.save(update_fields=['risk_score', 'investment_type'])

        return Response({
            'risk_score': total_score,
            'result_type': result_type,
            'result_description': description,
        })
