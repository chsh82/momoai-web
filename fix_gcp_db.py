"""GCP DB 종합 수정 스크립트 - instance/momoai.db (gunicorn이 사용하는 DB)"""
import sys
import os
sys.path.insert(0, '/home/chsh82/momoai_web')
os.chdir('/home/chsh82/momoai_web')

# gunicorn과 동일한 DATABASE_URL 설정 → Flask-SQLAlchemy가 instance/momoai.db를 사용
os.environ['DATABASE_URL'] = 'sqlite:///momoai.db'

from app import create_app
from app.models import db

app = create_app()

# ── 1. 누락된 테이블 생성 ──────────────────────────────────────────────────────
with app.app_context():
    print("=== 1단계: 누락 테이블 생성 (instance/momoai.db) ===")
    db.create_all()
    print("OK: db.create_all() 완료")
    # Flask app context에서 DB 경로 확인
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"   사용 중인 DB URI: {uri}")

# ── 2. 기존 테이블에 누락된 컬럼 추가 ──────────────────────────────────────────
import sqlite3

DB_PATH = '/home/chsh82/momoai_web/instance/momoai.db'
if not os.path.exists(DB_PATH):
    print(f"ERROR: DB 파일 없음: {DB_PATH}")
    sys.exit(1)

print(f"\n=== 2단계: 누락 컬럼 추가 ===")

COLUMNS = [
    # users 테이블
    "ALTER TABLE users ADD COLUMN role_level INTEGER",
    "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN locked_until DATETIME",
    "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN zoom_link VARCHAR(500)",
    "ALTER TABLE users ADD COLUMN zoom_token TEXT",
    "ALTER TABLE users ADD COLUMN profile_image_filename VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN profile_image_path VARCHAR(500)",
    # students 테이블
    "ALTER TABLE students ADD COLUMN tier VARCHAR(20)",
    "ALTER TABLE students ADD COLUMN tier_updated_at DATETIME",
    "ALTER TABLE students ADD COLUMN school VARCHAR(200)",
    "ALTER TABLE students ADD COLUMN birth_date DATE",
    "ALTER TABLE students ADD COLUMN is_temp BOOLEAN DEFAULT 0",
    # essays 테이블
    "ALTER TABLE essays ADD COLUMN attachment_filename VARCHAR(255)",
    "ALTER TABLE essays ADD COLUMN attachment_path VARCHAR(500)",
    # assignments 테이블
    "ALTER TABLE assignments ADD COLUMN target_student_id VARCHAR(36)",
    # books 테이블
    "ALTER TABLE books ADD COLUMN recommendation_reason TEXT",
    # videos 테이블
    "ALTER TABLE videos ADD COLUMN description TEXT",
    # harkness_boards 테이블
    "ALTER TABLE harkness_boards ADD COLUMN post_format VARCHAR(20)",
    # harkness_comments 테이블
    "ALTER TABLE harkness_comments ADD COLUMN question_number INTEGER",
    # harkness_posts 테이블
    "ALTER TABLE harkness_posts ADD COLUMN question1 TEXT",
    "ALTER TABLE harkness_posts ADD COLUMN question1_intent TEXT",
    "ALTER TABLE harkness_posts ADD COLUMN question2 TEXT",
    "ALTER TABLE harkness_posts ADD COLUMN question2_intent TEXT",
    "ALTER TABLE harkness_posts ADD COLUMN question3 TEXT",
    "ALTER TABLE harkness_posts ADD COLUMN question3_intent TEXT",
    # weekly_evaluations 테이블
    "ALTER TABLE weekly_evaluations ADD COLUMN participation_score INTEGER DEFAULT 0",
    "ALTER TABLE weekly_evaluations ADD COLUMN understanding_score INTEGER DEFAULT 0",
    # reading_mbti_tests 테이블
    "ALTER TABLE reading_mbti_tests ADD COLUMN version VARCHAR(20) DEFAULT 'standard'",
]

conn = sqlite3.connect(DB_PATH)
ok_count = 0
skip_count = 0
for sql in COLUMNS:
    try:
        conn.execute(sql)
        print(f"OK:   {sql[:80]}")
        ok_count += 1
    except Exception as e:
        err = str(e)[:60]
        if 'duplicate column' in err or 'no such table' in err:
            print(f"SKIP: {sql[:60]} ({err})")
        else:
            print(f"ERR:  {sql[:60]} ({err})")
        skip_count += 1

conn.commit()

# ── 3. 현재 테이블 목록 확인 ───────────────────────────────────────────────────
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(f"\n=== 3단계: 현재 테이블 목록 ({len(tables)}개) ===")
print(', '.join(tables))

conn.close()

print(f"\n=== 완료: {ok_count}개 추가, {skip_count}개 건너뜀 ===")
