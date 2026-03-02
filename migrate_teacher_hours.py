#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
강사 시수 보정 테이블 생성 마이그레이션

사용법:
    python migrate_teacher_hours.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] DB 파일을 찾을 수 없습니다: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 테이블 존재 여부 확인
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='teacher_hours_corrections'
    """)
    if cursor.fetchone():
        print("[SKIP] teacher_hours_corrections 테이블이 이미 존재합니다.")
        conn.close()
        return

    cursor.execute("""
        CREATE TABLE teacher_hours_corrections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id      VARCHAR(36) NOT NULL REFERENCES users(user_id),
            year            INTEGER NOT NULL,
            month           INTEGER NOT NULL,
            correction_date DATE,
            course_type     VARCHAR(50),
            hours_delta     FLOAT NOT NULL,
            note            VARCHAR(255),
            created_by      VARCHAR(36) NOT NULL REFERENCES users(user_id),
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX idx_thc_teacher_ym
        ON teacher_hours_corrections (teacher_id, year, month)
    """)

    conn.commit()
    conn.close()
    print("[OK] teacher_hours_corrections 테이블이 생성되었습니다.")


if __name__ == '__main__':
    migrate()
