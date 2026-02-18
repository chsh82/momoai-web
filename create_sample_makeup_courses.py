# -*- coding: utf-8 -*-
"""보강신청 가능한 샘플 수업 20개 생성"""
import sys
import os
from datetime import datetime, date, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Course
from app.models.course import CourseSession

def create_sample_courses():
    """보강신청 가능한 샘플 수업 생성"""
    app = create_app()

    with app.app_context():
        try:
            # 강사 목록 조회
            teachers = User.query.filter_by(role='teacher', is_active=True).all()
            if not teachers:
                print("[ERROR] No teachers found. Please create teachers first.")
                return

            # 관리자 조회
            admin = User.query.filter_by(role='admin').first()
            if not admin:
                print("[ERROR] No admin found.")
                return

            # 학년 목록
            grades = ['초1', '초2', '초3', '초4', '초5', '초6',
                     '중1', '중2', '중3', '고1', '고2', '고3']

            # 수업 타입
            course_types = ['베이직', '프리미엄', '정규반', '하크니스']

            # 요일
            weekdays = ['월', '화', '수', '목', '금', '토', '일']

            # 시간대
            time_slots = [
                (time(9, 0), time(10, 0)),
                (time(10, 0), time(11, 0)),
                (time(11, 0), time(12, 0)),
                (time(13, 0), time(14, 0)),
                (time(14, 0), time(15, 0)),
                (time(15, 0), time(16, 0)),
                (time(16, 0), time(17, 0)),
                (time(17, 0), time(18, 0)),
                (time(18, 0), time(19, 0)),
                (time(19, 0), time(20, 0)),
            ]

            created_count = 0
            today = date.today()

            for i in range(20):
                # 랜덤 선택
                grade = grades[i % len(grades)]
                course_type = course_types[i % len(course_types)]
                teacher = teachers[i % len(teachers)]
                weekday_idx = i % 7
                weekday_name = weekdays[weekday_idx]
                start_time, end_time = time_slots[i % len(time_slots)]

                # 수업 시작일 (다음 주부터)
                days_ahead = 7 + weekday_idx
                start_date = today + timedelta(days=days_ahead)
                end_date = start_date + timedelta(days=90)  # 3개월 코스

                # 수업명 생성
                import uuid
                course_name = f"{grade} {course_type} {weekday_name} {start_time.strftime('%H:%M')} - {teacher.name}"
                course_code = f"{grade}{course_type[0]}{start_date.strftime('%y%m%d')}{uuid.uuid4().hex[:6].upper()}"

                # 수업 생성
                course = Course(
                    course_name=course_name,
                    course_code=course_code,
                    grade=grade,
                    course_type=course_type,
                    teacher_id=teacher.user_id,
                    is_terminated=False,
                    weekday=weekday_idx,
                    start_time=start_time,
                    end_time=end_time,
                    start_date=start_date,
                    end_date=end_date,
                    availability_status='available',
                    makeup_class_allowed=True,  # 보강신청 가능
                    schedule_type='weekly',
                    max_students=15,
                    price_per_session=50000,
                    status='active',
                    created_by=admin.user_id,
                    description=f"{grade} {course_type} 수업 - 보강신청 가능"
                )

                db.session.add(course)
                db.session.flush()

                # 4주치 세션 생성 (테스트용)
                session_number = 1
                current_date = start_date

                for week in range(4):
                    session = CourseSession(
                        course_id=course.course_id,
                        session_number=session_number,
                        session_date=current_date,
                        start_time=start_time,
                        end_time=end_time,
                        topic=f"Week {week + 1} - {course_type} 수업",
                        status='scheduled'
                    )
                    db.session.add(session)
                    session_number += 1
                    current_date += timedelta(days=7)

                created_count += 1
                print(f"[{created_count}/20] Created: {course_name}")

            db.session.commit()
            print(f"\n[OK] Successfully created {created_count} makeup-eligible courses.")
            print("[OK] All courses have makeup_class_allowed=True and status='active'.")

        except Exception as e:
            print(f"[ERROR] {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_sample_courses()
