#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""모든 계정 비밀번호를 test1234로 통일"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User

print("=" * 70)
print("🔐 모든 계정 비밀번호 통일 (test1234)")
print("=" * 70)

app = create_app('development')

with app.app_context():
    # 모든 활성 사용자 조회
    users = User.query.filter_by(is_active=True).all()

    print(f"\n📋 총 {len(users)}개 계정 비밀번호 변경 중...\n")

    updated_count = 0
    for user in users:
        user.set_password('test1234')
        updated_count += 1

        role_emoji = {
            'admin': '👨‍💼',
            'teacher': '👨‍🏫',
            'student': '👨‍🎓',
            'parent': '👨‍👩‍👧'
        }.get(user.role, '👤')

        print(f"  {role_emoji} {user.name:15s} ({user.role:10s}) - {user.email}")

    db.session.commit()

    print(f"\n✅ {updated_count}개 계정 비밀번호 변경 완료!")
    print("\n" + "=" * 70)
    print("🔑 통일된 비밀번호: test1234")
    print("=" * 70)

    # 주요 계정 정보 표시
    print("\n📋 주요 테스트 계정:")
    print("-" * 70)

    # 관리자
    admin = User.query.filter_by(role='admin').first()
    if admin:
        print(f"\n1️⃣  관리자")
        print(f"   이메일: {admin.email}")
        print(f"   비밀번호: test1234")

    # 강사 (박선진)
    teacher = User.query.filter_by(name='박선진', role='teacher').first()
    if teacher:
        print(f"\n2️⃣  강사 (박선진)")
        print(f"   이메일: {teacher.email}")
        print(f"   비밀번호: test1234")

    # 학생 (박지원)
    student = User.query.filter_by(email='pjw@momoai.com').first()
    if student:
        print(f"\n3️⃣  학생 (박지원)")
        print(f"   이메일: {student.email}")
        print(f"   비밀번호: test1234")

    # 학부모
    parent = User.query.filter_by(role='parent').first()
    if parent:
        print(f"\n4️⃣  학부모 ({parent.name})")
        print(f"   이메일: {parent.email}")
        print(f"   비밀번호: test1234")

    print("\n" + "=" * 70)
