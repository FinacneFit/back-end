"""
DART API로 전종목 재무지표를 수집하고, 업종별 건전성 기준을 적용해
suitable_types를 재설정한다.

[2단계 알고리즘]
  1단계 - 건전성 스크리닝 (업종별 기준 다름):
           health_score < 40 → suitable_types = [] (투자주의, 추천 제외)
  2단계 - 성향 분류 (건전 기업만):
           PER + PBR + ROE → risk_score(0~11) → 안정형 ~ 공격투자형

[업종별 건전성 예외]
  금융/보험/증권 (K*)  : 부채비율·유동비율 무시, ROE만 평가
  지주회사             : 영업이익률 무시, 부채·유동비율만 평가
  건설/조선 (F*, C31*) : 부채비율 기준 완화 (350% 이하 허용)
  바이오/제약 (C21*,C27*): 영업이익률 음수 감점 없음
  항공/해운 (H5*)      : 부채비율 기준 완화 (500% 이하 허용)

사용법:
  python manage.py update_financials               # DART API 전체 수집
  python manage.py update_financials --code 005930 # 단일 종목
  python manage.py update_financials --recalculate # 기존 데이터로 점수만 재계산
"""
import os
import time
import datetime

import OpenDartReader
from django.core.management.base import BaseCommand

from stocks.models import Stock, StockFinancials

DART_KEY = os.getenv('DART_KEY', '')

BS_IDS = {
    'ifrs-full_CurrentAssets':      'current_assets',
    'ifrs-full_CurrentLiabilities': 'current_liabilities',
    'ifrs-full_Liabilities':        'total_liabilities',
    'ifrs-full_Equity':             'total_equity',
}
IS_IDS = {
    'ifrs-full_Revenue':                   'revenue',
    'dart_OperatingIncomeLoss':            'operating_income',
    'ifrs-full_ProfitLoss':                'net_income',
    'ifrs-full_BasicEarningsLossPerShare': 'eps',
}

# ── 업종 유형 감지 ───────────────────────────────────────────────────
FINANCIAL_CODES  = ('K',)                      # 금융 및 보험업
BIOTECH_CODES    = ('C21', 'C27')              # 의약품/화학
CONSTRUCT_CODES  = ('F',   'C31')              # 건설/조선
TRANSPORT_CODES  = ('H50', 'H51')              # 항공/해운
HOLDING_KEYWORDS = ('지주', '홀딩스', 'Holdings')


def detect_sector_type(name: str, sector: str, debt_ratio, op_margin) -> str:
    """업종 유형 반환: financial / holding / biotech / construction / transport / general"""
    # 1. DART induty_code 기반 (가장 정확)
    if sector:
        if any(sector.startswith(c) for c in FINANCIAL_CODES):
            return 'financial'
        if any(sector.startswith(c) for c in BIOTECH_CODES):
            return 'biotech'
        if any(sector.startswith(c) for c in CONSTRUCT_CODES):
            return 'construction'
        if any(sector.startswith(c) for c in TRANSPORT_CODES):
            return 'transport'

    # 2. 금융 지주회사: 지주/홀딩스 이름 + 고부채 → financial로 처리
    #    (신한지주, 하나금융지주 등 금융 계열 지주사는 부채비율 1000%+ 정상)
    is_holding_name = any(kw in name for kw in HOLDING_KEYWORDS)
    if is_holding_name and debt_ratio is not None and debt_ratio > 300:
        return 'financial'

    # 3. 일반 지주회사 (부채비율 낮은 산업형 지주)
    if is_holding_name:
        return 'holding'

    # 4. 재무 패턴 기반 금융 감지 (부채비율 300% 초과 → 금융업 특성)
    if debt_ratio is not None and debt_ratio > 300:
        return 'financial'

    return 'general'


# ── 업종별 건전성 점수 (0~100) ───────────────────────────────────────

