# -*- coding: utf-8 -*-
"""
결석 예고 & 입반/전반 예약 스키마 업데이트 마이그레이션
- absence_notices: 기존 테이블에 새 컬럼 추가 (created_by_role, admin_confirmed, admin_confirmed_at, admin_confirmed_by)
- enrollment_schedules: teacher_confirmed, teacher_confirmed_at, teacher_notified_at 추가
- 기존 데이터가 없거나 테이블 자체가 없으면 db.create_all()로 생성
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db

app = create_app()

def column_exists(conn, table, column):
    result = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in result)

def table_exists(conn, table):
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return result.fetchone() is not None

with app.app_context():
    # 새 테이블 생성 (없는 경우)
    db.create_all()
    print("db.create_all() 완료")

    with db.engine.connect() as conn:
        # absence_notices 테이블 컬럼 추가
        if table_exists(conn, 'absence_notices'):
            absence_cols = [
                ('created_by_role', "ALTER TABLE absence_notices ADD COLUMN created_by_role VARCHAR(20)"),
                ('admin_confirmed', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed BOOLEAN DEFAULT 0"),
                ('admin_confirmed_at', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed_at DATETIME"),
                ('admin_confirmed_by', "ALTER TABLE absence_notices ADD COLUMN admin_confirmed_by VARCHAR(36) REFERENCES users(user_id)"),
            ]
            for col_name, sql in absence_cols:
                if not column_exists(conn, 'absence_notices', col_name):
                    conn.execute(sql)
                    print(f"  absence_notices.{col_name} 추가됨")
                else:
                    print(f"  absence_notices.{col_name} 이미 존재")

        # enrollment_schedules 테이블 컬럼 추가
        if table_exists(conn, 'enrollment_schedules'):
            enroll_cols = [
                ('teacher_confirmed', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_confirmed BOOLEAN DEFAULT 0"),
                ('teacher_confirmed_at', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_confirmed_at DATETIME"),
                ('teacher_notified_at', "ALTER TABLE enrollment_schedules ADD COLUMN teacher_notified_at DATETIME"),
            ]
            for col_name, sql in enroll_cols:
                if not column_exists(conn, 'enrollment_schedules', col_name):
                    conn.execute(sql)
                    print(f"  enrollment_schedules.{col_name} 추가됨")
                else:
                    print(f"  enrollment_schedules.{col_name} 이미 존재")

        conn.execute("COMMIT")
        print("마이그레이션 완료!")
