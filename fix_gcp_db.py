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

# ── 3. harkness_posts.content NOT NULL 제약 해제 ───────────────────────────────
print(f"\n=== 3단계: harkness_posts.content nullable 수정 ===")
try:
    cur = conn.execute("PRAGMA table_info(harkness_posts)")
    cols = cur.fetchall()
    # cols: (cid, name, type, notnull, dflt_value, pk)
    content_col = next((c for c in cols if c[1] == 'content'), None)
    if content_col is None:
        print("SKIP: harkness_posts 테이블 없음")
    elif content_col[3] == 0:
        print("SKIP: content 이미 nullable")
    else:
        print("FIXING: content NOT NULL → nullable (테이블 재생성)")
        # question1~3 컬럼이 이미 추가됐는지 확인
        col_names = [c[1] for c in cols]
        has_q = 'question1' in col_names
        # question1~3 없으면 NULL로 채움
        q_select = ("question1, question1_intent, question2, question2_intent, "
                    "question3, question3_intent") if has_q else (
                    "NULL AS question1, NULL AS question1_intent, "
                    "NULL AS question2, NULL AS question2_intent, "
                    "NULL AS question3, NULL AS question3_intent")
        conn.executescript(f"""
            CREATE TABLE harkness_posts_new (
                post_id    VARCHAR(36) PRIMARY KEY,
                board_id   VARCHAR(36) NOT NULL,
                author_id  VARCHAR(36) NOT NULL,
                title      VARCHAR(200) NOT NULL,
                content    TEXT,
                question1  TEXT,
                question1_intent TEXT,
                question2  TEXT,
                question2_intent TEXT,
                question3  TEXT,
                question3_intent TEXT,
                view_count INTEGER DEFAULT 0,
                is_notice  BOOLEAN DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO harkness_posts_new
                SELECT post_id, board_id, author_id, title, content,
                       {q_select},
                       view_count, is_notice, created_at, updated_at
                FROM harkness_posts;
            DROP TABLE harkness_posts;
            ALTER TABLE harkness_posts_new RENAME TO harkness_posts;
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_harkness_posts_author_id   ON harkness_posts(author_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_harkness_posts_board_id    ON harkness_posts(board_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_harkness_posts_created_at  ON harkness_posts(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_harkness_posts_is_notice   ON harkness_posts(is_notice)")
        conn.commit()
        print("OK: harkness_posts.content → nullable 완료")
except Exception as e:
    print(f"ERR: harkness_posts fix 실패: {e}")
    conn.rollback()

# ── 4. 현재 테이블 목록 확인 ───────────────────────────────────────────────────
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(f"\n=== 4단계: 현재 테이블 목록 ({len(tables)}개) ===")
print(', '.join(tables))

conn.close()

print(f"\n=== 완료: {ok_count}개 추가, {skip_count}개 건너뜀 ===")
