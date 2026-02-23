"""GCP DB 누락 컬럼 추가 스크립트 - instance/momoai.db 직접 수정"""
import sqlite3
import os

DB_PATH = '/home/chsh82/momoai_web/instance/momoai.db'

if not os.path.exists(DB_PATH):
    print(f"ERROR: DB 파일 없음: {DB_PATH}")
    exit(1)

print(f"DB: {DB_PATH}")

COLUMNS = [
    "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN locked_until DATETIME",
    "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN zoom_link VARCHAR(500)",
    "ALTER TABLE users ADD COLUMN zoom_token TEXT",
    "ALTER TABLE students ADD COLUMN school VARCHAR(200)",
    "ALTER TABLE students ADD COLUMN birth_date DATE",
    "ALTER TABLE students ADD COLUMN is_temp BOOLEAN DEFAULT 0",
]

conn = sqlite3.connect(DB_PATH)
for sql in COLUMNS:
    try:
        conn.execute(sql)
        print("OK:", sql[:70])
    except Exception as e:
        print("SKIP:", str(e)[:70])
conn.commit()
conn.close()
print("\n=== 완료 ===")
