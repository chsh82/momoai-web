# -*- coding: utf-8 -*-
"""관리자 계정 생성 스크립트

3단계 관리자:
- master (level 1): 최고 관리자 - 모든 권한
- manager (level 2): 중간 관리자 - 제한된 관리 권한
- staff (level 3): 일반 관리자 - 기본 관리 권한
"""
from app import create_app, db
from app.models import User
import uuid

app = create_app()

with app.app_context():
    print("관리자 계정 생성 시작...\n")

    # 1. Master Admin (기존 Admin 계정 확인)
    master = User.query.filter_by(email='admin@momoai.com').first()
    if master:
        master.role_level = 1
        print(f"[OK] Master Admin: {master.email} (level 1)")
    else:
        master = User(
            user_id=str(uuid.uuid4()),
            email='admin@momoai.com',
            name='Master Admin',
            role='admin',
            role_level=1,
            is_active=True
        )
        master.set_password('admin123')
        db.session.add(master)
        print(f"[OK] Master Admin 생성: admin@momoai.com / admin123 (level 1)")

    # 2. Manager Admin
    manager = User.query.filter_by(email='manager@momoai.com').first()
    if not manager:
        manager = User(
            user_id=str(uuid.uuid4()),
            email='manager@momoai.com',
            name='Manager Admin',
            role='admin',
            role_level=2,
            is_active=True
        )
        manager.set_password('manager123')
        db.session.add(manager)
        print(f"[OK] Manager Admin 생성: manager@momoai.com / manager123 (level 2)")
    else:
        manager.role_level = 2
        print(f"[OK] Manager Admin 업데이트: {manager.email} (level 2)")

    # 3. Staff Admin
    staff = User.query.filter_by(email='staff@momoai.com').first()
    if not staff:
        staff = User(
            user_id=str(uuid.uuid4()),
            email='staff@momoai.com',
            name='Staff Admin',
            role='admin',
            role_level=3,
            is_active=True
        )
        staff.set_password('staff123')
        db.session.add(staff)
        print(f"[OK] Staff Admin 생성: staff@momoai.com / staff123 (level 3)")
    else:
        staff.role_level = 3
        print(f"[OK] Staff Admin 업데이트: {staff.email} (level 3)")

    db.session.commit()

    print("\n" + "="*60)
    print("관리자 계정 생성 완료!")
    print("="*60)
    print("\n[관리자 계정 정보]\n")
    print("1. Master Admin (최고 관리자)")
    print("   - 이메일: admin@momoai.com")
    print("   - 비밀번호: admin123")
    print("   - 권한: 모든 기능 접근 및 수정 가능\n")

    print("2. Manager Admin (중간 관리자)")
    print("   - 이메일: manager@momoai.com")
    print("   - 비밀번호: manager123")
    print("   - 권한: 대부분의 관리 기능 접근 가능\n")

    print("3. Staff Admin (일반 관리자)")
    print("   - 이메일: staff@momoai.com")
    print("   - 비밀번호: staff123")
    print("   - 권한: 기본 관리 기능 접근 가능\n")

    print("="*60)
    print("\n[권한 레벨 시스템]")
    print("  Level 1: master - 최고 관리자")
    print("  Level 2: manager - 중간 관리자")
    print("  Level 3: staff - 일반 관리자")
    print("  Level 4: teacher - 강사")
    print("  Level 5: parent - 학부모")
    print("  Level 6: student - 학생")
