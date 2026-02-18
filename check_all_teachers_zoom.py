# -*- coding: utf-8 -*-
"""모든 강사의 줌 링크 상태 확인 및 일괄 설정"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.course import Course
from app.utils.zoom_utils import encrypt_zoom_link, generate_zoom_token

def setup_all_teachers_zoom():
    """모든 강사에게 줌 링크 일괄 설정"""
    app = create_app()

    with app.app_context():
        # 모든 활성 강사 조회
        teachers = User.query.filter_by(role='teacher', is_active=True).all()

        print("="*80)
        print("All Active Teachers - Zoom Link Status")
        print("="*80)

        updated_count = 0

        for idx, teacher in enumerate(teachers, 1):
            # 담당 수업 수
            course_count = Course.query.filter_by(teacher_id=teacher.user_id).count()

            print(f"\n{idx}. {teacher.name} ({teacher.email})")
            print(f"   Courses: {course_count}")
            print(f"   Zoom Link: {'SET' if teacher.zoom_link else 'NOT SET'}")
            print(f"   Zoom Token: {teacher.zoom_token or 'NOT GENERATED'}")

            # 줌 링크가 없는 강사에게 설정
            if not teacher.zoom_link:
                test_zoom_link = f"https://zoom.us/j/{1000000000 + idx}?pwd=test{idx:04d}"
                encrypted_link = encrypt_zoom_link(test_zoom_link)
                teacher.zoom_link = encrypted_link

                if not teacher.zoom_token:
                    teacher.zoom_token = generate_zoom_token(teacher.name)

                print(f"   >>> UPDATED with token: {teacher.zoom_token}")
                updated_count += 1

        if updated_count > 0:
            db.session.commit()
            print("\n" + "="*80)
            print(f"SUMMARY: Updated {updated_count} teachers with zoom links")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("All teachers already have zoom links configured")
            print("="*80)

if __name__ == '__main__':
    setup_all_teachers_zoom()
