"""
python manage.py load_stocks          # 신규/갱신 (기존 유지)
python manage.py load_stocks --flush  # 전체 삭제 후 재로드

suitable_types 우선순위:
  1. StockFinancials.risk_score 가 있으면 재무지표 기반 점수로 결정
  2. 없으면 시가총액 + 시장 구분 fallback
"""
import FinanceDataReader as fdr
from django.core.management.base import BaseCommand

from stocks.models import Stock


# ── Fallback: 시가총액 + 시장 구분 기준 ─────────────────────────────
THRESHOLDS_KOSPI = [
    (10_000_000_000_000, ['안정형', '안정추구형']),
    ( 1_000_000_000_000, ['안정추구형', '위험중립형']),
    (   300_000_000_000, ['위험중립형', '적극투자형']),
]
THRESHOLDS_KOSDAQ = [
    (1_000_000_000_000, ['위험중립형', '적극투자형']),
]
DEFAULT_KOSPI  = ['적극투자형', '공격투자형']
DEFAULT_KOSDAQ = ['공격투자형']
DEFAULT_KONEX  = ['공격투자형']


def _suitable_types_fallback(market, marcap):
    if market == 'KOSPI':
        for threshold, types in THRESHOLDS_KOSPI:
            if marcap >= threshold:
                return types
        return DEFAULT_KOSPI
    elif market == 'KOSDAQ':
        for threshold, types in THRESHOLDS_KOSDAQ:
            if marcap >= threshold:
                return types
        return DEFAULT_KOSDAQ
    return DEFAULT_KONEX


# ── 재무지표 기반: risk_score → suitable_types ───────────────────────
def _suitable_types_from_score(score):
    if   score <= 20:  return ['안정형', '안정추구형']
    elif score <= 40:  return ['안정추구형', '위험중립형']
    elif score <= 58:  return ['위험중립형', '적극투자형']
    elif score <= 75:  return ['적극투자형', '공격투자형']
    else:              return ['공격투자형']


def _suitable_types(stock_obj, market, marcap):
    """StockFinancials 있으면 2단계 알고리즘 적용, 없으면 시가총액 fallback."""
    try:
        fin = stock_obj.financials
        from stocks.management.commands.update_financials import (
            calc_health_score, assign_suitable_types, detect_sector_type
        )
        sector_type = detect_sector_type(
            stock_obj.name, stock_obj.sector or '',
            fin.debt_ratio, fin.op_margin
        )
        health = calc_health_score(
            sector_type, fin.debt_ratio, fin.current_ratio, fin.op_margin, fin.roe
        )
        result = assign_suitable_types(health, fin.per, fin.pbr, fin.roe)
        if result is not None:
            return result
    except Exception:
        pass
    return _suitable_types_fallback(market, marcap)


def _category(market, marcap):
    if market == 'KOSPI':
        if marcap >= 10_000_000_000_000:
            return 'KOSPI 대형주'
        elif marcap >= 1_000_000_000_000:
            return 'KOSPI 중형주'
        else:
            return 'KOSPI 소형주'
    elif market == 'KOSDAQ':
        if marcap >= 1_000_000_000_000:
            return 'KOSDAQ 중형주'
        else:
            return 'KOSDAQ 소형주'
    return 'KONEX'


class Command(BaseCommand):
    help = 'KRX 전종목을 FinanceDataReader로 로드하고 성향 태깅'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='기존 종목 전체 삭제 후 재로드',
        )

    def handle(self, *args, **options):
        if options['flush']:
            count = Stock.objects.count()
            Stock.objects.all().delete()
            self.stdout.write(f'기존 {count}개 종목 삭제 완료')

        self.stdout.write('KRX 전종목 조회 중 (FinanceDataReader)...')
        try:
            df = fdr.StockListing('KRX')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'조회 실패: {e}'))
            return

        self.stdout.write(f'총 {len(df)}개 종목 수신')

        to_create, to_update_objs = [], []
        existing = {s.code: s for s in Stock.objects.all()}
        skipped = 0

        for _, row in df.iterrows():
            code   = str(row.get('Code', '')).strip().zfill(6)
            name   = str(row.get('Name', '')).strip()
            market = str(row.get('Market', 'KOSPI')).strip()
            close  = int(row.get('Close', 0) or 0)
            change = float(row.get('ChagesRatio', 0) or 0)
            marcap = int(row.get('Marcap', 0) or 0)

            if not code or not name or close <= 0:
                skipped += 1
                continue

            category = _category(market, marcap)

            if code in existing:
                s = existing[code]
                s.name       = name
                s.market     = market
                s.category   = category
                s.price      = close
                s.change     = round(change, 2)
                s.market_cap = marcap
                s.suitable_types = _suitable_types(s, market, marcap)
                to_update_objs.append(s)
            else:
                new_stock = Stock(
                    code=code, name=name, market=market,
                    category=category, price=close,
                    change=round(change, 2), market_cap=marcap,
                    suitable_types=_suitable_types_fallback(market, marcap),
                )
                to_create.append(new_stock)

        # 배치 처리
        if to_create:
            Stock.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update_objs:
            Stock.objects.bulk_update(
                to_update_objs,
                ['name', 'market', 'category', 'price', 'change', 'market_cap', 'suitable_types'],
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n완료: 신규 {len(to_create)}개 / 갱신 {len(to_update_objs)}개 / 스킵 {skipped}개'
        ))
