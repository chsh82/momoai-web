# -*- coding: utf-8 -*-
"""결석 예고(AbsenceNotice) 생성 헬퍼 - 헤르메스의 미래 날짜 결석 처리 전용.

app/admin/routes.py의 create_absence_notice 라우트 본문(AbsenceNotice 생성 +
담당 강사 알림)을 그대로 본떴다. 기존 3곳의 호출부(admin/teacher/
parent_portal)는 각자 폼 입력 검증이 섞여 있어 이번엔 건드리지 않고,
헤르메스 전용으로 새로 둔다(회귀 위험 최소화 - 중복 통합은 추후 과제)."""
from app.models import db
from app.models.absence_notice import AbsenceNotice
from app.models.notification import Notification

_NOTICE_LABEL = {'absent': '결석', 'late': '지각'}


def create_absence_notice_with_notification(student, course, absence_date, reason,
                                              notice_type='absent', created_by=None,
                                              created_by_role='admin', absence_date_end=None):
    """AbsenceNotice를 만들고 담당 강사에게 알림을 보낸다. 생성된 AbsenceNotice를 반환."""
    if absence_date_end and absence_date_end <= absence_date:
        absence_date_end = None

    notice = AbsenceNotice(
        student_id=student.student_id,
        course_id=course.course_id,
        absence_date=absence_date,
        absence_date_end=absence_date_end,
        reason=reason,
        notice_type=notice_type,
        created_by=created_by,
        created_by_role=created_by_role,
    )
    db.session.add(notice)
    db.session.flush()

    notice_label = _NOTICE_LABEL.get(notice_type, notice_type)
    if absence_date_end:
        date_str = f'{absence_date.strftime("%m/%d")}~{absence_date_end.strftime("%m/%d")}'
        date_full = f'{absence_date.strftime("%Y년 %m월 %d일")}~{absence_date_end.strftime("%m월 %d일")}'
    else:
        date_str = absence_date.strftime('%m/%d')
        date_full = absence_date.strftime('%Y년 %m월 %d일')

    if course.teacher_id:
        Notification.create_notification(
            user_id=course.teacher_id,
            notification_type='absence_notice',
            title=f'[{notice_label} 예고] {student.name} ({date_str})',
            message=(f'{student.name} 학생이 {date_full} '
                     f'{course.course_name} {notice_label} 예정입니다. 사유: {reason}'),
            link_url='/teacher/upcoming-changes',
        )

    return notice
