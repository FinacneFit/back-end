from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Choice, Question
from .serializers import QuestionSerializer

# 원점수(15~120) → 100점 만점으로 정규화: round((raw - 15) / 105 * 100)
SCORE_MIN, SCORE_MAX = 15, 120

RESULT_TYPES = [
    ( 0, 19, '안정형',     '원금 손실을 거의 원하지 않고, 예금이나 적금 수준의 안정성을 가장 중요하게 생각하는 유형입니다.'),
    (20, 38, '안정추구형', '안정성을 우선하지만 예·적금보다 높은 수익을 위해 일부 변동성은 감수할 수 있는 유형입니다.'),
    (39, 57, '위험중립형', '투자에는 위험이 따른다는 점을 이해하고 있으며, 수익과 안정성의 균형을 추구하는 유형입니다.'),
    (58, 76, '적극투자형', '일정 수준의 손실을 감수하더라도 시장 평균 이상의 수익을 추구하는 유형입니다.'),
    (77, 100, '공격투자형', '높은 수익을 위해 큰 변동성과 손실 가능성도 적극적으로 감수할 수 있는 유형입니다.'),
]


def normalize_score(raw):
    """원점수(15~120)를 0~100점으로 정규화"""
    return round((raw - SCORE_MIN) / (SCORE_MAX - SCORE_MIN) * 100)


def get_result_type(score_100):
    for min_s, max_s, type_name, description in RESULT_TYPES:
        if min_s <= score_100 <= max_s:
            return type_name, description
    return '위험중립형', '위험과 수익 사이의 균형을 추구합니다.'


class QuestionListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        questions = Question.objects.prefetch_related('choices').order_by('order')
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)


class SubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        answers = request.data.get('answers', [])

        question_count = Question.objects.count()
        if question_count == 0:
            return Response(
                {'detail': '설문 문항이 준비되지 않았습니다.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if len(answers) != question_count:
            return Response(
                {'detail': f'{question_count}개 문항 모두 응답해야 합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_score = 0
        answered_question_ids = set()
        for answer in answers:
            question_id = answer.get('question_id')
            choice_id = answer.get('choice_id')
            if not question_id or not choice_id:
                return Response(
                    {'detail': 'question_id 또는 choice_id 값이 누락되었습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if question_id in answered_question_ids:
                return Response(
                    {'detail': f'문항 ID {question_id}의 응답이 중복되었습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                choice = Choice.objects.get(pk=choice_id, question_id=question_id)
                total_score += choice.score
            except Choice.DoesNotExist:
                return Response(
                    {'detail': f'문항 ID {question_id}에 선택지 ID {choice_id}가 존재하지 않습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            answered_question_ids.add(question_id)

        score_100 = normalize_score(total_score)
        result_type, description = get_result_type(score_100)
        request.user.risk_score = score_100
        request.user.investment_type = result_type
        request.user.save(update_fields=['risk_score', 'investment_type'])

        return Response({
            'risk_score': score_100,
            'result_type': result_type,
            'result_description': description,
        })
