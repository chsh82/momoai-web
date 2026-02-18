# -*- coding: utf-8 -*-
"""테스트용 줌 링크 설정 스크립트"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.student import Student
from app.models.course import Course, CourseEnrollment
from app.utils.zoom_utils import encrypt_zoom_link, generate_zoom_token

def setup_test_zoom():
    """테스트용 줌 링크 설정"""
    app = create_app()

    with app.app_context():
        # 활성화된 강사 목록 조회
        teachers = User.query.filter_by(role='teacher', is_active=True).all()

        print("\n" + "="*60)
        print("현재 활성화된 강사 목록:")
        print("="*60)

        for idx, teacher in enumerate(teachers, 1):
            courses_count = Course.query.filter_by(teacher_id=teacher.user_id).count()
            print(f"{idx}. {teacher.name} ({teacher.email})")
            print(f"   - 담당 수업: {courses_count}개")
            print(f"   - 줌 링크: {'설정됨' if teacher.zoom_link else '미설정'}")
            print(f"   - 줌 토큰: {teacher.zoom_token or '미생성'}")

        if not teachers:
            print("활성화된 강사가 없습니다.")
            return

        # 수업이 있는 강사 찾기
        teachers_with_courses = []
        for teacher in teachers:
            enrollments = db.session.query(CourseEnrollment).join(Course).filter(
                Course.teacher_id == teacher.user_id,
                CourseEnrollment.status == 'active'
            ).count()
            if enrollments > 0:
                teachers_with_courses.append(teacher)

        print("\n" + "="*60)
        print(f"수강생이 있는 강사: {len(teachers_with_courses)}명")
        print("="*60)

        # 첫 번째 강사에게 테스트 줌 링크 설정
        if teachers_with_courses:
            teacher = teachers_with_courses[0]

            # 테스트 줌 링크 (실제 줌 링크 형식)
            test_zoom_link = "https://zoom.us/j/1234567890?pwd=abcd1234"

            # 줌 링크 암호화
            encrypted_link = encrypt_zoom_link(test_zoom_link)
            teacher.zoom_link = encrypted_link

            # 토큰 생성 (없는 경우)
            if not teacher.zoom_token:
                teacher.zoom_token = generate_zoom_token(teacher.name)

            db.session.commit()

            print(f"\n✅ {teacher.name} 강사에게 테스트 줌 링크 설정 완료!")
            print(f"   - 줌 링크: {test_zoom_link}")
            print(f"   - 줌 토큰: {teacher.zoom_token}")

            # 해당 강사의 수업 정보
            courses = Course.query.filter_by(teacher_id=teacher.user_id).all()
            print(f"\n   담당 수업:")
            for course in courses:
                enrollment_count = CourseEnrollment.query.filter_by(
                    course_id=course.course_id,
                    status='active'
                ).count()
                print(f"   - {course.course_name} (수강생: {enrollment_count}명)")
        else:
            print("\n수강생이 있는 강사가 없습니다.")
            print("모든 강사에게 테스트 줌 링크를 설정하시겠습니까? (y/n)")

if __name__ == '__main__':
    setup_test_zoom()
