"""
python manage.py load_stocks          # 신규/갱신 (기존 유지)
python manage.py load_stocks --flush  # 전체 삭제 후 재로드
"""
import FinanceDataReader as fdr
from django.core.management.base import BaseCommand

from stocks.models import Stock

# ── 시가총액 기준 투자성향 분류 ──────────────────────────────
# Marcap 단위: 원(KRW)
THRESHOLDS_KOSPI = [
    (10_000_000_000_000, ['안정형', '안정추구형']),          # 10조+
    ( 1_000_000_000_000, ['안정추구형', '위험중립형']),       # 1조+
    (   300_000_000_000, ['위험중립형', '적극투자형']),       # 3000억+
]
THRESHOLDS_KOSDAQ = [
    ( 1_000_000_000_000, ['위험중립형', '적극투자형']),       # 1조+
]
DEFAULT_KOSPI  = ['적극투자형', '공격투자형']
DEFAULT_KOSDAQ = ['공격투자형']
DEFAULT_KONEX  = ['공격투자형']


def _suitable_types(market, marcap):
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

            suitable = _suitable_types(market, marcap)
            category = _category(market, marcap)

            if code in existing:
                s = existing[code]
                s.name           = name
                s.market         = market
                s.category       = category
                s.price          = close
                s.change         = round(change, 2)
                s.suitable_types = suitable
                to_update_objs.append(s)
            else:
                to_create.append(Stock(
                    code=code, name=name, market=market,
                    category=category, price=close,
                    change=round(change, 2), suitable_types=suitable,
                ))

        # 배치 처리
        if to_create:
            Stock.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update_objs:
            Stock.objects.bulk_update(
                to_update_objs,
                ['name', 'market', 'category', 'price', 'change', 'suitable_types'],
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n완료: 신규 {len(to_create)}개 / 갱신 {len(to_update_objs)}개 / 스킵 {skipped}개'
        ))