def _health_general(debt_ratio, current_ratio, op_margin):
    """제조업 등 일반 기업"""
    score = 0
    if debt_ratio is not None:
        if   debt_ratio < 50:   score += 40
        elif debt_ratio < 100:  score += 30
        elif debt_ratio < 200:  score += 20
        elif debt_ratio < 300:  score += 10
    if current_ratio is not None:
        if   current_ratio > 200:  score += 30
        elif current_ratio > 150:  score += 20
        elif current_ratio > 100:  score += 10
    if op_margin is not None:
        if   op_margin > 10:  score += 30
        elif op_margin > 5:   score += 20
        elif op_margin > 0:   score += 10
    return score


def _health_financial(roe):
    """금융/보험/증권: 부채비율·유동비율 무의미 → ROE만 평가"""
    if roe is None: return 60   # 데이터 없음 → 중간값으로 처리
    if roe > 8:    return 80
    if roe > 3:    return 60
    if roe > 0:    return 40
    return 15


def _health_holding(debt_ratio, current_ratio):
    """지주회사: 영업이익률 무의미 → 부채·유동비율만 평가"""
    score = 0
    if debt_ratio is not None:
        if   debt_ratio < 50:   score += 60
        elif debt_ratio < 100:  score += 45
        elif debt_ratio < 200:  score += 30
        elif debt_ratio < 300:  score += 15
    if current_ratio is not None:
        if   current_ratio > 200:  score += 40
        elif current_ratio > 150:  score += 30
        elif current_ratio > 100:  score += 20
        elif current_ratio > 50:   score += 10
    return score


def _health_biotech(debt_ratio, current_ratio):
    """바이오/제약: R&D 적자 정상 → 영업이익률 감점 없음"""
    score = 0
    if debt_ratio is not None:
        if   debt_ratio < 50:   score += 40
        elif debt_ratio < 100:  score += 30
        elif debt_ratio < 200:  score += 20
        elif debt_ratio < 300:  score += 10
    if current_ratio is not None:
        if   current_ratio > 200:  score += 60
        elif current_ratio > 150:  score += 45
        elif current_ratio > 100:  score += 30
        elif current_ratio > 50:   score += 10
    return score


def _health_construction(debt_ratio, current_ratio, op_margin):
    """건설/조선: 부채비율 기준 완화 (350% 이하 허용)"""
    score = 0
    if debt_ratio is not None:
        if   debt_ratio < 100:  score += 40
        elif debt_ratio < 200:  score += 30
        elif debt_ratio < 350:  score += 20
        elif debt_ratio < 500:  score += 10
    if current_ratio is not None:
        if   current_ratio > 150:  score += 30
        elif current_ratio > 100:  score += 20
        elif current_ratio > 80:   score += 10
    if op_margin is not None:
        if   op_margin > 5:   score += 30
        elif op_margin > 0:   score += 15
    return score


def _health_transport(debt_ratio, current_ratio, op_margin):
    """항공/해운: 리스 자산으로 부채비율 높음 → 기준 완화 (500% 이하 허용)"""
    score = 0
    if debt_ratio is not None:
        if   debt_ratio < 150:  score += 40
        elif debt_ratio < 300:  score += 30
        elif debt_ratio < 500:  score += 20
        elif debt_ratio < 700:  score += 10
    if current_ratio is not None:
        if   current_ratio > 150:  score += 30
        elif current_ratio > 100:  score += 20
        elif current_ratio > 70:   score += 10
    if op_margin is not None:
        if   op_margin > 10:  score += 30
        elif op_margin > 5:   score += 20
        elif op_margin > 0:   score += 10
    return score


def calc_health_score(sector_type, debt_ratio, current_ratio, op_margin, roe):
    if sector_type == 'financial':
        return _health_financial(roe)
    if sector_type == 'holding':
        return _health_holding(debt_ratio, current_ratio)
    if sector_type == 'biotech':
        return _health_biotech(debt_ratio, current_ratio)
    if sector_type == 'construction':
        return _health_construction(debt_ratio, current_ratio, op_margin)
    if sector_type == 'transport':
        return _health_transport(debt_ratio, current_ratio, op_margin)
    return _health_general(debt_ratio, current_ratio, op_margin)


# ── 2단계: 성장성/공격성 점수 (0~11) ────────────────────────────────

