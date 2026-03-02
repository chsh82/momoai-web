#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""essays 테이블에 correction_model 컬럼 추가"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(essays)")
    cols = {row[1] for row in cur.fetchall()}
    if 'correction_model' in cols:
        print('[SKIP] correction_model 컬럼이 이미 존재합니다.')
        conn.close()
        return
    cur.execute("ALTER TABLE essays ADD COLUMN correction_model VARCHAR(20) NOT NULL DEFAULT 'standard'")
    conn.commit()
    conn.close()
    print('[OK] correction_model 컬럼 추가 완료 (기존 데이터: standard로 초기화)')

if __name__ == '__main__':
    migrate()
