#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""학생-강사 연결 확인 및 수정"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User, Student

print("=" * 70)
print("📚 학생-강사 연결 확인 및 수정")
print("=" * 70)

app = create_app('development')

with app.app_context():
    # 박선진 선생님 찾기
    teacher = User.query.filter_by(name='박선진', role='teacher').first()

    if not teacher:
        print("\n❌ 박선진 선생님을 찾을 수 없습니다.")
        print("\n모든 선생님 목록:")
        teachers = User.query.filter_by(role='teacher').all()
        for t in teachers:
            print(f"  - {t.name} (ID: {t.user_id}, Email: {t.email})")
        sys.exit(1)

    print(f"\n✅ 박선진 선생님 찾음")
    print(f"   User ID: {teacher.user_id}")
    print(f"   Email: {teacher.email}")

    # 박지원 학생 찾기
    student = Student.query.filter_by(name='박지원').first()

    if not student:
        print("\n❌ 박지원 학생을 찾을 수 없습니다.")
        print("\n모든 학생 목록 (처음 20명):")
        students = Student.query.limit(20).all()
        for s in students:
            teacher_name = s.teacher.name if s.teacher else "미배정"
            print(f"  - {s.name} (ID: {s.student_id[:8]}..., 담당: {teacher_name})")
        sys.exit(1)

    print(f"\n✅ 박지원 학생 찾음")
    print(f"   Student ID: {student.student_id}")
    print(f"   학년: {student.grade}")

    # 현재 담당 선생님 확인
    if student.teacher_id:
        current_teacher = User.query.get(student.teacher_id)
        print(f"   현재 담당: {current_teacher.name if current_teacher else '알 수 없음'} (ID: {student.teacher_id})")
    else:
        print(f"   현재 담당: 미배정")

    # 수정 필요 여부 확인
    if student.teacher_id == teacher.user_id:
        print(f"\n✅ 이미 박선진 선생님이 담당하고 있습니다.")
    else:
        print(f"\n⚠️  담당 선생님이 다릅니다. 박선진 선생님으로 변경하시겠습니까?")
        response = input("   변경하려면 'y' 입력: ")

        if response.lower() == 'y':
            old_teacher_id = student.teacher_id
            student.teacher_id = teacher.user_id
            db.session.commit()
            print(f"\n✅ 담당 선생님 변경 완료!")
            print(f"   이전: {old_teacher_id} → 현재: {teacher.user_id} (박선진)")
        else:
            print("\n취소되었습니다.")

    # MBTI 결과 확인
    from app.models.reading_mbti import ReadingMBTIResult
    results = ReadingMBTIResult.query.filter_by(student_id=student.student_id).all()

    print(f"\n📊 MBTI 검사 이력: {len(results)}회")
    if results:
        for result in results:
            print(f"   - {result.created_at.strftime('%Y-%m-%d')}: {result.mbti_type.type_name} ({result.mbti_type.type_code})")

    print("\n" + "=" * 70)
    print("완료!")
    print("=" * 70)