def calc_growth_score(per, pbr, roe):
    score = 0
    if per is not None:
        if   per < 0:    score += 5   # 성장기 적자 (고성장 기대)
        elif per < 10:   score += 1   # 저PER 가치주
        elif per < 15:   score += 2
        elif per < 25:   score += 3
        elif per < 50:   score += 4
        else:            score += 5   # 고PER 성장주
    if pbr is not None:
        if   pbr < 1:   score += 1
        elif pbr < 2:   score += 2
        elif pbr < 4:   score += 3
        elif pbr < 7:   score += 4
        else:           score += 5
    if roe is not None and roe > 15:
        score += 1
    return score


def assign_suitable_types(health_score, per, pbr, roe):
    if health_score < 40:
        return []   # 투자주의: 건전성 미달, 추천 제외
    growth = calc_growth_score(per, pbr, roe)
    if   growth <= 2:  return ['안정형', '안정추구형']
    elif growth <= 4:  return ['안정추구형', '위험중립형']
    elif growth <= 6:  return ['위험중립형', '적극투자형']
    elif growth <= 8:  return ['적극투자형', '공격투자형']
    else:              return ['공격투자형']


# ── DART 데이터 추출 ─────────────────────────────────────────────────

def _extract(df, id_map, sj_div):
    sub = df[df['sj_div'] == sj_div][['account_id', 'thstrm_amount']]
    sub = sub.drop_duplicates('account_id').set_index('account_id')
    result = {}
    for aid, key in id_map.items():
        try:
            result[key] = int(str(sub.loc[aid, 'thstrm_amount']).replace(',', ''))
        except Exception:
            result[key] = None
    return result


def fetch_financials(dart, code, market_cap, price):
    try:
        fs = dart.finstate_all(code, 2024)
        if fs is None or fs.empty:
            return None, None

        bs  = _extract(fs, BS_IDS, 'BS')
        is_ = _extract(fs, IS_IDS, 'IS')

        ca  = bs['current_assets']
        cl  = bs['current_liabilities']
        tl  = bs['total_liabilities']
        eq  = bs['total_equity']
        rev = is_['revenue']
        oi  = is_['operating_income']
        ni  = is_['net_income']
        eps = is_['eps']

        debt_ratio    = round(tl / eq * 100, 2)   if (tl  and eq)         else None
        current_ratio = round(ca / cl * 100, 2)   if (ca  and cl)         else None
        op_margin     = round(oi / rev * 100, 2)  if (oi  and rev)        else None
        roe           = round(ni / eq * 100, 2)   if (ni  and eq)         else None
        pbr           = round(market_cap / eq, 2) if (market_cap and eq)  else None
        per           = round(price / eps, 2)      if (eps and eps > 0 and price) else (
                        -1 if (eps is not None and eps <= 0) else None)

        # DART 업종코드 취득
        sector = None
        try:
            corp_info = dart.company(code)
            if corp_info is not None and not corp_info.empty:
                raw = str(corp_info.iloc[0].get('induty_code', '') or '')
                sector = raw[:3] if raw else None
        except Exception:
            pass

        data = dict(
            debt_ratio=debt_ratio, current_ratio=current_ratio,
            op_margin=op_margin,   roe=roe,
            pbr=pbr,               per=per,
        )
        return data, sector

    except Exception:
        return None, None


def _save(stock, data, sector, today):
    if sector:
        stock.sector = sector

    sector_type = detect_sector_type(
        stock.name, stock.sector or '',
        data['debt_ratio'], data['op_margin']
    )
    health  = calc_health_score(
        sector_type, data['debt_ratio'], data['current_ratio'],
        data['op_margin'], data['roe']
    )
    growth   = calc_growth_score(data['per'], data['pbr'], data['roe'])
    suitable = assign_suitable_types(health, data['per'], data['pbr'], data['roe'])

    for attempt in range(5):
        try:
            StockFinancials.objects.update_or_create(
                stock=stock,
                defaults={
                    **data,
                    'health_score': health,
                    'risk_score':   growth,
                    'updated_at':   today,
                },
            )
            stock.suitable_types = suitable
            stock.save(update_fields=['suitable_types', 'sector'])
            return
        except Exception as e:
            if 'database is locked' in str(e) and attempt < 4:
                time.sleep(3 * (attempt + 1))
            else:
                raise


