"""GCP DB 종합 수정 스크립트 - 누락 테이블 생성 + 누락 컬럼 추가"""
import sys
import os
sys.path.insert(0, '/home/chsh82/momoai_web')
os.chdir('/home/chsh82/momoai_web')

from app import create_app
from app.models import db

app = create_app()

# ── 1. 누락된 테이블 생성 (db.create_all은 이미 있는 테이블은 건드리지 않음) ──
with app.app_context():
    print("=== 1단계: 누락 테이블 생성 ===")
    db.create_all()
    print("OK: db.create_all() 완료")

# ── 2. 기존 테이블에 누락된 컬럼 추가 ──
import sqlite3

DB_PATH = '/home/chsh82/momoai_web/instance/momoai.db'
if not os.path.exists(DB_PATH):
    print(f"ERROR: DB 파일 없음: {DB_PATH}")
    sys.exit(1)

print(f"\n=== 2단계: 누락 컬럼 추가 ({DB_PATH}) ===")

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
conn.close()

print(f"\n=== 완료: {ok_count}개 추가, {skip_count}개 건너뜀 ===")
