# -*- coding: utf-8 -*-
"""누락 컬럼 직접 추가 (sqlite3 사용)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3

# DB 경로 찾기
from app import create_app
app = create_app()

with app.app_context():
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"DB URL: {db_url}")

db_path = db_url.replace('sqlite:///', '')
if not db_path.startswith('/'):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
print(f"DB Path: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def col_exists(table, col):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cursor.fetchall())

# absence_notices 누락 컬럼
absence_cols = [
    ('created_by', "ALTER TABLE absence_notices ADD COLUMN created_by VARCHAR(36)"),
    ('created_by_role', "ALTER TABLE absence_notices ADD COLUMN created_by_role VARCHAR(20)"),
    ('teacher_confirmed', "ALTER TABLE absence_notices ADD COLUMN teacher_confirmed BOOLEAN DEFAULT 0"),
    ('teacher_confirmed_at', "ALTER TABLE absence_notices ADD COLUMN teacher_confirmed_at DATETIME"),
    ('admin_confirmed', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed BOOLEAN DEFAULT 0"),
    ('admin_confirmed_at', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed_at DATETIME"),
    ('admin_confirmed_by', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed_by VARCHAR(36)"),
]
for col, sql in absence_cols:
    if not col_exists('absence_notices', col):
        cursor.execute(sql)
        print(f"  absence_notices.{col} 추가됨")
    else:
        print(f"  absence_notices.{col} 이미 존재")

# enrollment_schedules 누락 컬럼
enroll_cols = [
    ('teacher_confirmed', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_confirmed BOOLEAN DEFAULT 0"),
    ('teacher_confirmed_at', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_confirmed_at DATETIME"),
    ('teacher_notified_at', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_notified_at DATETIME"),
]
for col, sql in enroll_cols:
    if not col_exists('enrollment_schedules', col):
        cursor.execute(sql)
        print(f"  enrollment_schedules.{col} 추가됨")
    else:
        print(f"  enrollment_schedules.{col} 이미 존재")

conn.commit()
conn.close()
print("완료!")
