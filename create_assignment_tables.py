# -*- coding: utf-8 -*-
"""과제 관리 테이블 생성 스크립트"""
from app import create_app, db
from app.models.assignment import Assignment, AssignmentSubmission

app = create_app()

with app.app_context():
    print("과제 관리 테이블 생성 중...")

    # 테이블 생성
    db.create_all()

    print("✓ assignments 테이블 생성 완료")
    print("✓ assignment_submissions 테이블 생성 완료")
    print("\n과제 관리 시스템 테이블이 성공적으로 생성되었습니다!")
