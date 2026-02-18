#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""관리자 비밀번호 재설정"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User

app = create_app('development')

with app.app_context():
    # 관리자 계정 찾기
    admin = User.query.filter_by(email='admin@momoai.com').first()

    if admin:
        # 비밀번호를 test1234로 재설정
        admin.set_password('test1234')
        db.session.commit()

        print("=" * 70)
        print("Admin password reset successfully!")
        print("=" * 70)
        print(f"Email: {admin.email}")
        print(f"Password: test1234")
        print("=" * 70)

        # 확인
        if admin.check_password('test1234'):
            print("Password verified: OK")
        else:
            print("Password verification: FAILED")
    else:
        print("Admin account not found!")
