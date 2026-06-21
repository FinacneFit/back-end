from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

# AI 연동 시 여기서 import
# import openai

KEYWORD_RESPONSES = {
    '삼성전자': '삼성전자는 반도체 및 전자제품 글로벌 1위 기업으로, 안정적인 배당과 반도체 슈퍼사이클 수혜가 기대됩니다. 변동성이 낮아 안정추구형 투자자에게 적합합니다.',
    'SK하이닉스': 'SK하이닉스는 HBM(고대역폭 메모리) 시장을 선도하며 AI 수요 증가의 직접 수혜주입니다. 성장성이 높지만 반도체 업황 변동 리스크도 존재합니다.',
    'KODEX 200': 'KODEX 200은 코스피 200을 추종하는 ETF로, 분산투자 효과가 뛰어나 포트폴리오 안정성을 높여줍니다. 개별 종목 리스크 없이 시장 평균 수익을 추구합니다.',
    'KB금융': 'KB금융은 국내 최대 금융그룹으로 안정적인 배당 수익과 실적을 자랑합니다. 금리 인상기 수혜를 받을 수 있는 방어적 종목입니다.',
    '현대차': '현대차는 전기차 전환 가속화와 글로벌 시장 점유율 확대로 중장기 성장이 기대됩니다. 밸류에이션이 낮아 가치투자 관점에서도 매력적입니다.',
    '셀트리온': '셀트리온은 바이오시밀러 글로벌 시장에서 경쟁력을 갖추고 있습니다. 고성장 기대와 함께 임상 리스크도 존재하므로 적극투자형에 적합합니다.',
}


class ChatMessageView(APIView):
    def post(self, request):
        message = request.data.get('message', '').strip()
        if not message:
            return Response({'detail': '메시지를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        # TODO: AI(LLM) 연동 시 아래 주석 해제 후 구현
        # reply = call_llm(message, user=request.user)

        matched_key = next((k for k in KEYWORD_RESPONSES if k in message), None)
        reply = (
            KEYWORD_RESPONSES[matched_key]
            if matched_key
            else '궁금한 점을 더 구체적으로 질문해 주시면 분석해드릴게요! 예: "삼성전자를 추천한 이유를 알려줘"'
        )

        return Response({'reply': reply})
