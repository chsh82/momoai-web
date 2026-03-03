# -*- coding: utf-8 -*-
"""도서 태그 컬럼 추가 마이그레이션"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

for col in ['grade_tags', 'domain_tags', 'subject_tags']:
    try:
        c.execute(f'ALTER TABLE books ADD COLUMN {col} TEXT')
        print(f'Added column: {col}')
    except Exception as e:
        print(f'{col}: {e}')

conn.commit()
conn.close()
print('Done.')
