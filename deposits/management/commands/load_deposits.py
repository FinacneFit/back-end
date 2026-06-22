"""
python manage.py load_deposits

금융감독원 금융상품통합비교공시 API에서 예금·적금 데이터를 가져와 DB에 저장.
- 상품 고유키: (fin_co_no, fin_prdt_cd)
- update_or_create 방식으로 중복 없이 신규/갱신 처리
- 옵션(기간·금리)도 마찬가지로 중복 없이 upsert

옵션:
  --grp     금융회사 그룹코드 (기본값 020000=은행, 030300=저축은행)
  --all-grp 은행+저축은행 전체 조회
"""
import os
import time
import requests
from django.core.management.base import BaseCommand
from deposits.models import DepositProduct, DepositOption

FSS_BASE = 'https://finlife.fss.or.kr/finlifeapi/'

ENDPOINTS = {
    'deposit': 'depositProductsSearch',
    'saving':  'savingProductsSearch',
}

JOIN_DENY_MAP = {
    '1': '제한없음',
    '2': '서민전용',
    '3': '일부제한',
}

GRP_NAMES = {
    '020000': '은행',
    '030300': '저축은행',
    '030200': '여신전문금융사',
    '050000': '보험',
    '060000': '금융투자',
}


class Command(BaseCommand):
    help = 'FSS API에서 예금·적금 상품 데이터를 가져와 DB에 저장'

    def add_arguments(self, parser):
        parser.add_argument(
            '--grp', type=str, default='020000',
            help='금융회사 그룹코드 (기본: 020000=은행)',
        )
        parser.add_argument(
            '--all-grp', action='store_true',
            help='은행 + 저축은행 전체 조회',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('FSS_API_KEY', '')
        if not api_key:
            self.stdout.write(self.style.ERROR(
                'FSS_API_KEY가 .env에 설정되어 있지 않습니다.\n'
                '금융감독원 금융상품통합비교공시(https://finlife.fss.or.kr)에서\n'
                'API 키를 발급받아 .env에 FSS_API_KEY=<키> 형태로 추가해 주세요.'
            ))
            return

        grp_list = list(GRP_NAMES.keys()) if options['all_grp'] else [options['grp']]

        total_created = total_updated = 0
        for grp in grp_list:
            grp_name = GRP_NAMES.get(grp, grp)
            self.stdout.write(f'\n[{grp_name}({grp})] 조회 시작')
            for ptype, endpoint in ENDPOINTS.items():
                c, u = self._fetch_and_save(api_key, ptype, endpoint, grp)
                total_created += c
                total_updated += u

        self.stdout.write(self.style.SUCCESS(
            f'\n완료 — 신규 {total_created}개, 갱신 {total_updated}개'
        ))

    # ── 핵심: API 호출 + 저장 ────────────────────────────────────────
    def _fetch_and_save(self, api_key: str, product_type: str, endpoint: str, fin_grp_no: str):
        all_base, all_opts = self._fetch_all_pages(api_key, endpoint, fin_grp_no)

        # 옵션을 (fin_co_no, fin_prdt_cd) → list 로 인덱싱
        opt_map: dict = {}
        for opt in all_opts:
            key = (opt['fin_co_no'], opt['fin_prdt_cd'])
            opt_map.setdefault(key, []).append(opt)

        created = updated = 0
        type_label = '예금' if product_type == 'deposit' else '적금'

        for p in all_base:
            fin_co_no   = p.get('fin_co_no', '')
            fin_prdt_cd = p.get('fin_prdt_cd', '')
            if not fin_co_no or not fin_prdt_cd:
                continue

            join_deny_raw = str(p.get('join_deny') or '1')
            join_deny = JOIN_DENY_MAP.get(join_deny_raw, join_deny_raw)

            product_obj, is_new = DepositProduct.objects.update_or_create(
                fin_co_no=fin_co_no,
                fin_prdt_cd=fin_prdt_cd,
                defaults={
                    'kor_co_nm':    p.get('kor_co_nm', ''),
                    'fin_prdt_nm':  p.get('fin_prdt_nm', ''),
                    'product_type': product_type,
                    'join_way':     p.get('join_way', '') or '',
                    'mtrt_int':     p.get('mtrt_int', '') or '',
                    'spcl_cnd':     p.get('spcl_cnd', '') or '',
                    'join_deny':    join_deny,
                    'join_member':  p.get('join_member', '') or '',
                    'etc_note':     p.get('etc_note', '') or '',
                    'max_limit':    str(p.get('max_limit', '') or ''),
                    'dcls_month':   p.get('dcls_month', '') or '',
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

            self._save_options(product_obj, opt_map.get((fin_co_no, fin_prdt_cd), []))

        self.stdout.write(
            f'  {type_label}: 신규 {created}개 / 갱신 {updated}개'
        )
        return created, updated

    def _fetch_all_pages(self, api_key: str, endpoint: str, fin_grp_no: str):
        """FSS API 전체 페이지 수집. 최대 20페이지까지 안전하게 순회."""
        url = f'{FSS_BASE}{endpoint}.json'
        all_base: list = []
        all_opts: list = []

        for page in range(1, 21):
            params = {
                'auth':        api_key,
                'topFinGrpNo': fin_grp_no,
                'pageNo':      page,
            }
            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  페이지 {page} 조회 실패: {e}'))
                break

            result    = data.get('result', {})
            base_list = result.get('baseList', [])
            opt_list  = result.get('optionList', [])

            all_base.extend(base_list)
            all_opts.extend(opt_list)

            # 마지막 페이지 판단
            total = int(result.get('totalCount', 0) or 0)
            fetched = len(all_base)
            self.stdout.write(f'  p{page}: 상품 {len(base_list)}개 (누적 {fetched}/{total})')

            if not base_list or fetched >= total:
                break

            time.sleep(0.3)   # API rate limit 방어

        return all_base, all_opts

    def _save_options(self, product: DepositProduct, raw_opts: list):
        """기간·금리 옵션 upsert + 삭제된 옵션 제거."""
        current_keys: set = set()

        for opt in raw_opts:
            try:
                save_trm        = int(opt.get('save_trm') or 0)
                intr_rate_type  = str(opt.get('intr_rate_type') or 'S')
                intr_rate       = float(opt.get('intr_rate')  or 0)
                intr_rate2      = float(opt.get('intr_rate2') or 0)
                intr_rate_type_nm = opt.get('intr_rate_type_nm', '단리')
            except (TypeError, ValueError):
                continue

            if save_trm <= 0:
                continue

            DepositOption.objects.update_or_create(
                product=product,
                save_trm=save_trm,
                intr_rate_type=intr_rate_type,
                defaults={
                    'intr_rate_type_nm': intr_rate_type_nm,
                    'intr_rate':  intr_rate,
                    'intr_rate2': intr_rate2,
                },
            )
            current_keys.add((save_trm, intr_rate_type))

        # API에 더 이상 없는 옵션 삭제
        for old in DepositOption.objects.filter(product=product):
            if (old.save_trm, old.intr_rate_type) not in current_keys:
                old.delete()
