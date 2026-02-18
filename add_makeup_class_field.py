# -*- coding: utf-8 -*-
"""보강수업 신청 가능여부 필드 추가"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.course import Course

def add_makeup_class_field():
    """Course 테이블에 makeup_class_allowed 컬럼 추가"""
    app = create_app()

    with app.app_context():
        try:
            # SQLite용 ALTER TABLE
            with db.engine.connect() as conn:
                # 컬럼이 이미 존재하는지 확인
                result = conn.execute(db.text("PRAGMA table_info(courses)"))
                columns = [row[1] for row in result]

                if 'makeup_class_allowed' in columns:
                    print("[OK] makeup_class_allowed column already exists.")
                else:
                    # 컬럼 추가 (SQLite는 DEFAULT 값을 지원)
                    conn.execute(db.text("""
                        ALTER TABLE courses
                        ADD COLUMN makeup_class_allowed BOOLEAN DEFAULT 1
                    """))
                    conn.commit()
                    print("[OK] makeup_class_allowed column added successfully.")

                # 기존 레코드 업데이트 (NULL인 경우 True로 설정)
                result = conn.execute(db.text("""
                    UPDATE courses
                    SET makeup_class_allowed = 1
                    WHERE makeup_class_allowed IS NULL
                """))
                conn.commit()
                print(f"[OK] Updated {result.rowcount} existing courses to allow makeup classes.")

        except Exception as e:
            print(f"[ERROR] {e}")
            db.session.rollback()

if __name__ == '__main__':
    add_makeup_class_field()
