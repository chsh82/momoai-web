#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""줌 시스템 테스트 준비"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User, Student, Course, CourseEnrollment
from app.utils.zoom_utils import encrypt_zoom_link, generate_zoom_token

print("=" * 70)
print("🎥 줌 시스템 테스트 준비")
print("=" * 70)

app = create_app('development')

with app.app_context():
    # 1. 강사 목록 조회
    teachers = User.query.filter_by(role='teacher', is_active=True).limit(5).all()

    print(f"\n📋 강사 목록 (총 {len(teachers)}명):")
    for teacher in teachers:
        courses = Course.query.filter_by(teacher_id=teacher.user_id).count()
        has_zoom = "✅" if teacher.zoom_token else "❌"
        print(f"  {has_zoom} {teacher.name} (ID: {teacher.user_id[:8]}...) - 수업 {courses}개")
        if teacher.zoom_token:
            print(f"     토큰: {teacher.zoom_token}")

    # 2. 박선진 선생님 선택 (이전에 사용했던 선생님)
    print("\n" + "=" * 70)
    target_teacher = User.query.filter_by(name='박선진', role='teacher').first()

    if not target_teacher:
        print("❌ 박선진 선생님을 찾을 수 없습니다. 다른 강사를 사용합니다.")
        target_teacher = teachers[0] if teachers else None

    if not target_teacher:
        print("❌ 강사가 없습니다. 테스트를 진행할 수 없습니다.")
        sys.exit(1)

    print(f"✅ 선택된 강사: {target_teacher.name}")

    # 3. 줌 링크가 없으면 테스트용 추가
    if not target_teacher.zoom_link:
        print("\n📝 테스트용 줌 링크 추가 중...")
        test_zoom_url = "https://zoom.us/j/1234567890?pwd=test123"
        target_teacher.zoom_link = encrypt_zoom_link(test_zoom_url)
        target_teacher.zoom_token = generate_zoom_token(target_teacher.name)
        db.session.commit()
        print(f"✅ 줌 링크 추가 완료!")
        print(f"   토큰: {target_teacher.zoom_token}")
        print(f"   실제 URL: {test_zoom_url}")
    else:
        print(f"\n✅ 이미 줌 링크가 등록되어 있습니다.")
        print(f"   토큰: {target_teacher.zoom_token}")

    # 4. 해당 강사의 수업 조회
    print("\n" + "=" * 70)
    courses = Course.query.filter_by(teacher_id=target_teacher.user_id).limit(3).all()
    print(f"📚 {target_teacher.name} 선생님의 수업 (총 {len(courses)}개):")

    for course in courses:
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.course_id,
            status='active'
        ).count()
        print(f"  - {course.course_name} (학생 {enrollments}명)")

    # 5. 등록된 학생 확인
    if courses:
        first_course = courses[0]
        enrollments = CourseEnrollment.query.filter_by(
            course_id=first_course.course_id,
            status='active'
        ).limit(3).all()

        print(f"\n👥 '{first_course.course_name}' 수업 학생:")
        if enrollments:
            for enrollment in enrollments:
                student = enrollment.student
                user = User.query.filter_by(user_id=student.user_id).first()
                if user:
                    print(f"  - {student.name} (이메일: {user.email})")
        else:
            print("  ⚠️ 등록된 학생이 없습니다.")

    # 6. 테스트 안내
    print("\n" + "=" * 70)
    print("🧪 테스트 방법:")
    print("=" * 70)
    print("\n1️⃣ 관리자 계정으로 테스트:")
    print("   - http://localhost:5000/admin/zoom-links")
    print("   - 강사 목록 확인")
    print("   - 줌 링크 수정/삭제 테스트")
    print("   - 토큰 재생성 테스트")

    print("\n2️⃣ 학생 계정으로 테스트:")
    if enrollments:
        student_user = User.query.filter_by(user_id=enrollments[0].student.user_id).first()
        if student_user:
            print(f"   - 이메일: {student_user.email}")
            print(f"   - 비밀번호: 123456 (기본값)")
    print("   - http://localhost:5000/student/courses")
    print("   - '🎥 강의실' 버튼 확인")
    print(f"   - 또는 직접 접속: http://localhost:5000/zoom/join/{target_teacher.zoom_token}")

    print("\n3️⃣ 접속 로그 확인:")
    print("   - http://localhost:5000/admin/zoom-access-logs")
    print("   - 학생 접속 기록 확인")

    print("\n" + "=" * 70)
    print("✅ 준비 완료!")
    print("=" * 70)
