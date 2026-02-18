# -*- coding: utf-8 -*-
"""수업 관리 유틸리티 함수"""
from datetime import datetime, timedelta, time
from app.models import db, Course, CourseSession, CourseEnrollment, Attendance


def generate_course_sessions(course):
    """
    수업 생성 시 자동으로 세션들을 생성

    Args:
        course: Course 객체

    Returns:
        생성된 CourseSession 객체 리스트
    """
    if not course or not course.start_date or not course.end_date:
        return []

    sessions = []
    current_date = course.start_date
    session_number = 1

    # weekly 스케줄인 경우
    if course.schedule_type == 'weekly' and course.weekday is not None:
        # 첫 수업일 찾기 (시작일부터 지정된 요일 찾기)
        while current_date.weekday() != course.weekday:
            current_date += timedelta(days=1)

        # 종료일까지 매주 세션 생성
        while current_date <= course.end_date:
            session = CourseSession(
                course_id=course.course_id,
                session_number=session_number,
                session_date=current_date,
                start_time=course.start_time,
                end_time=course.end_time,
                status='scheduled'
            )
            sessions.append(session)
            db.session.add(session)

            # 다음 주로 이동
            current_date += timedelta(days=7)
            session_number += 1

    # custom 스케줄인 경우는 수동으로 세션 추가
    else:
        # 기본적으로 시작일에 첫 세션만 생성
        session = CourseSession(
            course_id=course.course_id,
            session_number=1,
            session_date=course.start_date,
            start_time=course.start_time,
            end_time=course.end_time,
            status='scheduled'
        )
        sessions.append(session)
        db.session.add(session)

    # 총 세션 수 업데이트
    course.total_sessions = len(sessions)

    return sessions


def create_attendance_records_for_enrollment(enrollment):
    """
    학생이 수강 신청하면 해당 수업의 모든 세션에 대한 출석 레코드를 자동 생성

    Args:
        enrollment: CourseEnrollment 객체

    Returns:
        생성된 Attendance 객체 리스트
    """
    if not enrollment or not enrollment.course:
        return []

    attendance_records = []

    # 해당 수업의 모든 세션에 대해 출석 레코드 생성
    for session in enrollment.course.sessions:
        # 이미 존재하는지 확인
        existing = Attendance.query.filter_by(
            session_id=session.session_id,
            student_id=enrollment.student_id,
            enrollment_id=enrollment.enrollment_id
        ).first()

        if not existing:
            attendance = Attendance(
                session_id=session.session_id,
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id,
                status='absent',  # 기본값은 결석
                checkin_method='manual'
            )
            attendance_records.append(attendance)
            db.session.add(attendance)

    return attendance_records


def create_attendance_records_for_session(session):
    """
    새로운 세션이 생성되면 모든 수강 학생에 대한 출석 레코드를 자동 생성

    Args:
        session: CourseSession 객체

    Returns:
        생성된 Attendance 객체 리스트
    """
    if not session or not session.course:
        return []

    attendance_records = []

    # 해당 수업의 모든 활성 수강생에 대해 출석 레코드 생성
    for enrollment in session.course.enrollments:
        if enrollment.status == 'active':
            # 이미 존재하는지 확인
            existing = Attendance.query.filter_by(
                session_id=session.session_id,
                student_id=enrollment.student_id,
                enrollment_id=enrollment.enrollment_id
            ).first()

            if not existing:
                attendance = Attendance(
                    session_id=session.session_id,
                    student_id=enrollment.student_id,
                    enrollment_id=enrollment.enrollment_id,
                    status='absent',
                    checkin_method='manual'
                )
                attendance_records.append(attendance)
                db.session.add(attendance)

    return attendance_records


def update_enrollment_attendance_stats(enrollment_id):
    """
    수강 신청의 출석 통계 업데이트

    Args:
        enrollment_id: CourseEnrollment ID

    Returns:
        업데이트된 CourseEnrollment 객체
    """
    enrollment = CourseEnrollment.query.get(enrollment_id)
    if not enrollment:
        return None

    # 출석 레코드 조회
    attendance_records = Attendance.query.filter_by(enrollment_id=enrollment_id).all()

    attended = sum(1 for a in attendance_records if a.status == 'present')
    absent = sum(1 for a in attendance_records if a.status == 'absent')
    late = sum(1 for a in attendance_records if a.status == 'late')

    enrollment.attended_sessions = attended
    enrollment.absent_sessions = absent
    enrollment.late_sessions = late

    return enrollment


