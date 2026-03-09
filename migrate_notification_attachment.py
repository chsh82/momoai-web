"""DB 마이그레이션: notifications 테이블에 attachment 컬럼 추가"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance/momoai.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 기존 컬럼 확인
cursor.execute("PRAGMA table_info(notifications)")
columns = [row[1] for row in cursor.fetchall()]

if 'attachment_url' not in columns:
    cursor.execute("ALTER TABLE notifications ADD COLUMN attachment_url VARCHAR(500)")
    print("attachment_url 컬럼 추가됨")
else:
    print("attachment_url 이미 존재")

if 'attachment_name' not in columns:
    cursor.execute("ALTER TABLE notifications ADD COLUMN attachment_name VARCHAR(200)")
    print("attachment_name 컬럼 추가됨")
else:
    print("attachment_name 이미 존재")

conn.commit()
conn.close()
print("마이그레이션 완료")
