"""
두 가지 주가 갱신 잡을 관리:

  1. portfolio_price_update  — 매 1분, 거래시간(09:00~15:30)에만
     KIS 모의투자 API로 (포트폴리오 보유 종목 + 5개 성향별 추천 종목) 현재가 갱신

  2. daily_close_update      — 평일 16:00 KST
     FinanceDataReader로 KRX 전종목 종가 일괄 갱신
"""
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
_scheduler = None


# ── 잡 3: 예금·적금 상품 일일 갱신 (FSS API) ────────────────────────

def _update_deposits():
    """매일 새벽 2시 FSS API 데이터 갱신"""
    import os
    if not os.environ.get('FSS_API_KEY'):
        return
    try:
        from django.core.management import call_command
        call_command('load_deposits')
        logger.info('[FSS] 예금·적금 상품 갱신 완료')
    except Exception as e:
        logger.error(f'[FSS] 예금·적금 갱신 실패: {e}')

INVESTMENT_TYPES = ['안정형', '안정추구형', '위험중립형', '적극투자형', '공격투자형']


# ── 잡 1: 포트폴리오 + 추천 종목 1분 갱신 (KIS API) ──────────────────

def _collect_target_codes():
    """갱신 대상 종목코드 수집: 포트폴리오 보유 + 성향별 추천 상위 3개"""
    from portfolio.models import PortfolioHolding
    from .models import Stock

    # ① 전체 사용자 포트폴리오 종목
    portfolio_codes = set(
        PortfolioHolding.objects
        .values_list('stock__code', flat=True)
        .distinct()
    )

    # ② 5개 성향별 추천 종목 (상위 3개씩) — Python 필터 (SQLite JSON 제약)
    all_stocks = list(Stock.objects.values('code', 'suitable_types'))
    rec_codes = set()
    for itype in INVESTMENT_TYPES:
        matched = [s['code'] for s in all_stocks if itype in s['suitable_types']][:5]
        rec_codes.update(matched)

    return list(portfolio_codes | rec_codes)


def _update_portfolio_prices():
    from .kis_api import fetch_price, is_trading_hours
    from .models import Stock

    if not is_trading_hours():
        return

    codes = _collect_target_codes()
    if not codes:
        return

    logger.info(f'[KIS] {len(codes)}개 종목 갱신 시작 (포트폴리오 + 추천)')
    updated = 0

    for code in codes:
        price, change = fetch_price(code)
        if price:
            Stock.objects.filter(code=code).update(price=price, change=change)
            updated += 1
        time.sleep(1.1)   # KIS 모의투자 rate limit: 초당 1건

    logger.info(f'[KIS] 갱신 완료 {updated}/{len(codes)}')


# ── 잡 2: 전종목 종가 일괄 갱신 (FinanceDataReader) ───────────────────

def _update_close_prices():
    import FinanceDataReader as fdr
    from .models import Stock

    logger.info('[FDR] 전종목 종가 갱신 시작')
    try:
        df = fdr.StockListing('KRX')
    except Exception as e:
        logger.error(f'[FDR] 데이터 조회 실패: {e}')
        return

    updated = 0
    for _, row in df.iterrows():
        code   = str(row.get('Code', '')).strip().zfill(6)
        close  = int(row.get('Close', 0) or 0)
        change = float(row.get('ChagesRatio', 0) or 0)
        if not code or close <= 0:
            continue
        cnt = Stock.objects.filter(code=code).update(
            price=close, change=round(change, 2)
        )
        updated += cnt

    logger.info(f'[FDR] 전종목 종가 갱신 완료: {updated}개')


# ── 스케줄러 시작/종료 ──────────────────────────────────────────────

def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    import pytz
    tz = pytz.timezone('Asia/Seoul')
    _scheduler = BackgroundScheduler(timezone=tz)

    _scheduler.add_job(
        _update_portfolio_prices,
        IntervalTrigger(minutes=1, timezone=tz),
        id='portfolio_price_update',
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _update_close_prices,
        CronTrigger(hour=16, minute=0, day_of_week='mon-fri', timezone=tz),
        id='daily_close_update',
        replace_existing=True,
    )
    _scheduler.add_job(
        _update_deposits,
        CronTrigger(hour=2, minute=0, timezone=tz),
        id='daily_deposit_update',
        replace_existing=True,
    )

    _scheduler.start()
    logger.info('[스케줄러] 시작 — KIS 1분 갱신(포트폴리오+추천) + FDR 16:00 종가 갱신 + FSS 02:00 예금 갱신')


def shutdown():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
