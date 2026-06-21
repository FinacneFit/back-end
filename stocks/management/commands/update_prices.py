from django.core.management.base import BaseCommand
from stocks.models import Stock
from stocks.utils import fetch_price


class Command(BaseCommand):
    help = 'yfinance로 DB의 모든 주식 현재가·등락률 업데이트'

    def handle(self, *args, **options):
        stocks = Stock.objects.all()
        ok, fail = 0, 0

        self.stdout.write(f'총 {stocks.count()}개 종목 업데이트 시작...\n')

        for stock in stocks:
            price, change = fetch_price(stock.code)
            if price:
                stock.price  = price
                stock.change = change
                stock.save(update_fields=['price', 'change'])
                sign = '+' if change >= 0 else ''
                self.stdout.write(
                    f'  ✓ {stock.name:12s} {price:>10,}원  ({sign}{change:.2f}%)'
                )
                ok += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'  ✗ {stock.name} ({stock.code}) — 가격 조회 실패')
                )
                fail += 1

        self.stdout.write(
            self.style.SUCCESS(f'\n완료: {ok}개 성공 / {fail}개 실패')
        )
