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

SECTOR_TYPE_DESC = {
    'financial':    '금융업 특성상 부채비율 대신 ROE 중심으로 건전성을 평가한 종목',
    'holding':      '지주회사로 자회사 포트폴리오 안정성 기준으로 평가한 종목',
    'biotech':      '바이오/제약 특성상 유동비율·성장성 중심으로 평가한 종목',
    'construction': '건설업 특성상 부채비율 허용 범위를 넓게 적용한 종목',
    'transport':    '항공·해운 특성상 감가상각 구조를 고려해 평가한 종목',
    'general':      '일반 산업 표준 기준(부채비율·유동비율·영업이익률·ROE)으로 평가한 종목',
}

TYPE_DESC = {
    '안정형':     '원금 보존 최우선, 예·적금 수준의 안전 자산 선호',
    '안정추구형': '안정성 우선이지만 일부 변동성 허용, 채권·배당주 중심',
    '위험중립형': '수익과 안정의 균형 추구, 다양한 자산군 혼합',
    '적극투자형': '시장 평균 이상 수익 추구, 성장주·ETF 중심',
    '공격투자형': '고위험 고수익 추구, 변동성·손실 가능성 적극 수용',
}


def _fmt_opt(label, val, unit='', fmt='.1f'):
    if val is None:
        return None
    return f"{label} {format(val, fmt)}{unit}"


def _build_system_prompt(user, user_context=None):
    # DB 값이 없으면 프론트 캐시 값 사용
    investment_type = user.investment_type or (user_context or {}).get('investment_type', '')
    risk_score      = user.risk_score      or (user_context or {}).get('risk_score', 0)

    # ── 포트폴리오 ──
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
            f"매입가 {h.buy_price:,}원 / 현재가 {h.stock.price:,}원 / 수익률 {ret:+.1f}%"
        )

    overall_return = (
        round((total_value - total_invested) / total_invested * 100, 2)
        if total_invested else 0
    )

    # ── 성향 기반 추천 종목 (건전성 알고리즘 결과) ──
    all_stocks = Stock.objects.select_related('financials').order_by('-market_cap')
    if investment_type:
        recommended = [s for s in all_stocks if investment_type in (s.suitable_types or [])][:5]
    else:
        recommended = list(all_stocks[:5])

    rec_lines = []
    for s in recommended:
        parts = [f"- {s.name}({s.code}): {s.price:,}원, 등락 {s.change:+.2f}%, {s.category}"]
        try:
            fin = s.financials
            metrics = [x for x in [
                _fmt_opt('건전성점수', fin.health_score, '/100', '.0f'),
                _fmt_opt('ROE', fin.roe, '%'),
                _fmt_opt('부채비율', fin.debt_ratio, '%', '.0f'),
                _fmt_opt('영업이익률', fin.op_margin, '%'),
                _fmt_opt('PER', fin.per, '배'),
                _fmt_opt('PBR', fin.pbr, '배'),
            ] if x]
            if metrics:
                parts.append(f"  재무: {' | '.join(metrics)}")
        except Exception:
            pass
        rec_lines.append('\n'.join(parts))

    # ── 텍스트 조립 ──
    portfolio_text = '\n'.join(portfolio_lines) if portfolio_lines else '(보유 종목 없음)'
    rec_text       = '\n'.join(rec_lines)       if rec_lines       else '(추천 종목 없음)'

    if investment_type and risk_score:
        type_line = (
            f"{investment_type} (성향점수: {risk_score}/100)\n"
            f"  → {TYPE_DESC.get(investment_type, '')}"
        )
    elif investment_type:
        type_line = f"{investment_type}\n  → {TYPE_DESC.get(investment_type, '')}"
    else:
        type_line = "미설문 상태 (투자 성향 설문을 아직 완료하지 않은 사용자)"

    return f"""당신은 FinFit 앱의 개인 투자 포트폴리오 전문 어시스턴트입니다.
사용자의 포트폴리오와 투자 성향, 추천 종목 알고리즘 결과를 바탕으로 한국어로 맞춤 답변을 제공하세요.

[사용자 투자 성향]
{type_line}

[현재 포트폴리오]
{portfolio_text}
총 투자금: {total_invested:,}원 | 평가금액: {total_value:,}원 | 전체 수익률: {overall_return:+.1f}%

[성향 기반 추천 종목]
아래 종목은 2단계 알고리즘으로 선별됐습니다.
1단계 건전성 평가: 업종별 특성(금융·바이오·건설·지주회사 등)을 반영해 부채비율·유동비율·영업이익률·ROE를 종합한 건전성점수(0~100) 산출
2단계 성향 분류: 건전성점수 + PER·PBR·ROE 기반 성장성/위험도 분류 → 사용자 투자 성향({investment_type or '미설문'})에 맞는 종목 선별

{rec_text}

[답변 원칙]
- 추천 종목을 언급할 때는 건전성점수·ROE·부채비율 등 구체적 수치를 근거로 설명하세요.
- 사용자의 성향({investment_type or '미설문'})에 맞게 왜 이 종목이 적합한지 알고리즘 관점에서 설명하세요.
- 포트폴리오 수익률이나 보유 종목이 있으면 함께 연결해 분석하세요.
- 3~5문장으로 간결하게 답변하되, 수치는 반드시 인용하세요.
- 투자 결정은 사용자 본인의 판단임을 필요시 안내하세요."""


class ChatMessageView(APIView):
    def post(self, request):
        message      = request.data.get('message', '').strip()
        history      = request.data.get('history', [])
        user_context = request.data.get('user_context', {})

        if not message:
            return Response({'detail': '메시지를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        messages = [{'role': 'developer', 'content': _build_system_prompt(request.user, user_context)}]

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