class Command(BaseCommand):
    help = '업종별 건전성 기준 적용 → 2단계 알고리즘으로 suitable_types 재설정'

    def add_arguments(self, parser):
        parser.add_argument('--code', type=str, default=None)
        parser.add_argument('--recalculate', action='store_true',
                            help='DART 재호출 없이 기존 데이터로 점수/성향만 재계산')

    def handle(self, *args, **options):
        today = datetime.date.today()

        # ── --recalculate 모드 ───────────────────────────────────────
        if options['recalculate']:
            qs = StockFinancials.objects.select_related('stock').all()
            if options['code']:
                qs = qs.filter(stock__code=options['code'])

            total = qs.count()
            self.stdout.write(f'재계산 대상: {total}개')
            updated = 0

            for i, fin in enumerate(qs, 1):
                self.stdout.write(f'  [{i}/{total}] {fin.stock.name}', ending='\r')
                self.stdout.flush()

                data = dict(
                    debt_ratio=fin.debt_ratio, current_ratio=fin.current_ratio,
                    op_margin=fin.op_margin,   roe=fin.roe,
                    pbr=fin.pbr,               per=fin.per,
                )
                sector_type = detect_sector_type(
                    fin.stock.name, fin.stock.sector or '',
                    data['debt_ratio'], data['op_margin']
                )
                health   = calc_health_score(
                    sector_type, data['debt_ratio'], data['current_ratio'],
                    data['op_margin'], data['roe']
                )
                growth   = calc_growth_score(data['per'], data['pbr'], data['roe'])
                suitable = assign_suitable_types(health, data['per'], data['pbr'], data['roe'])

                fin.health_score = health
                fin.risk_score   = growth
                fin.save(update_fields=['health_score', 'risk_score'])

                fin.stock.suitable_types = suitable
                fin.stock.save(update_fields=['suitable_types'])
                updated += 1

            self.stdout.write('\n')

            # 결과 요약
            all_stocks = list(Stock.objects.all())
            dist = {k: 0 for k in ['안정형','안정추구형','위험중립형','적극투자형','공격투자형','투자주의']}
            for s in all_stocks:
                if not s.suitable_types:
                    dist['투자주의'] += 1
                else:
                    for k in list(dist.keys())[:-1]:
                        if k in s.suitable_types:
                            dist[k] += 1
            self.stdout.write(self.style.SUCCESS(f'재계산 완료: {updated}개'))
            for k, v in dist.items():
                self.stdout.write(f'  {k}: {v}개')
            return

        # ── 일반 모드: DART API 수집 ─────────────────────────────────
        if not DART_KEY:
            self.stdout.write(self.style.ERROR('DART_KEY 환경변수가 없습니다.'))
            return

        dart = OpenDartReader(DART_KEY)
        qs = Stock.objects.all()
        if options['code']:
            qs = qs.filter(code=options['code'])
        else:
            done_ids = StockFinancials.objects.filter(updated_at=today).values_list('stock_id', flat=True)
            qs = qs.exclude(id__in=done_ids)

        total = qs.count()
        self.stdout.write(f'대상 종목: {total}개')
        updated = skipped = 0

        for i, stock in enumerate(qs, 1):
            self.stdout.write(f'  [{i}/{total}] {stock.name} ({stock.code})', ending='\r')
            self.stdout.flush()

            data, sector = fetch_financials(dart, stock.code, stock.market_cap, stock.price)
            time.sleep(0.5)

            if data:
                _save(stock, data, sector, today)
                updated += 1
            else:
                skipped += 1

        self.stdout.write('\n')
        self.stdout.write(self.style.SUCCESS(
            f'완료: 재무지표 갱신 {updated}개 / DART 데이터 없음(fallback 유지) {skipped}개'
        ))
