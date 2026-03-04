# -*- coding: utf-8 -*-
"""도서 태그/뱃지 컬럼 추가 마이그레이션"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

columns = [
    ('grade_tags', 'TEXT'),
    ('domain_tags', 'TEXT'),
    ('subject_tags', 'TEXT'),
    ('is_textbook_work', 'INTEGER DEFAULT 0 NOT NULL'),
    ('is_snu_classic', 'INTEGER DEFAULT 0 NOT NULL'),
]

for col, col_type in columns:
    try:
        c.execute(f'ALTER TABLE books ADD COLUMN {col} {col_type}')
        print(f'Added column: {col}')
    except Exception as e:
        print(f'{col}: {e}')

conn.commit()
conn.close()
print('Done.')
