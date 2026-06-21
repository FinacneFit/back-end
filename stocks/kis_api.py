"""
KIS Developers 모의투자 REST API 클라이언트.
- 접근 토큰: 메모리 + 파일 이중 캐싱 (24시간, 서버 재시작 후에도 재사용)
- 주식 현재가 조회 (tr_id: FHKST01010100)
"""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import pytz
import requests

logger = logging.getLogger(__name__)

_BASE  = 'https://openapivts.koreainvestment.com:29443'
_KEY   = os.environ.get('APP_KEY', '')
_SEC   = os.environ.get('APP_SECRET', '')

# 토큰 캐시 파일 경로 (BASE_DIR 기준)
_CACHE_FILE = Path(__file__).resolve().parent.parent / '.kis_token_cache.json'

# 메모리 캐시
_mem = {'token': None, 'expires_at': 0.0}

KST = pytz.timezone('Asia/Seoul')


# ── 토큰 ──────────────────────────────────────────────────────────

def _load_file_cache():
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            if time.time() < data.get('expires_at', 0) - 300:
                return data['token'], data['expires_at']
    except Exception:
        pass
    return None, 0.0


def _save_file_cache(token, expires_at):
    try:
        _CACHE_FILE.write_text(json.dumps({'token': token, 'expires_at': expires_at}))
    except Exception as e:
        logger.warning(f'[KIS] 토큰 캐시 저장 실패: {e}')


def _get_token() -> str | None:
    now = time.time()

    # 1) 메모리 캐시
    if _mem['token'] and now < _mem['expires_at'] - 300:
        return _mem['token']

    # 2) 파일 캐시 (서버 재시작 후에도 재사용)
    token, expires_at = _load_file_cache()
    if token:
        _mem['token']      = token
        _mem['expires_at'] = expires_at
        logger.info('[KIS] 파일 캐시에서 토큰 로드')
        return token

    # 3) 신규 발급
    try:
        resp = requests.post(
            f'{_BASE}/oauth2/tokenP',
            json={'grant_type': 'client_credentials', 'appkey': _KEY, 'appsecret': _SEC},
            timeout=10,
        )
        data = resp.json()
        token = data.get('access_token')
        if not token:
            logger.error(f'[KIS] 토큰 발급 실패: {data}')
            return None

        expires_at = now + int(data.get('expires_in', 86400))
        _mem['token']      = token
        _mem['expires_at'] = expires_at
        _save_file_cache(token, expires_at)
        logger.info('[KIS] 새 접근 토큰 발급 완료')
        return token

    except Exception as e:
        logger.error(f'[KIS] 토큰 발급 오류: {e}')
        return None


# ── 현재가 조회 ────────────────────────────────────────────────────

def fetch_price(code: str) -> tuple[int | None, float]:
    """
    종목코드(6자리)로 KIS 모의투자 현재가 조회.
    Returns (price: int, change_pct: float) | (None, 0.0)
    """
    token = _get_token()
    if not token:
        return None, 0.0

    try:
        resp = requests.get(
            f'{_BASE}/uapi/domestic-stock/v1/quotations/inquire-price',
            headers={
                'Authorization': f'Bearer {token}',
                'appkey':    _KEY,
                'appsecret': _SEC,
                'tr_id':     'FHKST01010100',
                'custtype':  'P',
            },
            params={
                'FID_COND_MRKT_DIV_CODE': 'J',
                'FID_INPUT_ISCD': code,
            },
            timeout=5,
        )
        data = resp.json()
        if data.get('rt_cd') != '0':
            logger.warning(f'[KIS] {code} 조회 실패: {data.get("msg1")}')
            return None, 0.0

        out    = data['output']
        price  = int(out.get('stck_prpr', 0) or 0)
        change = float(out.get('prdy_ctrt', 0) or 0)
        return (price, round(change, 2)) if price > 0 else (None, 0.0)

    except Exception as e:
        logger.error(f'[KIS] {code} 요청 오류: {e}')
        return None, 0.0


# ── 거래 시간 확인 ─────────────────────────────────────────────────

def is_trading_hours() -> bool:
    """평일 09:00 ~ 15:30 KST 여부"""
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    return (9, 0) <= (h, m) <= (15, 30)
