"""
평일 16:00 KST에 KRX 전종목 종가를 FinanceDataReader로 일괄 갱신.
Django runserver / gunicorn 시작 시 apps.py → start() 자동 호출.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = None


def _update_close_prices():
    import FinanceDataReader as fdr
    from .models import Stock

    logger.info('[스케줄러] 종가 일괄 갱신 시작')
    try:
        df = fdr.StockListing('KRX')
    except Exception as e:
        logger.error(f'[스케줄러] 데이터 조회 실패: {e}')
        return

    updated = 0
    for _, row in df.iterrows():
        code  = str(row.get('Code', '')).strip().zfill(6)
        close = int(row.get('Close', 0) or 0)
        change = float(row.get('ChagesRatio', 0) or 0)
        if not code or close <= 0:
            continue
        cnt = Stock.objects.filter(code=code).update(
            price=close, change=round(change, 2)
        )
        updated += cnt

    logger.info(f'[스케줄러] 종가 갱신 완료: {updated}개')


def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    import pytz
    _scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Seoul'))
    _scheduler.add_job(
        _update_close_prices,
        CronTrigger(hour=16, minute=0, day_of_week='mon-fri'),
        id='daily_close_update',
        replace_existing=True,
    )
    _scheduler.start()
    logger.info('[스케줄러] 시작 — 매 평일 16:00 KST 종가 자동 갱신')


def shutdown():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
