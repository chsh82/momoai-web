#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""로그인 계정 확인"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User
from werkzeug.security import generate_password_hash

print("=" * 70)
print("🔐 로그인 계정 확인")
print("=" * 70)

app = create_app('development')

with app.app_context():
    # 관리자 계정 확인
    admin = User.query.filter_by(role='admin').first()

    if admin:
        print(f"\n✅ 관리자 계정 존재:")
        print(f"   이메일: {admin.email}")
        print(f"   이름: {admin.name}")
        print(f"   역할: {admin.role}")
        print(f"   활성화: {admin.is_active}")
    else:
        print("\n❌ 관리자 계정이 없습니다.")
        print("   새로운 관리자 계정을 생성하시겠습니까?")

        # 자동으로 admin 계정 생성
        print("\n📝 관리자 계정 생성 중...")
        admin = User(
            email='admin@momoai.com',
            name='관리자',
            role='admin',
            role_level=1,
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ 관리자 계정 생성 완료!")
        print(f"   이메일: {admin.email}")
        print(f"   비밀번호: admin123")

    # 학생 계정 확인
    print("\n" + "=" * 70)
    student_user = User.query.filter_by(email='pjw@momoai.com').first()

    if student_user:
        print(f"✅ 테스트 학생 계정:")
        print(f"   이메일: {student_user.email}")
        print(f"   이름: {student_user.name}")
        print(f"   역할: {student_user.role}")

        # 비밀번호가 123456인지 확인하고 아니면 재설정
        if not student_user.check_password('123456'):
            print("   ⚠️ 비밀번호 재설정 중...")
            student_user.set_password('123456')
            db.session.commit()
            print("   ✅ 비밀번호: 123456")
        else:
            print("   ✅ 비밀번호: 123456")

    print("\n" + "=" * 70)
    print("🌐 로그인 URL: http://localhost:5000/auth/login")
    print("=" * 70)

    print("\n📋 테스트용 계정 정보:")
    print("   1️⃣ 관리자: admin@momoai.com / admin123")
    print("   2️⃣ 학생: pjw@momoai.com / 123456")
    print("=" * 70)
