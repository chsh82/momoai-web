#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
마이그레이션: course_enrollments 테이블에 discount_type 컬럼 추가
실행: python3 migrate_discount_type.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'momoai.db')


def column_exists(cursor, table, column):
    cursor.execute(f'PRAGMA table_info({table})')
    return any(row[1] == column for row in cursor.fetchall())


def run():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    changes = []

    if not column_exists(cursor, 'course_enrollments', 'discount_type'):
        cursor.execute(
            "ALTER TABLE course_enrollments ADD COLUMN discount_type VARCHAR(20) DEFAULT NULL"
        )
        changes.append('course_enrollments.discount_type')

    conn.commit()
    conn.close()

    if changes:
        print(f'[OK] 추가된 컬럼: {", ".join(changes)}')
    else:
        print('[SKIP] 이미 최신 상태입니다.')


if __name__ == '__main__':
    run()
