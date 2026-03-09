#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
모든 SQLAlchemy 모델의 컬럼을 실제 DB와 비교하여 누락 컬럼을 자동 추가.
실행: venv/bin/python3 migrate_sync_all_columns.py
"""
import sys

# Flask 앱 초기화
from app import create_app
app = create_app()

with app.app_context():
    import sqlite3
    from flask import current_app
    from sqlalchemy import inspect as sa_inspect
    from app.models import db

    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    conn = sqlite3.connect(db_uri)
    cur = conn.cursor()

    def get_db_columns(table):
        cur.execute(f'PRAGMA table_info({table})')
        return {r[1]: r[2] for r in cur.fetchall()}  # name → type

    def get_db_tables():
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in cur.fetchall()}

    # SQLAlchemy 타입 → SQLite 타입 매핑
    def sa_type_to_sqlite(col):
        t = str(col.type)
        t_upper = t.upper()
        if 'VARCHAR' in t_upper or 'STRING' in t_upper or 'TEXT' in t_upper:
            return t_upper if 'VARCHAR' in t_upper else 'TEXT'
        if 'INTEGER' in t_upper or 'INT' in t_upper:
            return 'INTEGER'
        if 'BOOLEAN' in t_upper or 'BOOL' in t_upper:
            return 'INTEGER'  # SQLite stores BOOL as INTEGER
        if 'DATETIME' in t_upper:
            return 'DATETIME'
        if 'DATE' in t_upper:
            return 'DATE'
        if 'FLOAT' in t_upper or 'NUMERIC' in t_upper or 'REAL' in t_upper:
            return 'REAL'
        return 'TEXT'

    def get_default(col):
        if col.default is not None:
            val = col.default.arg
            if callable(val):
                return None
            if isinstance(val, bool):
                return '1' if val else '0'
            if isinstance(val, (int, float)):
                return str(val)
            if isinstance(val, str):
                return f"'{val}'"
        if not col.nullable and col.default is None:
            # nullable=False without default — use safe defaults
            t = sa_type_to_sqlite(col)
            if 'INT' in t or 'REAL' in t:
                return '0'
            return "''"
        return None

    existing_tables = get_db_tables()
    inspector = sa_inspect(db.engine)

    added = []
    skipped = []
    errors = []

    for table_name, table in db.metadata.tables.items():
        if table_name not in existing_tables:
            skipped.append(f'{table_name} (테이블 없음 — 스킵)')
            continue

        db_cols = get_db_columns(table_name)

        for col in table.columns:
            col_name = col.name
            if col_name in db_cols:
                continue  # 이미 존재

            # 컬럼 추가
            sqlite_type = sa_type_to_sqlite(col)
            default_val = get_default(col)

            nullable = 'NULL' if col.nullable else 'NOT NULL'
            if default_val is not None:
                sql = f'ALTER TABLE {table_name} ADD COLUMN {col_name} {sqlite_type} DEFAULT {default_val}'
            else:
                sql = f'ALTER TABLE {table_name} ADD COLUMN {col_name} {sqlite_type}'

            try:
                cur.execute(sql)
                added.append(f'{table_name}.{col_name}')
            except Exception as e:
                errors.append(f'{table_name}.{col_name}: {e}')

    conn.commit()
    conn.close()

    print(f'\n[결과]')
    if added:
        print(f'추가된 컬럼 {len(added)}개:')
        for a in added:
            print(f'  + {a}')
    else:
        print('추가할 컬럼 없음 (이미 최신)')

    if errors:
        print(f'\n오류 {len(errors)}건:')
        for e in errors:
            print(f'  ! {e}')

    if skipped:
        print(f'\n스킵 {len(skipped)}건 (테이블 미생성):')
        for s in skipped:
            print(f'  - {s}')

    print(f'\n완료. 서비스 재시작 필요.')
    sys.exit(1 if errors else 0)
