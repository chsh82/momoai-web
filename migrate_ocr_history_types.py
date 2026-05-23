# -*- coding: utf-8 -*-
"""
ocr_history 테이블의 user_id, essay_id 컬럼 타입을 INTEGER → VARCHAR(36)으로 수정.

원인: OCRHistory 모델이 Integer로 선언됐으나 실제 users.user_id, essays.essay_id는
UUID(String 36) 타입이어서 FK 불일치 및 쿼리 필터링 오동작 발생.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for env_file in ['.env.production', '.env']:
    env_path = os.path.join(BASE_DIR, env_file)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        break

sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db
from sqlalchemy import text, inspect

app = create_app('production')

with app.app_context():
    try:
        inspector = inspect(db.engine)
        cols = {c['name']: c for c in inspector.get_columns('ocr_history')}
        dialect = db.engine.dialect.name  # 'postgresql' or 'sqlite'

        fixed = []

        if dialect == 'postgresql':
            with db.engine.connect() as conn:
                # user_id 컬럼 타입 확인 및 수정
                user_id_type = str(cols.get('user_id', {}).get('type', '')).upper()
                if 'INT' in user_id_type:
                    conn.execute(text(
                        "ALTER TABLE ocr_history "
                        "ALTER COLUMN user_id TYPE VARCHAR(36) USING user_id::text"
                    ))
                    fixed.append('user_id: INTEGER → VARCHAR(36)')

                # essay_id 컬럼 타입 확인 및 수정
                essay_id_type = str(cols.get('essay_id', {}).get('type', '')).upper()
                if 'INT' in essay_id_type:
                    conn.execute(text(
                        "ALTER TABLE ocr_history "
                        "ALTER COLUMN essay_id TYPE VARCHAR(36) USING essay_id::text"
                    ))
                    fixed.append('essay_id: INTEGER → VARCHAR(36)')

                conn.commit()

            if fixed:
                print(f"OK: 컬럼 타입 수정 완료 - {', '.join(fixed)}")
            else:
                print("INFO: 컬럼 타입이 이미 VARCHAR(36)입니다. 수정 불필요.")

        else:
            # SQLite는 타입 변환 불필요 (타입에 유연함)
            print(f"INFO: {dialect} DB - 타입 수정 불필요")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
