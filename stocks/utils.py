import yfinance as yf

_SECTOR_MAP = {
    'Technology':           'IT',
    'Communication Services': '통신',
    'Consumer Cyclical':    '소비재',
    'Consumer Defensive':   '필수소비재',
    'Financial Services':   '금융',
    'Healthcare':           '바이오',
    'Basic Materials':      '소재',
    'Industrials':          '산업재',
    'Energy':               '에너지',
    'Real Estate':          '부동산',
    'Utilities':            '유틸리티',
}


def fetch_price(code):
    """
    code: 6자리 종목코드 (e.g. '005930')
    KOSPI(.KS) → KOSDAQ(.KQ) 순으로 시도.
    Returns (price: int, change: float) or (None, None)
    """
    for suffix in ('.KS', '.KQ'):
        try:
            fi = yf.Ticker(code + suffix).fast_info
            price = fi.last_price
            if not price or price <= 0:
                continue
            prev = fi.previous_close or fi.regular_market_previous_close
            change = round((price - prev) / prev * 100, 2) if prev else 0.0
            return int(price), change
        except Exception:
            continue
    return None, None


def fetch_stock_info(code):
    """
    6자리 코드로 yfinance에서 종목 전체 정보를 가져온다.
    DB에 없는 신규 종목 등록 시 사용.
    Returns dict {'name', 'code', 'price', 'change', 'category'} or None
    """
    for suffix in ('.KS', '.KQ'):
        try:
            ticker = yf.Ticker(code + suffix)

            # 가격 (빠른 경로)
            fi = ticker.fast_info
            price = fi.last_price
            if not price or price <= 0:
                continue
            prev = fi.previous_close or fi.regular_market_previous_close
            change = round((price - prev) / prev * 100, 2) if prev else 0.0

            # 이름 · 카테고리 (info 경로)
            try:
                info     = ticker.info
                name     = info.get('shortName') or info.get('longName') or code
                sector   = info.get('sector', '')
                q_type   = fi.quote_type or ''
                category = _SECTOR_MAP.get(sector, 'ETF' if q_type == 'ETF' else '주식')
            except Exception:
                name, category = code, '주식'

            return {
                'code':     code,
                'name':     name,
                'price':    int(price),
                'change':   change,
                'category': category,
            }
        except Exception:
            continue
    return None
