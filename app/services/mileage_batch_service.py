# -*- coding: utf-8 -*-
"""마일리지 정기 배치 - 주간 출석(AT01) / 분기 완주(AT02)

app/utils/scheduler.py는 이 모듈의 함수를 호출만 한다(로직은 여기 둔다).
모든 함수는 여러 번 실행해도 결과가 같다(source_id 조합 키 + point_events의
유니크 제약이 중복 지급을 막는다). DB 커밋은 호출부(스케줄러 job 또는
scripts/run_mileage_batch.py)에서 한다 - 여기서는 award_points()를 통해
add()/flush()까지만 한다.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import and_

from app.models import db
from app.models.student import Student
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.payment_period import PaymentPeriod
from app.models.mileage import PointEvent
from app.services.mileage_service import award_points
from app.services.mileage_rules import (
    is_makeup_course_type, MAKEUP_COURSE_TYPE_PREFIX,
    ATTENDANCE_ATTENDED_STATUSES, ATTENDANCE_ABSENT_STATUSES, ATTENDANCE_KNOWN_STATUSES,
    ATTENDANCE_STATUS_PRIORITY, MILEAGE_START_DATE,
)

logger = logging.getLogger(__name__)


def _kst_today():
    return (datetime.utcnow() + timedelta(hours=9)).date()


def _previous_week_monday(today=None):
    """오늘(KST 날짜)이 속한 주의 월요일에서 7일을 빼 "직전 주"의 월요일을 구한다."""
    today = today or _kst_today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7)


def parse_iso_week(label):
    """'2026-W36' 형식을 그 주의 월요일 date로 변환한다."""
    year_str, week_str = label.split('-W')
    return datetime.fromisocalendar(int(year_str), int(week_str), 1).date()


def _scheduled_sessions_by_student(start_date, end_date):
    """[start_date, end_date] 구간에 실제로 예정된(취소되지 않은) 정규 수업 세션을
    학생별로 묶어서 반환한다. student_id -> set(session_id)
    """
    rows = db.session.query(CourseSession.session_id, CourseEnrollment.student_id).join(
        Course, Course.course_id == CourseSession.course_id
    ).join(
        CourseEnrollment, CourseEnrollment.course_id == Course.course_id
    ).filter(
        CourseSession.session_date >= start_date,
        CourseSession.session_date <= end_date,
        CourseSession.status != 'cancelled',
        CourseEnrollment.status == 'active',
    ).all()

    by_student = defaultdict(set)
    for session_id, student_id in rows:
        by_student[student_id].add(session_id)
    return by_student


def run_weekly_attendance_batch(monday=None, dry_run=False):
    """AT01 - 그 주에 학생에게 예정된 CourseSession 전부에 출석했으면 100점 지급.

    "주 5일" 같은 고정 일수 기준이 아니라, 학생 각자의 그 주 예정 세션 대비
    실제 출석 세션의 비율(=전부 출석했는지)로 판정한다(2026-08-28 결정사항).
    예정된 세션이 0건인 주는 지급 대상에서 제외한다.

    Args:
        monday: 대상 주의 월요일(date, KST 기준 달력 날짜). 생략하면 직전 주.
        dry_run: True면 award_points를 호출하지 않고 결과만 계산해서 반환한다.
    Returns:
        list[dict]: 학생별 처리 결과(감사용 - 총 세션 수, 출석 수, 처리 결과)
    """
    if monday is None:
        monday = _previous_week_monday()

    # 마일리지 적립 시작일 게이트(2026-08-29 결정사항) - 대상 주의 시작일이
    # 시작일보다 이르면 그 주는 시작일 이전 수업이 섞여 있으므로 통째로
    # 건너뛴다(award_points() 쪽 게이트는 occurred_at을 넘기지 않아 실행
    # 시점 기준으로 통과해버리므로, 배치 쪽에서 별도로 막아야 한다).
    if monday < MILEAGE_START_DATE:
        logger.info(
            '[MileageWeekly] 시작일(%s) 이전 주라 배치를 건너뜀 - monday=%s',
            MILEAGE_START_DATE, monday,
        )
        return []

    sunday = monday + timedelta(days=6)
    iso_year, iso_week, _ = monday.isocalendar()

    by_student = _scheduled_sessions_by_student(monday, sunday)

    results = []
    for student_id, session_ids in by_student.items():
        if not session_ids:
            continue

        attended_rows = db.session.query(Attendance.session_id).filter(
            Attendance.student_id == student_id,
            Attendance.session_id.in_(session_ids),
            Attendance.status.in_(ATTENDANCE_ATTENDED_STATUSES),
        ).all()
        attended_ids = {r[0] for r in attended_rows}
        full_attendance = session_ids.issubset(attended_ids)

        source_id = f"{student_id}-{iso_year}-W{iso_week:02d}"
        entry = {
            'student_id': student_id,
            'week': f"{iso_year}-W{iso_week:02d}",
            'range': f"{monday.isoformat()} ~ {sunday.isoformat()}",
            'scheduled_count': len(session_ids),
            'attended_count': len(attended_ids),
            'full_attendance': full_attendance,
            'source_id': source_id,
        }

        if not full_attendance:
            entry['action'] = 'not_eligible(결석 있음)'
        elif dry_run:
            dup = PointEvent.query.filter_by(
                student_id=student_id, activity_code='AT01',
                source_type='attendance_week', source_id=source_id, entry_type='award',
            ).first()
            entry['action'] = 'skip(이미 지급됨)' if dup else 'would_award(100점)'
        else:
            event = award_points(
                student_id=student_id, activity_code='AT01',
                source_type='attendance_week', source_id=source_id,
            )
            entry['action'] = 'awarded(100점)' if event else 'skip(중복 또는 상한)'
            if event:
                _evaluate_badges_safe(student_id, ['AT01'])

        results.append(entry)

    return results


def _resolve_quarter_period(year=None, period_number=None):
    """분기 구간을 PaymentPeriod에서 조회한다(하드코딩 없음).

    year/period_number를 생략하면 "오늘(KST) 기준으로 가장 최근에 끝난 분기"를 찾는다.
    """
    query = PaymentPeriod.query.filter_by(period_type='quarterly')
    if year is not None and period_number is not None:
        return query.filter_by(year=year, period_number=period_number).first()

    today = _kst_today()
    return query.filter(PaymentPeriod.end_date < today).order_by(PaymentPeriod.end_date.desc()).first()


def _pick_best_status(statuses, student_id, session_date):
    """중복 세션의 여러 출결 기록 중 하나를 채택한다(2026-08-28 재결정).

    ① 체크된 기록(None 아님)을 미체크보다 우선
    ② 둘 다 체크됐으면 ATTENDANCE_STATUS_PRIORITY가 더 좋은(숫자가 작은) 쪽을 채택

    "가장 나쁜 상태 채택"에서 바뀐 이유 - 같은 시각에 강좌가 두 개 등록돼
    있어도 학생은 한 곳에만 있을 수 있다. 한쪽에 present가 찍혔으면 실제로
    출석한 것이고, 다른 쪽 absent는 관리되지 않는 중복 레코드의 잔재일
    가능성이 크다(동일 시간대에 병행 생성된 정규 강좌가 있던 학생 사례에서 확인됨). 출석은 확인해야 찍히지만 결석은
    방치해도 남으므로, 찍힌 좋은 기록을 더 신뢰한다.

    Returns:
        선택된 status 문자열, 또는 유효한 기록이 전혀 없으면 None
    """
    known_checked = []
    for status in statuses:
        if status is None:
            continue
        if status not in ATTENDANCE_KNOWN_STATUSES:
            logger.warning(
                '[MileageQuarterly] 알 수 없는 출결 상태 - status=%r student_id=%s date=%s',
                status, student_id, session_date,
            )
            continue
        known_checked.append(status)

    if not known_checked:
        return None
    return min(known_checked, key=lambda s: ATTENDANCE_STATUS_PRIORITY[s])


def _regular_attendance_stats(student_id, course_ids, start_date, end_date):
    """정규(비보강) 강좌들의 분기 구간 내 세션을 날짜별로 묶어 결석 여부를 판정한다.

    강사 교체 시 기존 Course를 종료하지 않고 새 Course를 병행 생성하는
    실데이터 패턴이 확인되어(예: 같은 학생의 두 정규 Course가 같은 요일에
    완전히 겹치는 세션 날짜를 가짐), 같은 날짜에 세션이 여러 건 잡히면
    근본 원인은 그대로 두고 이 배치 안에서만 하루로 합친다(_pick_best_status
    참고). 중복이 감지되면 나중에 데이터를 정리할 때 쓸 수 있도록 로그를 남긴다.

    Returns:
        (total_days, absent_days)
    """
    if not course_ids:
        return 0, 0

    rows = db.session.query(
        CourseSession.session_date, CourseSession.course_id, Attendance.status
    ).outerjoin(
        Attendance, and_(
            Attendance.session_id == CourseSession.session_id,
            Attendance.student_id == student_id,
        )
    ).filter(
        CourseSession.course_id.in_(course_ids),
        CourseSession.session_date >= start_date,
        CourseSession.session_date <= end_date,
        CourseSession.status != 'cancelled',
    ).all()

    statuses_by_date = defaultdict(list)
    courses_by_date = defaultdict(set)
    for session_date, course_id, status in rows:
        statuses_by_date[session_date].append(status)
        courses_by_date[session_date].add(course_id)

    absent_days = 0
    for session_date, statuses in statuses_by_date.items():
        if len(courses_by_date[session_date]) > 1:
            logger.warning(
                '[MileageQuarterly] 중복 정규 세션 감지 - student_id=%s date=%s course_ids=%s',
                student_id, session_date, sorted(courses_by_date[session_date]),
            )

        best = _pick_best_status(statuses, student_id, session_date)
        if best in ATTENDANCE_ABSENT_STATUSES:
            absent_days += 1

    return len(statuses_by_date), absent_days


def _makeup_attended_count(student_id, start_date, end_date):
    """엄격한 보강 인정 기준 - SessionAdjustment의 결제 반영 상태(applied 등)가
    아니라, 실제 보강 수업에 출석(present/late)한 횟수를 직접 확인한다.
    결제 조정만 되고 보강에 출석하지 않은 경우는 인정하지 않는다.

    (2026-08-28 수정) 처음에는 MakeupClassRequest로 개설된 보강만 인정했으나,
    실데이터 확인 결과 course_type이 보강 계열인 Course 293개 중
    MakeupClassRequest/EnrollmentSchedule을 거친 것은 약 16%뿐이었다(나머지는
    관리자가 직접 개설). 신청 경로가 아니라 Course.course_type 기준으로 "실제
    보강 수업에 출석했는가"를 직접 보는 쪽이 실제 데이터와 맞고, "출석 여부"라는
    원래 기준 자체는 그대로 유지된다.
    """
    count = db.session.query(Attendance.attendance_id).join(
        CourseSession, CourseSession.session_id == Attendance.session_id
    ).join(
        Course, Course.course_id == CourseSession.course_id
    ).filter(
        Attendance.student_id == student_id,
        Attendance.status.in_(ATTENDANCE_ATTENDED_STATUSES),
        Course.course_type.like(f'{MAKEUP_COURSE_TYPE_PREFIX}%'),
        CourseSession.session_date >= start_date,
        CourseSession.session_date <= end_date,
    ).count()
    return count


def run_quarterly_completion_batch(year=None, period_number=None, dry_run=False):
    """AT02 - 직전 분기(PaymentPeriod 기준) 결석이 전부 보강으로 커버되면 1,000점 지급.

    분기 구간은 하드코딩하지 않고 PaymentPeriod(quarterly)에서 조회한다
    (2026-08-28 결정사항 - 이 프로젝트의 실제 분기는 역년 분기가 아니라
    12월/3월/6월/9월 시작 12주 단위다).

    보강 인정은 SessionAdjustment의 결제 반영 상태가 아니라 실제 보강 수업
    출석 기록으로 확인한다(엄격한 기준, 2026-08-28 결정사항).

    분기 도중 등록해 전 회차를 이수할 수 없는 학생은 대상에서 제외한다.

    Returns:
        list[dict]: 학생별 판정 근거(총 회차, 결석 수, 보강 인정 수)를 포함한 결과
    """
    period = _resolve_quarter_period(year, period_number)
    if period is None:
        return []

    q_start, q_end = period.start_date, period.end_date

    # course_type도 함께 가져와서 보강 계열 수강은 "정규 회차" 집계에서 제외한다
    # (2026-08-28 수정 - 보강을 정규 수업과 합산하면 결석·완주 판정이 왜곡됨).
    enrollments = db.session.query(CourseEnrollment, Course.course_type).join(
        Course, Course.course_id == CourseEnrollment.course_id
    ).filter(
        CourseEnrollment.status.in_(['active', 'completed']),
    ).all()

    by_student = defaultdict(set)  # student_id -> set(course_id) (정규, 분기 시작 전 등록분만)
    for e, course_type in enrollments:
        if is_makeup_course_type(course_type):
            continue  # 보강 수업은 정규 회차 집계 대상이 아님(보강 인정은 별도 함수에서 처리)
        enrolled_date = e.enrolled_at.date() if e.enrolled_at else q_start
        if enrolled_date > q_start:
            continue  # 분기 도중 등록 -> 전 회차 이수 불가, 대상 제외
        by_student[e.student_id].add(e.course_id)

    results = []
    for student_id, course_ids in by_student.items():
        total_sessions, total_absent = _regular_attendance_stats(student_id, course_ids, q_start, q_end)

        if total_sessions == 0:
            continue  # 이 분기에 정규 수업이 아예 없었던 학생 - 판정 대상 아님

        makeup_count = _makeup_attended_count(student_id, q_start, q_end)
        covered = min(makeup_count, total_absent)
        effective_absent = total_absent - covered

        source_id = f"{student_id}-{period.year}Q{period.period_number}"
        entry = {
            'student_id': student_id,
            'quarter': f"{period.year}Q{period.period_number}",
            'range': f"{q_start.isoformat()} ~ {q_end.isoformat()}",
            'total_sessions': total_sessions,
            'absent_count': total_absent,
            'makeup_attended_count': makeup_count,
            'effective_absent': effective_absent,
            'source_id': source_id,
        }

        if effective_absent > 0:
            entry['action'] = f'not_eligible(미보강 결석 {effective_absent}건)'
        elif dry_run:
            dup = PointEvent.query.filter_by(
                student_id=student_id, activity_code='AT02',
                source_type='attendance_quarter', source_id=source_id, entry_type='award',
            ).first()
            entry['action'] = 'skip(이미 지급됨)' if dup else 'would_award(1000점)'
        else:
            event = award_points(
                student_id=student_id, activity_code='AT02',
                source_type='attendance_quarter', source_id=source_id,
            )
            entry['action'] = 'awarded(1000점)' if event else 'skip(중복 또는 상한)'
            if event:
                _evaluate_badges_safe(student_id, ['AT02'])

        results.append(entry)

    return results


def _evaluate_badges_safe(student_id, trigger_codes):
    """배치 안에서 뱃지 판정이 실패해도 배치 자체는 계속 진행되게 한다."""
    try:
        from app.services.badge_service import evaluate_badges
        evaluate_badges(student_id, trigger_codes=trigger_codes)
    except Exception:
        logger.exception('배치 내 뱃지 판정 실패 (student_id=%s)', student_id)
