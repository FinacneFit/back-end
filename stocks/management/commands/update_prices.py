"""
python manage.py update_prices
장중/장마감 직후 FinanceDataReader로 전종목 현재가(종가) 일괄 갱신.
"""
import FinanceDataReader as fdr
from django.core.management.base import BaseCommand

from stocks.models import Stock


class Command(BaseCommand):
    help = 'FinanceDataReader로 DB 전종목 현재가 일괄 갱신'

    def handle(self, *args, **options):
        self.stdout.write('KRX 시세 조회 중...')
        try:
            df = fdr.StockListing('KRX')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'조회 실패: {e}'))
            return

        updated, skipped = 0, 0
        for _, row in df.iterrows():
            code  = str(row.get('Code', '')).strip().zfill(6)
            close = int(row.get('Close', 0) or 0)
            change = float(row.get('ChagesRatio', 0) or 0)
            if not code or close <= 0:
                skipped += 1
                continue
            cnt = Stock.objects.filter(code=code).update(
                price=close, change=round(change, 2)
            )
            updated += cnt

        self.stdout.write(self.style.SUCCESS(
            f'완료: {updated}개 갱신 / {skipped}개 스킵'
        ))