def calculate_tuition_amount(enrollment):
    """
    출석 기반 수업료 계산

    Args:
        enrollment: CourseEnrollment 객체

    Returns:
        dict: {
            'total_amount': 총 수업료,
            'paid_amount': 납부 완료 금액,
            'remaining_amount': 미납 금액,
            'attended_unpaid': 출석했으나 미납된 회차 수
        }
    """
    if not enrollment or not enrollment.course:
        return {
            'total_amount': 0,
            'paid_amount': 0,
            'remaining_amount': 0,
            'attended_unpaid': 0
        }

    course = enrollment.course
    price_per_session = course.price_per_session

    # 총 수업료 (출석한 회차 기준)
    attended_sessions = enrollment.attended_sessions + enrollment.late_sessions
    total_amount = attended_sessions * price_per_session

    # 납부 완료 금액
    paid_amount = enrollment.paid_sessions * price_per_session

    # 미납 금액
    remaining_amount = max(0, total_amount - paid_amount)

    # 출석했으나 미납된 회차
    attended_unpaid = max(0, attended_sessions - enrollment.paid_sessions)

    return {
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'remaining_amount': remaining_amount,
        'attended_unpaid': attended_unpaid
    }


def get_course_statistics(course_id):
    """
    수업 통계 정보 조회

    Args:
        course_id: Course ID

    Returns:
        dict: 수업 통계 정보
    """
    course = Course.query.get(course_id)
    if not course:
        return None

    # 수강생 수
    total_students = len([e for e in course.enrollments if e.status == 'active'])

    # 완료된 세션 수
    completed_sessions = len([s for s in course.sessions if s.status == 'completed'])

    # 예정된 세션 수
    scheduled_sessions = len([s for s in course.sessions if s.status == 'scheduled'])

    # 전체 출석률
    total_attendance_records = Attendance.query.join(CourseSession).filter(
        CourseSession.course_id == course_id,
        CourseSession.status == 'completed'
    ).all()

    if total_attendance_records:
        present_count = sum(1 for a in total_attendance_records if a.status in ['present', 'late'])
        attendance_rate = (present_count / len(total_attendance_records)) * 100
    else:
        attendance_rate = 0

    # 총 수업료 (모든 수강생의 납부 완료 + 미납)
    total_revenue = 0
    total_pending = 0

    for enrollment in course.enrollments:
        if enrollment.status == 'active':
            calc = calculate_tuition_amount(enrollment)
            total_revenue += calc['paid_amount']
            total_pending += calc['remaining_amount']

    return {
        'course_name': course.course_name,
        'course_code': course.course_code,
        'total_students': total_students,
        'max_students': course.max_students,
        'completed_sessions': completed_sessions,
        'scheduled_sessions': scheduled_sessions,
        'total_sessions': course.total_sessions,
        'attendance_rate': round(attendance_rate, 2),
        'total_revenue': total_revenue,
        'total_pending': total_pending,
        'status': course.status
    }


def enroll_student_to_course(course_id, student_id):
    """
    학생을 수업에 등록 (편의 함수)

    Args:
        course_id: Course ID
        student_id: Student ID

    Returns:
        CourseEnrollment 객체 또는 None
    """
    course = Course.query.get(course_id)
    if not course:
        return None

    # 정원 확인
    if course.is_full:
        return None

    # 이미 등록되어 있는지 확인
    existing = CourseEnrollment.query.filter_by(
        course_id=course_id,
        student_id=student_id,
        status='active'
    ).first()

    if existing:
        return existing

    # 수강 신청 생성
    enrollment = CourseEnrollment(
        course_id=course_id,
        student_id=student_id,
        status='active'
    )
    db.session.add(enrollment)
    db.session.flush()

    # 출석 레코드 자동 생성
    create_attendance_records_for_enrollment(enrollment)

    return enrollment
