# MOMOAI v4.1.0 - Gunicorn 설정
# gunicorn -c gunicorn_config.py "app:create_app('production')"
#
# 주의(2026-08-30): 실제 systemd 유닛(momoai.service)은 이 파일을 참조하지
# 않고 gunicorn CLI 플래그(--bind --workers --timeout --log-level)를 직접
# 지정해서 실행한다. 즉 이 파일은 현재 프로덕션에 적용되지 않는 문서 성격의
# 설정이다. 실제로 이 파일로 전환하려면 systemd 유닛의 ExecStart를
# "gunicorn -c gunicorn_config.py \"app:create_app('production')\"" 로 바꿔야 한다.

import multiprocessing
import os

# 서버 소켓
bind = "127.0.0.1:8000"  # Nginx가 프록시할 포트
backlog = 2048

# 워커 프로세스
workers = multiprocessing.cpu_count() * 2 + 1  # CPU 코어 수에 따라 자동 조정
worker_class = "sync"  # 또는 "gevent", "eventlet"
worker_connections = 1000
max_requests = 1000  # 메모리 누수 방지를 위해 1000개 요청마다 재시작
max_requests_jitter = 50  # 재시작 시점 분산
timeout = 300  # 요청 타임아웃 (초) — Gemini OCR/Claude 첨삭 등 장시간 처리 대응
keepalive = 5  # Keep-Alive 연결 유지 시간

# 로깅 - 이 파일이 실제로 쓰이지 않아 아래 경로는 한 번도 생성된 적이 없다.
# 실제 운영 로그는 journalctl -u momoai로 조회한다(app/__init__.py의
# configure_logging 참고). 이 파일을 다시 쓰게 되면 그때 경로를 재검토할 것.
# accesslog = "/var/log/momoai/access.log"
# errorlog = "/var/log/momoai/error.log"
loglevel = "info"  # debug, info, warning, error, critical
# access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 프로세스 이름
proc_name = "momoai"

# 데몬 모드 (systemd 사용 시 False)
daemon = False

# PID 파일
pidfile = "/var/run/momoai.pid"

# 사용자/그룹 (보안을 위해 권한이 낮은 사용자로 실행)
# user = "momoai"
# group = "momoai"

# 임시 파일 디렉토리
tmp_upload_dir = "/tmp"

# 프리로드 (메모리 절약)
preload_app = True

# 재시작 시 그레이스풀 타임아웃 (in-flight 첨삭/OCR 보호)
graceful_timeout = 300

# SSL/TLS (Nginx가 처리하므로 보통 불필요)
# keyfile = "/etc/ssl/private/momoai.key"
# certfile = "/etc/ssl/certs/momoai.crt"

# 환경 변수
raw_env = [
    "FLASK_ENV=production",
]

# 서버 훅 (선택사항)
def on_starting(server):
    """서버 시작 시"""
    print("🚀 MOMOAI v4.1.0 서버 시작 중...")

def on_reload(server):
    """리로드 시"""
    print("🔄 서버 리로드 중...")

def worker_int(worker):
    """워커 인터럽트"""
    print(f"⚠️  워커 {worker.pid} 인터럽트")

def worker_abort(worker):
    """워커 중단"""
    print(f"❌ 워커 {worker.pid} 중단됨")
