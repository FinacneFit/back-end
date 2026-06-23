import os
import time
import requests

from django.conf import settings
from django.core.management.base import BaseCommand

from deposits.models import DepositProduct, DepositOption


FSS_BASE = 'https://finlife.fss.or.kr/finlifeapi/'

ENDPOINTS = {
    'deposit': {
        'label': '예금',
        'endpoint': 'depositProductsSearch',
    },
    'saving': {
        'label': '적금',
        'endpoint': 'savingProductsSearch',
    },
}

JOIN_DENY_MAP = {
    '1': '제한없음',
    '2': '서민전용',
    '3': '일부제한',
}

GROUPS = {
    '020000': '은행',
    '030300': '저축은행',
}


class Command(BaseCommand):
    help = '금융감독원 API에서 예금·적금 상품 데이터를 가져와 DB에 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['all', 'deposit', 'saving'],
            help='가져올 상품 유형: all, deposit, saving',
        )
        parser.add_argument(
            '--grp',
            type=str,
            default='020000',
            help='금융회사 그룹코드. 기본값: 020000 은행',
        )
        parser.add_argument(
            '--all-grp',
            action='store_true',
            help='은행 + 저축은행 전체 조회',
        )

    def handle(self, *args, **options):
        api_key = os.getenv('FSS_API_KEY', '').strip()

        if not api_key:
            self.stdout.write(self.style.ERROR('FSS_API_KEY가 설정되어 있지 않습니다.'))
            self.stdout.write(self.style.ERROR(f'현재 BASE_DIR: {settings.BASE_DIR}'))
            self.stdout.write(self.style.ERROR('back-end/.env 파일에 FSS_API_KEY가 있는지 확인하세요.'))
            return

        self.stdout.write(self.style.SUCCESS(f'FSS_API_KEY 확인 완료: 길이 {len(api_key)}'))

        selected_type = options['type']

        if selected_type == 'all':
            product_types = ['deposit', 'saving']
        else:
            product_types = [selected_type]

        group_codes = ['020000', '030300'] if options['all_grp'] else [options['grp']]

        total_created = 0
        total_updated = 0

        for group_code in group_codes:
            group_name = GROUPS.get(group_code, group_code)
            self.stdout.write(f'\n[{group_name}({group_code})] 조회 시작')

            for product_type in product_types:
                info = ENDPOINTS[product_type]

                created, updated = self._fetch_and_save(
                    api_key=api_key,
                    product_type=product_type,
                    product_label=info['label'],
                    endpoint=info['endpoint'],
                    group_code=group_code,
                )

                total_created += created
                total_updated += updated

        self.stdout.write(
            self.style.SUCCESS(
                f'\n완료 — 신규 {total_created}개, 갱신 {total_updated}개'
            )
        )

        self.stdout.write(f'현재 DB 상품 수: {DepositProduct.objects.count()}개')
        self.stdout.write(f'현재 DB 옵션 수: {DepositOption.objects.count()}개')

        deposit_count = DepositProduct.objects.filter(product_type='deposit').count()
        saving_count = DepositProduct.objects.filter(product_type='saving').count()

        self.stdout.write(f'예금 상품 수: {deposit_count}개')
        self.stdout.write(f'적금 상품 수: {saving_count}개')

    def _fetch_and_save(self, api_key, product_type, product_label, endpoint, group_code):
        base_list, option_list = self._fetch_all_pages(
            api_key=api_key,
            endpoint=endpoint,
            group_code=group_code,
        )

        option_map = {}

        for option in option_list:
            key = (
                str(option.get('fin_co_no', '')),
                str(option.get('fin_prdt_cd', '')),
            )
            option_map.setdefault(key, []).append(option)

        created = 0
        updated = 0

        for item in base_list:
            fin_co_no = str(item.get('fin_co_no', '')).strip()
            fin_prdt_cd = str(item.get('fin_prdt_cd', '')).strip()

            if not fin_co_no or not fin_prdt_cd:
                continue

            join_deny_raw = str(item.get('join_deny') or '1')
            join_deny = JOIN_DENY_MAP.get(join_deny_raw, join_deny_raw)

            product, is_created = DepositProduct.objects.update_or_create(
                fin_co_no=fin_co_no,
                fin_prdt_cd=fin_prdt_cd,
                product_type=product_type,
                defaults={
                    'kor_co_nm': item.get('kor_co_nm', '') or '',
                    'fin_prdt_nm': item.get('fin_prdt_nm', '') or '',
                    'join_way': item.get('join_way', '') or '',
                    'mtrt_int': item.get('mtrt_int', '') or '',
                    'spcl_cnd': item.get('spcl_cnd', '') or '',
                    'join_deny': join_deny,
                    'join_member': item.get('join_member', '') or '',
                    'etc_note': item.get('etc_note', '') or '',
                    'max_limit': str(item.get('max_limit', '') or ''),
                    'dcls_month': item.get('dcls_month', '') or '',
                },
            )

            if is_created:
                created += 1
            else:
                updated += 1

            raw_options = option_map.get((fin_co_no, fin_prdt_cd), [])
            self._save_options(product, raw_options)

        self.stdout.write(f'  {product_label}: 신규 {created}개 / 갱신 {updated}개')

        return created, updated

    def _fetch_all_pages(self, api_key, endpoint, group_code):
        url = f'{FSS_BASE}{endpoint}.json'

        all_base_list = []
        all_option_list = []

        for page_no in range(1, 21):
            params = {
                'auth': api_key,
                'topFinGrpNo': group_code,
                'pageNo': page_no,
            }

            self.stdout.write(f'  요청: {endpoint}.json / page={page_no} / grp={group_code}')

            data = None
            last_error = None

            for attempt in range(1, 4):
                try:
                    self.stdout.write(f'  시도 {attempt}/3')

                    response = requests.get(
                        url,
                        params=params,
                        timeout=60,
                    )

                    self.stdout.write(f'  HTTP 상태: {response.status_code}')
                    response.raise_for_status()

                    data = response.json()
                    break

                except requests.exceptions.ReadTimeout as error:
                    last_error = error
                    self.stdout.write(
                        self.style.WARNING(
                            f'  응답 시간 초과: {attempt}/3회 실패'
                        )
                    )
                    time.sleep(2)

                except requests.exceptions.RequestException as error:
                    last_error = error
                    self.stdout.write(
                        self.style.WARNING(
                            f'  API 요청 오류: {attempt}/3회 실패 - {error}'
                        )
                    )
                    time.sleep(2)

                except ValueError as error:
                    last_error = error
                    self.stdout.write(
                        self.style.ERROR(
                            f'  JSON 변환 실패: {error}'
                        )
                    )
                    break

            if data is None:
                self.stdout.write(
                    self.style.ERROR(
                        f'  API 요청 최종 실패: {last_error}'
                    )
                )
                return all_base_list, all_option_list

            result = data.get('result')

            if not result:
                self.stdout.write(self.style.ERROR('  result 필드가 없습니다.'))
                self.stdout.write(str(data)[:1000])
                return all_base_list, all_option_list

            err_cd = str(result.get('err_cd', '')).strip()
            err_msg = str(result.get('err_msg', '')).strip()

            self.stdout.write(f'  API 결과 코드: {err_cd}')
            self.stdout.write(f'  API 메시지: {err_msg}')

            if err_cd and err_cd != '000':
                self.stdout.write(self.style.ERROR('  금융감독원 API가 정상 응답을 주지 않았습니다.'))
                self.stdout.write(self.style.ERROR(f'  err_cd: {err_cd}'))
                self.stdout.write(self.style.ERROR(f'  err_msg: {err_msg}'))
                return all_base_list, all_option_list

            base_list = result.get('baseList') or []
            option_list = result.get('optionList') or []
            total_count = int(result.get('totalCount') or 0)

            all_base_list.extend(base_list)
            all_option_list.extend(option_list)

            self.stdout.write(
                f'  p{page_no}: 상품 {len(base_list)}개 / 옵션 {len(option_list)}개 '
                f'(누적 {len(all_base_list)}/{total_count})'
            )

            if not base_list:
                break

            if total_count and len(all_base_list) >= total_count:
                break

            time.sleep(0.2)

        return all_base_list, all_option_list

    def _save_options(self, product, raw_options):
        current_keys = set()

        for option in raw_options:
            try:
                save_trm = int(option.get('save_trm') or 0)
                intr_rate_type = str(option.get('intr_rate_type') or 'S')
                intr_rate_type_nm = option.get('intr_rate_type_nm', '단리') or '단리'
                intr_rate = float(option.get('intr_rate') or 0)
                intr_rate2 = float(option.get('intr_rate2') or 0)
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
                    'intr_rate': intr_rate,
                    'intr_rate2': intr_rate2,
                },
            )

            current_keys.add((save_trm, intr_rate_type))

        for old_option in DepositOption.objects.filter(product=product):
            key = (old_option.save_trm, old_option.intr_rate_type)

            if key not in current_keys:
                old_option.delete()