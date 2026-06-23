import os
from django.apps import AppConfig


class StocksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'stocks'

    def ready(self):
        import sys
        # 마이그레이션·셸 등 관리 커맨드에서는 스케줄러 미실행
        mgmt_cmds = {'migrate', 'makemigrations', 'shell', 'createsuperuser',
                     'collectstatic', 'test', 'check', 'load_stocks', 'update_prices',
                     'load_deposits', 'load_survey'}
        if any(cmd in sys.argv for cmd in mgmt_cmds):
            return

        # runserver: 리로더가 두 번 호출하므로 자식 프로세스(RUN_MAIN=true)에서만 실행
        if 'runserver' in sys.argv:
            if os.environ.get('RUN_MAIN') != 'true':
                return

        from . import scheduler
        scheduler.start()
