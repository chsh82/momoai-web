# -*- coding: utf-8 -*-
"""APScheduler 설정 및 예약 작업"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone='Asia/Seoul')


def send_class_reminders(app):
    """수업 1시간 전 학생·학부모에게 푸시 알림 발송 (30분마다 실행)"""
    from datetime import datetime, timedelta
    with app.app_context():
        try:
            from app.models import db, ParentStudent
            from app.models.course import CourseSession, CourseEnrollment
            from app.models.reminder_log import ReminderLog
            from app.utils.push_utils import send_push_to_user

            now = datetime.now()
            # 1시간 후 ± 5분 윈도우
            window_start = (now + timedelta(minutes=55)).time()
            window_end   = (now + timedelta(minutes=65)).time()
            today = now.date()

            sessions = CourseSession.query.filter(
                CourseSession.session_date == today,
                CourseSession.start_time != None,
                CourseSession.start_time >= window_start,
                CourseSession.start_time < window_end,
                CourseSession.status == 'scheduled'
            ).all()

            for session in sessions:
                # 이미 발송한 세션은 건너뜀
                if ReminderLog.query.filter_by(session_id=session.session_id).first():
                    continue

                course = session.course
                time_str = session.start_time.strftime('%H:%M')
                title = f'수업 1시간 전 알림'
                body = f'{course.course_name} 수업이 {time_str}에 시작됩니다.'

                enrollments = CourseEnrollment.query.filter_by(
                    course_id=course.course_id, status='active'
                ).all()

                for enroll in enrollments:
                    student = enroll.student
                    if not student:
                        continue

                    # 학생 본인
                    if student.user_id:
                        send_push_to_user(
                            user_id=student.user_id,
                            title=title,
                            body=body,
                            url='/student/courses'
                        )

                    # 학부모
                    parents = ParentStudent.query.filter_by(
                        student_id=student.student_id, is_active=True
                    ).all()
                    for ps in parents:
                        send_push_to_user(
                            user_id=ps.parent_id,
                            title=f'{student.name} 수업 1시간 전 알림',
                            body=body,
                            url='/parent/attendance'
                        )

                # 발송 이력 기록
                db.session.add(ReminderLog(session_id=session.session_id))

            db.session.commit()
            if sessions:
                logger.info(f'[Reminder] {len(sessions)}개 세션 알림 발송 완료')

        except Exception as e:
            logger.error(f'[Reminder] 오류: {e}')


def init_scheduler(app):
    """스케줄러 초기화 및 시작 (단일 워커에서만 실행)"""
    if scheduler.running:
        return

    # 파일 락으로 첫 번째 워커에서만 스케줄러 실행
    import fcntl
    lock_path = '/tmp/momoai_scheduler.lock'
    try:
        lock_fp = open(lock_path, 'w')
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        logger.info('[Scheduler] 다른 워커가 이미 실행 중 — 스킵')
        return

    scheduler.add_job(
        func=send_class_reminders,
        args=[app],
        trigger=IntervalTrigger(minutes=30),
        id='class_reminder',
        replace_existing=True
    )
    scheduler.start()
    logger.info('[Scheduler] APScheduler 시작됨 (30분 간격, 수업 1시간 전 알림)')
