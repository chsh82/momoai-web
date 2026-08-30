# -*- coding: utf-8 -*-
"""APScheduler 설정 및 예약 작업"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone='Asia/Seoul')

# init_scheduler()의 flock 파일 핸들을 프로세스 생존 기간 내내 붙잡아 두기 위한
# 모듈 전역 참조. 지역변수로 두면 init_scheduler()가 return하는 순간 참조 카운트가
# 0이 되어 가비지 컬렉션되고, 그 시점에 fd가 닫히면서 flock도 함께 풀려버린다 -
# 그러면 "워커 1개만 스케줄러 실행" 가드가 실제로는 전혀 걸리지 않고, gunicorn
# 워커마다 각자 스케줄러를 띄워 모든 예약 작업이 워커 수만큼 중복 실행된다
# (2026-08-29 발견 - 마일리지 배치 job 6개 등록 확인 중 실제로 재현됨).
_scheduler_lock_fp = None


def send_class_reminders(app):
    """수업 1시간 전 학생·학부모에게 푸시 알림 발송 (30분마다 실행)"""
    from datetime import datetime, timedelta
    with app.app_context():
        logger.info('[Reminder] job 시작')
        job_start = datetime.utcnow()
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
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[Reminder] job 종료 - %d개 세션 알림 발송, 소요 %.1f초', len(sessions), elapsed)

        except Exception:
            logger.exception('[Reminder] 오류')


def generate_weekly_sessions(app):
    """매주 일요일 자정: 다음 7일치 세션 생성"""
    from datetime import date, datetime, timedelta
    with app.app_context():
        logger.info('[WeeklySession] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.models.course import Course
            from app.utils.course_utils import extend_sessions_for_course

            today = date.today()          # 일요일
            from_date = today + timedelta(days=1)   # 월요일
            to_date = today + timedelta(days=7)     # 다음 일요일

            active_courses = Course.query.filter(
                Course.schedule_type == 'weekly',
                Course.status == 'active',
                Course.is_terminated == False,
                Course.end_date >= from_date,
                Course.start_date <= to_date
            ).all()

            total_created = 0
            for course in active_courses:
                created = extend_sessions_for_course(course, from_date, to_date)
                total_created += len(created)
            db.session.commit()
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[WeeklySession] job 종료 - 대상 강좌 %d개, %d개 세션 생성, 소요 %.1f초',
                       len(active_courses), total_created, elapsed)

        except Exception:
            logger.exception('[WeeklySession] 오류')


def apply_enrollment_schedules(app):
    """자정마다 실행: 오늘 날짜로 예약된 입반/전반을 자동 처리"""
    from datetime import date, datetime
    with app.app_context():
        logger.info('[EnrollSchedule] job 시작')
        job_start = datetime.utcnow()
        applied, failed = 0, 0
        try:
            from app.models import db
            from app.models.enrollment_schedule import EnrollmentSchedule
            from app.models.course import CourseEnrollment
            from app.models.notification import Notification
            from app.utils.course_utils import enroll_student_to_course, create_makeup_course_from_source

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

                    else:  # makeup: 별도 1회 보강수업 개설 후 학생 배정
                        create_makeup_course_from_source(
                            course, student, sched.scheduled_date, sched.schedule_id
                        )

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

                    logger.info(
                        '[EnrollSchedule] %s 적용 - schedule_id=%s student_id=%s course_id=%s',
                        sched.schedule_type, sched.schedule_id, sched.student_id, sched.course_id,
                    )
                    applied += 1

                except Exception:
                    failed += 1
                    logger.exception('[EnrollSchedule] 개별 처리 실패 - schedule_id=%s', sched.schedule_id)

            db.session.commit()
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            summary = logger.warning if failed else logger.info
            summary('[EnrollSchedule] job 종료 - 처리 %d건, 적용 %d건, 실패 %d건, 소요 %.1f초',
                    len(schedules), applied, failed, elapsed)

        except Exception:
            logger.exception('[EnrollSchedule] 전체 오류')


def mileage_confirm_job(app):
    """1시간 간격: 질문·댓글의 24시간 대기 포인트를 확정 상태로 전환"""
    from datetime import datetime
    with app.app_context():
        logger.info('[MileageConfirm] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.services.mileage_service import confirm_pending_points
            count = confirm_pending_points()
            db.session.commit()
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[MileageConfirm] job 종료 - %d건 확정, 소요 %.1f초', count, elapsed)
        except Exception:
            logger.exception('[MileageConfirm] 오류')


def mileage_weekly_job(app):
    """매주 월요일 00:10: 직전 주 AT01(주간 출석) 집계"""
    from datetime import datetime
    with app.app_context():
        logger.info('[MileageWeekly] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.services.mileage_batch_service import run_weekly_attendance_batch
            results = run_weekly_attendance_batch()
            db.session.commit()
            awarded = sum(1 for r in results if r['action'].startswith('awarded'))
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[MileageWeekly] job 종료 - %d명 검토, %d명 지급, 소요 %.1f초',
                       len(results), awarded, elapsed)
        except Exception:
            logger.exception('[MileageWeekly] 오류')


def mileage_quarterly_job(app):
    """3/6/9/12월 1일 00:20: 직전 분기 AT02(분기 완주) 판정 (PaymentPeriod 기준 분기)"""
    from datetime import datetime
    with app.app_context():
        logger.info('[MileageQuarterly] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.services.mileage_batch_service import run_quarterly_completion_batch
            results = run_quarterly_completion_batch()
            db.session.commit()
            awarded = sum(1 for r in results if r['action'].startswith('awarded'))
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[MileageQuarterly] job 종료 - %d명 검토, %d명 지급, 소요 %.1f초',
                       len(results), awarded, elapsed)
        except Exception:
            logger.exception('[MileageQuarterly] 오류')


def ranking_monthly_provisional_job(app):
    """매월 1일 00:30: 전월 시즌 잠정 순위 집계·저장 (is_final=False)"""
    from datetime import datetime
    with app.app_context():
        logger.info('[RankingMonthly] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.services.ranking_service import build_ranking, previous_season
            from app.services.mileage_rules import RANKING_FIRST_SEASON
            season = previous_season()
            if season < RANKING_FIRST_SEASON:
                logger.info('[RankingMonthly] %s는 집계 시작 시즌(%s) 이전이라 건너뜀',
                           season, RANKING_FIRST_SEASON)
                return
            results = build_ranking(season, finalize=True, is_final=False)
            db.session.commit()
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[RankingMonthly] job 종료 - %s 잠정 순위 저장 %d명, 소요 %.1f초',
                       season, len(results), elapsed)
        except Exception:
            logger.exception('[RankingMonthly] 오류')


def ranking_monthly_final_job(app):
    """매월 3일 00:30: 전월 시즌 순위 확정 (is_final=True)"""
    from datetime import datetime
    with app.app_context():
        logger.info('[RankingFinal] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.models import db
            from app.services.ranking_service import build_ranking, previous_season
            from app.services.mileage_rules import RANKING_FIRST_SEASON
            season = previous_season()
            if season < RANKING_FIRST_SEASON:
                logger.info('[RankingFinal] %s는 집계 시작 시즌(%s) 이전이라 건너뜀',
                           season, RANKING_FIRST_SEASON)
                return
            results = build_ranking(season, finalize=True, is_final=True)
            db.session.commit()
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[RankingFinal] job 종료 - %s 순위 확정 %d명, 소요 %.1f초',
                       season, len(results), elapsed)
        except Exception:
            logger.exception('[RankingFinal] 오류')


def badge_sweep_job(app):
    """매일 03:00: 전체 학생 뱃지 조건 재검사 (누락 보정용)"""
    from datetime import datetime
    with app.app_context():
        logger.info('[BadgeSweep] job 시작')
        job_start = datetime.utcnow()
        try:
            from app.services.badge_service import run_badge_sweep
            from app.models import db
            results = run_badge_sweep()
            db.session.commit()
            total_granted = sum(len(r['granted']) for r in results)
            elapsed = (datetime.utcnow() - job_start).total_seconds()
            logger.info('[BadgeSweep] job 종료 - %d명에게 총 %d건 부여, 소요 %.1f초',
                       len(results), total_granted, elapsed)
        except Exception:
            logger.exception('[BadgeSweep] 오류')


def init_scheduler(app):
    """스케줄러 초기화 및 시작 (단일 워커에서만 실행)"""
    if scheduler.running:
        return

    # 파일 락으로 첫 번째 워커에서만 스케줄러 실행
    import fcntl
    global _scheduler_lock_fp
    lock_path = '/tmp/momoai_scheduler.lock'
    try:
        lock_fp = open(lock_path, 'w')
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _scheduler_lock_fp = lock_fp  # 모듈 전역에 보관 - 프로세스가 살아있는 한 fd를 열어 둬야 잠금이 유지된다
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
    scheduler.add_job(
        func=generate_weekly_sessions,
        args=[app],
        trigger=CronTrigger(day_of_week='sun', hour=0, minute=1, timezone='Asia/Seoul'),
        id='weekly_session_gen',
        replace_existing=True
    )

    # --- 마일리지 배치 (docs/mileage/08_개발지시서_3단계.md) ---
    scheduler.add_job(
        func=mileage_confirm_job,
        args=[app],
        trigger=IntervalTrigger(hours=1),
        id='mileage_confirm',
        replace_existing=True
    )
    scheduler.add_job(
        func=mileage_weekly_job,
        args=[app],
        trigger=CronTrigger(day_of_week='mon', hour=0, minute=10, timezone='Asia/Seoul'),
        id='mileage_weekly',
        replace_existing=True
    )
    scheduler.add_job(
        func=mileage_quarterly_job,
        args=[app],
        # 역년 분기(1/4/7/10월)가 아니라 이 프로젝트의 실제 분기 시작월(3/6/9/12월)에
        # 맞춘다 - PaymentPeriod.generate_quarterly() 기준(2026-08-28 결정사항)
        trigger=CronTrigger(month='3,6,9,12', day=1, hour=0, minute=20, timezone='Asia/Seoul'),
        id='mileage_quarterly',
        replace_existing=True
    )
    scheduler.add_job(
        func=ranking_monthly_provisional_job,
        args=[app],
        trigger=CronTrigger(day=1, hour=0, minute=30, timezone='Asia/Seoul'),
        id='ranking_monthly_provisional',
        replace_existing=True
    )
    scheduler.add_job(
        func=ranking_monthly_final_job,
        args=[app],
        trigger=CronTrigger(day=3, hour=0, minute=30, timezone='Asia/Seoul'),
        id='ranking_monthly_final',
        replace_existing=True
    )
    scheduler.add_job(
        func=badge_sweep_job,
        args=[app],
        trigger=CronTrigger(hour=3, minute=0, timezone='Asia/Seoul'),
        id='badge_sweep',
        replace_existing=True
    )

    scheduler.start()
    job_ids = [job.id for job in scheduler.get_jobs()]
    logger.info('[Scheduler] APScheduler 시작됨 - job %d개 등록: %s', len(job_ids), ', '.join(job_ids))
