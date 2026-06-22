import os
import requests
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolio.models import PortfolioHolding
from stocks.models import Stock

_GMS_URL = 'https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions'
_GMS_KEY = os.environ.get('GMS_KEY', '')
_MODEL   = 'gpt-5.4-mini'


def _build_system_prompt(user):
    holdings = PortfolioHolding.objects.filter(user=user).select_related('stock')

    total_invested, total_value = 0, 0
    portfolio_lines = []
    for h in holdings:
        invested = h.buy_price * h.qty
        value    = h.stock.price * h.qty
        ret      = round((value - invested) / invested * 100, 2) if invested else 0
        total_invested += invested
        total_value    += value
        portfolio_lines.append(
            f"- {h.stock.name}({h.stock.code}): {h.qty}주, "
            f"매입가 {h.buy_price:,}원, 현재가 {h.stock.price:,}원, 수익률 {ret:+.1f}%"
        )

    overall_return = (
        round((total_value - total_invested) / total_invested * 100, 2)
        if total_invested else 0
    )

    all_stocks = list(Stock.objects.order_by('-market_cap'))
    if user.investment_type:
        recommended = [s for s in all_stocks if user.investment_type in s.suitable_types][:5]
    else:
        recommended = all_stocks[:5]

    rec_lines = [
        f"- {s.name}({s.code}): {s.price:,}원, "
        f"시가총액 {s.market_cap // 100_000_000:,}억원, "
        f"등락률 {s.change:+.2f}%, {s.category}"
        for s in recommended
    ]

    portfolio_text = '\n'.join(portfolio_lines) if portfolio_lines else '(보유 종목 없음)'
    rec_text       = '\n'.join(rec_lines)       if rec_lines       else '(추천 종목 없음)'

    return f"""당신은 개인 투자 포트폴리오 전문 어시스턴트입니다. 사용자의 포트폴리오와 투자 성향에 특화된 맞춤 답변을 한국어로 제공하세요.

[사용자 투자 정보]
- 투자 성향: {user.investment_type or '미설정'} (성향점수: {user.risk_score}/100)

[현재 포트폴리오]
{portfolio_text}
총 투자금: {total_invested:,}원 | 평가금액: {total_value:,}원 | 전체 수익률: {overall_return:+.1f}%

[성향 기반 추천 종목 (시가총액 상위)]
{rec_text}

[답변 원칙]
- 사용자의 포트폴리오와 투자 성향을 항상 고려해 개인화된 답변을 제공하세요.
- 수치가 있으면 구체적으로 인용하세요.
- 3~5문장으로 간결하게 답변하세요.
- 투자 결정은 사용자 본인의 판단임을 필요시 안내하세요."""


class ChatMessageView(APIView):
    def post(self, request):
        message = request.data.get('message', '').strip()
        history = request.data.get('history', [])

        if not message:
            return Response({'detail': '메시지를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        messages = [{'role': 'developer', 'content': _build_system_prompt(request.user)}]

        for h in history[-20:]:
            role = 'user' if h['role'] == 'user' else 'assistant'
            messages.append({'role': role, 'content': h['text']})

        messages.append({'role': 'user', 'content': message})

        try:
            resp = requests.post(
                _GMS_URL,
                headers={
                    'Authorization': f'Bearer {_GMS_KEY}',
                    'Content-Type': 'application/json',
                },
                json={'model': _MODEL, 'messages': messages, 'max_completion_tokens': 600, 'temperature': 0.7},
                timeout=30,
            )
            data  = resp.json()
            reply = data['choices'][0]['message']['content']
        except (KeyError, IndexError):
            return Response({'detail': 'AI 응답 형식 오류'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            return Response({'detail': f'AI 서비스 오류: {e}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'reply': reply})
