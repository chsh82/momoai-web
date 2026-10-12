# -*- coding: utf-8 -*-
"""헤르메스 실행 핸들러 - 이미 해석된 ORM 객체(student/course 등)를 받아 실제
상태를 변경한다. 엔티티 해석(app/utils/hermes_resolver.py)과 분리해 각각
단독으로 테스트/재사용 가능하게 한다."""
from app.models import Attendance
from app.utils.course_utils import (
    apply_attendance_update, create_attendance_records_for_session, create_makeup_course_from_source,
)


class HermesActionError(Exception):
    """Hermes 실행 핸들러가 명확화 질문 없이는 더 진행할 수 없을 때 던진다
    (예: 해당 날짜에 세션이 아예 없음) - 호출부가 그대로 재질문 문구로 쓴다."""


def execute_schedule_makeup(student, source_course, makeup_date, makeup_time=None,
                             teacher=None, created_by=None):
    """1회 보강수업을 만들고 학생을 등록한다.

    teacher를 지정하면 원 수업 강사 대신 그 강사가 보강을 맡는다(다른 강사가
    대신 봐주기로 한 경우 - 2026-10-12 실사용에서 "최성호 강사와 보강" 같은
    지시가 들어와 추가함).

    create_makeup_course_from_source -> enroll_student_to_course가 이미
    강사/학부모 알림과 최근 결석의 absent_makeup 자동전환까지 전부 처리한다
    (app/utils/course_utils.py 확인됨) - 여기서 추가로 알림을 보낼 필요 없음."""
    makeup_course = create_makeup_course_from_source(
        source_course, student, makeup_date, makeup_start_override=makeup_time,
        teacher_override=teacher.user_id if teacher else None,
    )
    if created_by:
        makeup_course.created_by = created_by
    return makeup_course


def execute_mark_absence(student, course, session, status, reason=None, checked_by=None):
    """오늘/과거 세션의 출결을 바꾼다 - 과거/당일 날짜 전용(미래 날짜 "결석
    예고"는 app/utils/absence_utils.py가 따로 담당한다).

    session은 이미 app/utils/hermes_resolver.resolve_session_for_date로 찾은
    CourseSession이어야 한다(없으면 호출부가 명확화 질문으로 처리).

    app/teacher/routes.py의 update_attendance(PATCH)와 같은
    apply_attendance_update를 쓰므로 absent_makeup 자동전환·학부모 알림이
    동일하게 적용된다. 다만 강사 본인이 아니라 관리자가 대신 처리하는
    것이므로, 강사에게도 별도로 알려준다(기존 라우트는 강사 본인이 누르는
    거라 강사 자신에게는 알리지 않음 - 이건 헤르메스 전용 추가 동작)."""
    attendance = Attendance.query.filter_by(
        session_id=session.session_id, student_id=student.student_id,
    ).first()
    if attendance is None:
        create_attendance_records_for_session(session, skip_date_filter=True)
        attendance = Attendance.query.filter_by(
            session_id=session.session_id, student_id=student.student_id,
        ).first()
    if attendance is None:
        raise HermesActionError(
            f'{student.name} 학생이 이 수업({course.course_name})에 활성 등록돼 있지 않아 '
            f'출결 레코드를 만들 수 없습니다.'
        )

    result = apply_attendance_update(attendance, new_status=status, notes=reason, checked_by=checked_by)

    if course.teacher_id and checked_by != course.teacher_id:
        from app.models.notification import Notification
        status_label = {'absent': '결석', 'absent_makeup': '결석(보강 처리)', 'late': '지각', 'excused': '인정결석'}.get(
            result['final_status'], result['final_status'])
        Notification.create_notification(
            user_id=course.teacher_id,
            notification_type='attendance_absent',
            title=f'{student.name} 학생 {status_label} 처리됨',
            message=f'관리자가 {session.session_date.strftime("%m/%d")} {course.course_name} 수업의 '
                    f'{student.name} 학생을 {status_label} 처리했습니다.',
            link_url=f'/teacher/courses/{course.course_id}',
        )

    return result
