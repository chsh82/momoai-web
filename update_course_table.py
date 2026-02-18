# -*- coding: utf-8 -*-
"""Course 테이블 업데이트 스크립트 - 새 필드 추가"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 60)
    print("Course 테이블 업데이트")
    print("=" * 60)

    # 새 컬럼 추가
    try:
        # SQLite에서는 ALTER TABLE로 여러 컬럼을 한 번에 추가할 수 없으므로 하나씩 추가
        db.session.execute(text("ALTER TABLE courses ADD COLUMN grade VARCHAR(50)"))
        print("[OK] grade 컬럼 추가")
    except Exception as e:
        print(f"[SKIP] grade 컬럼: {e}")

    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN course_type VARCHAR(50)"))
        print("[OK] course_type 컬럼 추가")
    except Exception as e:
        print(f"[SKIP] course_type 컬럼: {e}")

    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN is_terminated BOOLEAN DEFAULT 0"))
        print("[OK] is_terminated 컬럼 추가")
    except Exception as e:
        print(f"[SKIP] is_terminated 컬럼: {e}")

    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN availability_status VARCHAR(20) DEFAULT 'available'"))
        print("[OK] availability_status 컬럼 추가")
    except Exception as e:
        print(f"[SKIP] availability_status 컬럼: {e}")

    db.session.commit()

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)
    print("\n새로 추가된 필드:")
    print("  - grade: 학년")
    print("  - course_type: 수업 타입 (베이직, 프리미엄, 정규반 등)")
    print("  - is_terminated: 종료 여부")
    print("  - availability_status: 사용 여부 (사용/대기/불가)")
