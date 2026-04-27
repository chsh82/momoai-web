# -*- coding: utf-8 -*-
"""APScheduler 설정 및 예약 작업"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
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


def apply_enrollment_schedules(app):
    """자정마다 실행: 오늘 날짜로 예약된 입반/전반을 자동 처리"""
    from datetime import date
    with app.app_context():
        try:
            from app.models import db
            from app.models.enrollment_schedule import EnrollmentSchedule
            from app.models.course import CourseEnrollment
            from app.models.notification import Notification
            from app.utils.course_utils import enroll_student_to_course

            today = date.today()
            schedules = EnrollmentSchedule.query.filter_by(
                status='scheduled'
            ).filter(EnrollmentSchedule.scheduled_date <= today).all()

            for sched in schedules:
                try:
                    course = sched.course
                    student = sched.student
                    if not course or not student:
                        sched.status = 'cancelled'
                        continue

                    type_label_map = {'enroll': '입반', 'withdraw': '전반', 'makeup': '보강참여'}
                    type_label = type_label_map.get(sched.schedule_type, sched.schedule_type)

                    if sched.schedule_type == 'enroll':
                        # 입반: 이미 active 수강 중이면 건너뜀
                        existing = CourseEnrollment.query.filter_by(
                            course_id=sched.course_id,
                            student_id=sched.student_id,
                            status='active'
                        ).first()
                        if not existing:
                            enroll_student_to_course(sched.course_id, sched.student_id)

                    elif sched.schedule_type == 'withdraw':
                        # 전반: active 수강을 inactive로 변경
                        enrollment = CourseEnrollment.query.filter_by(
                            course_id=sched.course_id,
                            student_id=sched.student_id,
                            status='active'
                        ).first()
                        if enrollment:
                            enrollment.status = 'inactive'
                            # 미래 출결 레코드 삭제
                            from app.models.attendance import Attendance
                            future_atts = Attendance.query.join(
                                CourseSession, Attendance.session_id == CourseSession.session_id
                            ).filter(
                                Attendance.enrollment_id == enrollment.enrollment_id,
                                CourseSession.session_date >= today
                            ).all()
                            for att in future_atts:
                                db.session.delete(att)
                            from app.utils.enrollment_utils import clear_teacher_if_no_active_enrollment
                            clear_teacher_if_no_active_enrollment(sched.student_id)

                    else:  # makeup: 기존 학적 유지, 추가 수강만 등록
                        existing = CourseEnrollment.query.filter_by(
                            course_id=sched.course_id,
                            student_id=sched.student_id,
                            status='active'
                        ).first()
                        if not existing:
                            enroll_student_to_course(sched.course_id, sched.student_id)

                    from datetime import datetime
                    sched.status = 'applied'
                    sched.applied_at = datetime.utcnow()

                    # 강사에게 적용 완료 알림
                    if course.teacher_id:
                        if sched.schedule_type == 'makeup':
                            notif_msg = (f'{student.name} 학생이 {course.course_name} 수업에 '
                                         f'보강으로 참여합니다. (기존 학적 유지)')
                        else:
                            notif_msg = (f'{course.course_name} 수업에 {student.name} 학생의 '
                                         f'{type_label}이 오늘부로 적용되었습니다.')
                        Notification.create_notification(
                            user_id=course.teacher_id,
                            notification_type='enrollment_applied',
                            title=f'[{type_label} 완료] {student.name} 학생',
                            message=notif_msg,
                            link_url=f'/teacher/courses/{course.course_id}'
                        )
                        sched.teacher_notified = True
                        sched.teacher_notified_at = datetime.utcnow()

                    logger.info(f'[EnrollSchedule] {sched.schedule_type} 적용: {student.name} → {course.course_name}')

                except Exception as e:
                    logger.error(f'[EnrollSchedule] 개별 처리 오류 {sched.schedule_id}: {e}')

            db.session.commit()

        except Exception as e:
            logger.error(f'[EnrollSchedule] 전체 오류: {e}')


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
    scheduler.add_job(
        func=apply_enrollment_schedules,
        args=[app],
        trigger=CronTrigger(hour=0, minute=5),  # 매일 자정 00:05
        id='enrollment_schedule',
        replace_existing=True
    )
    scheduler.start()
    logger.info('[Scheduler] APScheduler 시작됨 (수업 알림 30분 간격 + 입반/전반 자정 자동처리)')
