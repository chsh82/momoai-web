# -*- coding: utf-8 -*-
"""essays 테이블에 api_provider 컬럼 추가"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(essays)")
columns = [row[1] for row in cursor.fetchall()]

if 'api_provider' not in columns:
    cursor.execute("ALTER TABLE essays ADD COLUMN api_provider VARCHAR(20) NOT NULL DEFAULT 'claude'")
    conn.commit()
    print("api_provider 컬럼이 essays 테이블에 추가되었습니다.")
else:
    print("api_provider 컬럼이 이미 존재합니다.")

conn.close()
