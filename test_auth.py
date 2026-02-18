#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""인증 시스템 테스트 스크립트"""
from app import create_app
from app.models import db, User

app = create_app('development')

with app.app_context():
    print("=" * 50)
    print("인증 시스템 테스트")
    print("=" * 50)

    # 기존 테스트 사용자 삭제
    test_user = User.query.filter_by(email='test@momoai.com').first()
    if test_user:
        db.session.delete(test_user)
        db.session.commit()
        print("[OK] 기존 테스트 사용자 삭제됨")

    # 테스트 사용자 생성
    user = User(
        email='test@momoai.com',
        name='테스트 강사',
        role='teacher'
    )
    user.set_password('testpassword123')

    db.session.add(user)
    db.session.commit()
    print(f"[OK] 테스트 사용자 생성: {user.email}")
    print(f"    - User ID: {user.user_id}")
    print(f"    - Name: {user.name}")
    print(f"    - Role: {user.role}")

    # 비밀번호 확인
    if user.check_password('testpassword123'):
        print("[OK] 비밀번호 검증 성공")
    else:
        print("[FAIL] 비밀번호 검증 실패")

    if user.check_password('wrongpassword'):
        print("[FAIL] 잘못된 비밀번호가 통과됨")
    else:
        print("[OK] 잘못된 비밀번호 차단")

    # 전체 사용자 조회
    all_users = User.query.all()
    print(f"\n[OK] 총 사용자 수: {len(all_users)}")
    for u in all_users:
        print(f"    - {u.name} ({u.email}) - {u.role}")

    print("\n" + "=" * 50)
    print("테스트 완료!")
    print("=" * 50)
    print("\n웹 브라우저에서 테스트:")
    print("1. http://localhost:5000/auth/signup - 회원가입")
    print("2. http://localhost:5000/auth/login - 로그인")
    print("\n테스트 계정:")
    print("  Email: test@momoai.com")
    print("  Password: testpassword123")
