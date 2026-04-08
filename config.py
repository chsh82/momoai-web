import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent

# .env 파일 명시적 경로로 로드 (실행 디렉터리와 무관하게 동작)
load_dotenv(BASE_DIR / '.env')
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR / 'outputs'
HTML_FOLDER = OUTPUT_FOLDER / 'html'
PDF_FOLDER = OUTPUT_FOLDER / 'pdf'
POST_FILES_FOLDER = UPLOAD_FOLDER / 'post_files'
POST_IMAGES_FOLDER = UPLOAD_FOLDER / 'post_images'
MATERIALS_FOLDER = UPLOAD_FOLDER / 'materials'
CORRECTION_ATTACHMENTS_FOLDER = UPLOAD_FOLDER / 'correction_attachments'
MOMOAI_DOC_PATH = Path(os.environ.get('MOMOAI_DOC_PATH') or str(BASE_DIR / 'docs' / 'MOMOAI_v3_3_0_final.md'))
MOMOAI_STANDARD_DOC_PATH = Path(os.environ.get('MOMOAI_STANDARD_DOC_PATH') or str(BASE_DIR / 'docs' / 'MOMOAI_v3_3_basic.md'))
MOMOAI_ELEM_DOC_PATH = Path(os.environ.get('MOMOAI_ELEM_DOC_PATH') or str(BASE_DIR / 'docs' / 'MOMOAI_elem.md'))

# API 키 - 환경 변수에서만 로드 (보안)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# SMS/카카오톡 API 설정 - 환경 변수에서만 로드 (보안)
SMS_API_KEY = os.environ.get('SMS_API_KEY')
SMS_USER_ID = os.environ.get('SMS_USER_ID')
SMS_SENDER = os.environ.get('SMS_SENDER')

KAKAO_API_KEY = os.environ.get('KAKAO_API_KEY')
KAKAO_USER_ID = os.environ.get('KAKAO_USER_ID')
KAKAO_SENDER_KEY = os.environ.get('KAKAO_SENDER_KEY')

# 네이버 도서 검색 API
NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

# 토스 페이먼츠
TOSS_CLIENT_KEY = os.environ.get('TOSS_CLIENT_KEY')
TOSS_SECRET_KEY = os.environ.get('TOSS_SECRET_KEY')

# 업로드 제한
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB (수동첨삭 이미지 10개 대응)
ALLOWED_EXTENSIONS = {'xlsx', 'csv'}
ALLOWED_MATERIAL_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'hwp', 'txt', 'zip', 'png', 'jpg', 'jpeg'}

# 폴더 생성
for folder in [UPLOAD_FOLDER, HTML_FOLDER, PDF_FOLDER, POST_FILES_FOLDER, POST_IMAGES_FOLDER,
               MATERIALS_FOLDER, CORRECTION_ATTACHMENTS_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)


class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database 설정
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{BASE_DIR / "instance" / "momoai.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Login 설정
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30  # 30일

    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    UPLOAD_FOLDER = str(UPLOAD_FOLDER)
    HTML_FOLDER = str(HTML_FOLDER)
    PDF_FOLDER = str(PDF_FOLDER)
    POST_FILES_FOLDER = str(POST_FILES_FOLDER)
    POST_IMAGES_FOLDER = str(POST_IMAGES_FOLDER)
    MATERIALS_FOLDER = str(MATERIALS_FOLDER)
    CORRECTION_ATTACHMENTS_FOLDER = str(CORRECTION_ATTACHMENTS_FOLDER)

    # MOMOAI 설정
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY
    GEMINI_API_KEY = GEMINI_API_KEY
    MOMOAI_DOC_PATH = str(MOMOAI_DOC_PATH)
    MOMOAI_STANDARD_DOC_PATH = str(MOMOAI_STANDARD_DOC_PATH)
    MOMOAI_ELEM_DOC_PATH = str(MOMOAI_ELEM_DOC_PATH)

    # SMS/카카오톡 API 설정
    SMS_API_KEY = SMS_API_KEY
    SMS_USER_ID = SMS_USER_ID
    SMS_SENDER = SMS_SENDER
    KAKAO_API_KEY = KAKAO_API_KEY
    KAKAO_USER_ID = KAKAO_USER_ID
    KAKAO_SENDER_KEY = KAKAO_SENDER_KEY
    NAVER_CLIENT_ID = NAVER_CLIENT_ID
    NAVER_CLIENT_SECRET = NAVER_CLIENT_SECRET
    TOSS_CLIENT_KEY = TOSS_CLIENT_KEY
    TOSS_SECRET_KEY = TOSS_SECRET_KEY

    # 푸시 알림 (PWA) — env var에서 \n을 실제 줄바꿈으로 복원
    VAPID_PRIVATE_KEY = (os.environ.get('VAPID_PRIVATE_KEY') or '').replace('\\n', '\n') or None
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
    VAPID_CLAIMS_SUB = os.environ.get('VAPID_CLAIMS_SUB') or 'mailto:contact@momoai.kr'

    # 이메일 설정 (Gmail SMTP 예시)
    # .env에 아래 항목 추가 시 이메일 인증 활성화됨
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SQLALCHEMY_ECHO = True  # SQL 쿼리 로깅


class ProductionConfig(Config):
    """프로덕션 환경 설정"""
    DEBUG = False
    # 프로덕션에서는 PostgreSQL 사용
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://user:password@localhost/momoai'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
