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
        # 시작일 = 종료일 (보강수업 등 단일 세션): 요일 매칭 없이 당일 세션만 생성
        if course.start_date == course.end_date:
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
            course.total_sessions = 1
            return sessions

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

    enrollment_date = enrollment.enrolled_at.date() if enrollment.enrolled_at else None

    # 보강수업 또는 custom(1회성) 수업은 과거 날짜로 개설될 수 있으므로 입반일 필터 적용 안 함
    skip_date_filter = (
        enrollment.course.course_type == '보강수업' or
        enrollment.course.schedule_type == 'custom'
    )

    # 해당 수업의 모든 세션에 대해 출석 레코드 생성
    for session in enrollment.course.sessions:
        if not skip_date_filter and enrollment_date and session.session_date < enrollment_date:
            continue
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
                status='present',  # 기본값은 출석
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
            # 입반일 이후 세션만 생성
            enrollment_date = enrollment.enrolled_at.date() if enrollment.enrolled_at else None
            if enrollment_date and enrollment_date > session.session_date:
                continue
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

    # 출석 레코드 조회 (오늘 이전 진행된 세션만)
    from app.models.course import CourseSession
    from datetime import date
    attendance_records = Attendance.query.filter_by(
        enrollment_id=enrollment_id
    ).join(CourseSession, Attendance.session_id == CourseSession.session_id).filter(
        CourseSession.session_date <= date.today()
    ).all()

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

    # 보강수업 입반 시 강사 알림 + 출결 소급 처리
    if course.course_type == '보강수업':
        _notify_makeup_teachers(course, student_id)
        # 1:1/그룹 구분 없이 원 수업 최근 결석을 absent_makeup으로 변경
        # - 그룹 보강: 학생이 다른 반에서 보충
        # - 1:1 보강: 새 강사가 진행하므로 원 강사 시수 귀속 방지
        _mark_recent_absent_as_makeup(student_id, course.course_id)

    # 학부모에게 입반 알림 발송
    _notify_parents_on_enrollment(course, student_id)

    return enrollment


def _notify_parents_on_enrollment(course, student_id):
    """수업 입반 시 학생 본인 및 연결된 학부모에게 알림 발송"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from app.models.notification import Notification
        from app.models.parent_student import ParentStudent
        from app.models.student import Student

        student = Student.query.get(student_id)
        if not student:
            return

        is_makeup = (course.course_type == '보강수업')
        if is_makeup:
            title = f'[보강 등록] {student.name} 학생'
            start_str = course.start_date.strftime('%Y년 %m월 %d일') if course.start_date else ''
            message = (f'{student.name} 학생이 {start_str} '
                       f'{course.course_name} 보강 수업에 등록되었습니다.')
        else:
            title = f'[수업 입반] {student.name} 학생'
            message = (f'{student.name} 학생이 {course.course_name} 수업에 '
                       f'등록되었습니다.')

        # 학생 본인 알림
        if student.user_id:
            Notification.create_notification(
                user_id=student.user_id,
                notification_type='enrollment_applied',
                title=title,
                message=message,
                link_url='/student/courses'
            )

        # 학부모 알림
        parents = ParentStudent.query.filter_by(
            student_id=student_id, is_active=True
        ).all()
        for ps in parents:
            Notification.create_notification(
                user_id=ps.parent_id,
                notification_type='enrollment_applied',
                title=title,
                message=message,
                link_url='/parent/courses'
            )
    except Exception as e:
        logger.error(f'[입반알림] student_id={student_id} course_id={course.course_id}: {e}', exc_info=True)


def _notify_makeup_teachers(makeup_course, student_id, original_course_id=None):
    """
    보강수업 입반 시 강사 알림 발송:
    1. 보강 수업 담당 강사 — 항상 발송
    2. 학생이 현재 수강 중인 진행 중 정규 수업 담당 강사 전체 — 자동 탐색하여 발송
       (보강 담당과 동일 강사인 경우 중복 발송 생략)
    """
    try:
        from app.models.notification import Notification
        from app.models.student import Student

        student = Student.query.get(student_id)
        if not student:
            return

        makeup_date = makeup_course.start_date
        date_str = makeup_date.strftime('%Y년 %m월 %d일') if makeup_date else '미정'

        # 1. 보강 담당 강사에게 알림
        if makeup_course.teacher_id:
            Notification.create_notification(
                user_id=makeup_course.teacher_id,
                notification_type='makeup_student_joining',
                title=f'[보강] {student.name} 학생 수업 참여 예정',
                message=(f'{student.name} 학생이 {date_str} '
                         f'{makeup_course.course_name} 보강수업에 참여합니다.'),
                link_url=f'/teacher/courses/{makeup_course.course_id}'
            )

        # 2. 학생이 현재 수강 중인 진행 중 정규 수업 담당 강사들에게 알림
        # 보강 입반 시점에 active 상태인 정규 수업(보강수업·완료 제외)을 모두 조회
        active_enrollments = (
            CourseEnrollment.query
            .join(Course, CourseEnrollment.course_id == Course.course_id)
            .filter(
                CourseEnrollment.student_id == student_id,
                CourseEnrollment.status == 'active',
                Course.course_type != '보강수업',
                Course.status == 'active',
                Course.course_id != makeup_course.course_id
            )
            .all()
        )

        notified_teachers = {makeup_course.teacher_id}  # 중복 발송 방지
        for enr in active_enrollments:
            c = enr.course
            if not c.teacher_id or c.teacher_id in notified_teachers:
                continue
            Notification.create_notification(
                user_id=c.teacher_id,
                notification_type='makeup_student_absent',
                title=f'[보강] {student.name} 학생 결석 예정',
                message=(f'{student.name} 학생이 {date_str} '
                         f'{c.course_name} 수업에 결석하고 타반 보강수업에 참여합니다.'),
                link_url=f'/teacher/courses/{c.course_id}'
            )
            notified_teachers.add(c.teacher_id)

    except Exception:
        # 알림 실패가 입반을 막아서는 안 됨
        pass


def _mark_recent_absent_as_makeup(student_id, exclude_course_id):
    """
    그룹 보강 입반 시: 학생의 원 수업들 중 가장 최근 absent 레코드를
    absent_makeup으로 소급 변경.
    (1:1 보강은 별도 시수/비용 발생이므로 호출하지 않음)
    """
    try:
        # 학생이 현재 수강 중인 정규 수업의 출결 레코드 조회
        # 가장 최근 absent 1건만 변경
        recent_absent = (
            Attendance.query
            .join(CourseSession, Attendance.session_id == CourseSession.session_id)
            .join(Course, CourseSession.course_id == Course.course_id)
            .join(CourseEnrollment,
                  (CourseEnrollment.course_id == Course.course_id) &
                  (CourseEnrollment.student_id == student_id) &
                  (CourseEnrollment.status == 'active'))
            .filter(
                Attendance.student_id == student_id,
                Attendance.status == 'absent',
                Course.course_type != '보강수업',
                Course.status == 'active',
                Course.course_id != exclude_course_id
            )
            .order_by(CourseSession.session_date.desc())
            .first()
        )
        if recent_absent:
            recent_absent.status = 'absent_makeup'
    except Exception:
        pass
