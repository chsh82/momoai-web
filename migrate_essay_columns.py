"""프로덕션 DB에 essay 컬럼 추가 마이그레이션"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

migrations = [
    ("course_id", "ALTER TABLE essays ADD COLUMN course_id VARCHAR(36) REFERENCES courses(course_id)"),
    ("session_id", "ALTER TABLE essays ADD COLUMN session_id VARCHAR(36) REFERENCES course_sessions(session_id)"),
    ("session_assigned_auto", "ALTER TABLE essays ADD COLUMN session_assigned_auto BOOLEAN NOT NULL DEFAULT 1"),
]

for name, sql in migrations:
    try:
        cur.execute(sql)
        print(f"✅ {name} 추가됨")
    except Exception as e:
        print(f"⏭  {name}: {e}")

conn.commit()
conn.close()
print("완료")
