# -*- coding: utf-8 -*-
"""강사 월별 시수 계산 유틸리티"""
from datetime import date
from sqlalchemy import extract, func, or_
from app.models import db, Course, CourseSession, Attendance

# 보강 관련 course_type 집합 (신규 타입 + 기존 호환)
MAKEUP_TYPES = frozenset({'보강수업', '보강(프리미엄)', '보강(정규반)', '보강(하크니스)'})


def is_makeup_type(course_type: str) -> bool:
    """보강 계열 수업 타입인지 확인"""
    return bool(course_type and course_type.startswith('보강'))


def get_grade_level(course_grade):
    """Course.grade → '초등' or '중등'"""
    return '초등' if str(course_grade or '').startswith('초') else '중등'


def calculate_session_hours(course_type, grade_level, attended_count):
    """
    수업 유형 + 학년 구분 + 출석 학생 수 → 시수(float)
    26-03월 이후 기준:

    - 베이직:               0.5 (고정)
    - 프리미엄:             1.0 (고정)
    - 시그니처/특강/모의고사: 0.0 (별도 수당)
    - 보강(프리미엄):       0명=0.0 / 1명+=1.0 (1:1 전용)
    - 보강(정규반):         0명=0.0 / 1명+=0.5 (그룹 보강)
    - 보강(하크니스):       0명=0.0 / 1명+=0.5 (그룹 보강)
    - 보강수업 (구형):      0명=0.0 / 1:1=1.0 / 그룹=0.5 (기존 데이터 호환)
    - 정규반(초등):         1명=1.0 / 2명=2.0 / n>=3: 2.0+(n-2)*0.5
    - 정규반(중등/고등):    1명=1.0 / 2명=2.5 / n>=3: 2.5+(n-2)*0.5
    - 하크니스(초등):       1명=1.0 / 2명=2.5 / n>=3: 2.5+(n-2)*0.5
    - 하크니스(중등/고등):  1명=1.0 / 2명=3.0 / n>=3: 3.0+(n-2)*0.5
    - 체험단:               0명=0.0 / 1명=1.0 / n>=2: 정규반 공식 동일
    """
    n = max(0, attended_count or 0)

    if course_type == '베이직':
        return 0.0 if n == 0 else 0.5
    if course_type == '프리미엄':
        return 0.0 if n == 0 else 1.0
    if course_type in ('시그니처', '특강', '모의고사'):
        return 0.0
    # 보강 신규 타입 (명시적 구분)
    if course_type == '보강(프리미엄)':
        return 0.0 if n == 0 else 1.0
    if course_type in ('보강(정규반)', '보강(하크니스)'):
        return 0.0 if n == 0 else 0.5
    # 보강수업 (기존 데이터 호환: 1:1=1.0, 그룹=0.5)
    if course_type == '보강수업':
        if n == 0:
            return 0.0
        return 1.0 if n == 1 else 0.5

    is_elem = (grade_level == '초등')

    def regular(n):
        if n == 0:
            return 0.0
        if n == 1:
            return 1.0
        if is_elem:
            # 초등: 2명=2.0, 3명부터 +0.5
            return 2.0 + (n - 2) * 0.5
        else:
            # 중등: 2명=2.5, 3명부터 +0.5
            return 2.5 + (n - 2) * 0.5

    if course_type == '정규반':
        return regular(n)

    if course_type == '하크니스':
        if n == 0:
            return 0.0
        if n == 1:
            return 1.0
        # 초등: 2명=2.5, 3명부터 +0.5 / 중등: 2명=3.0, 3명부터 +0.5
        base = 2.5 if is_elem else 3.0
        return base + (n - 2) * 0.5

    if course_type == '체험단':
        if n == 0:
            return 0.0
        return 1.0 if n == 1 else regular(n)

    return 0.0


def _week_of_month(d):
    """날짜 → 해당 월의 몇째 주인지 (1~5)"""
    first_day = d.replace(day=1)
    # 월의 첫 번째 날 기준으로 주를 계산 (달력 주 단위)
    adjusted = d.day + first_day.weekday()
    return (adjusted - 1) // 7 + 1


def build_teacher_monthly_data(teacher_id, year, month):
    """
    강사의 월별 시수 데이터를 계산해 반환.

    Returns dict:
    {
      'sessions': [
          {'session': CourseSession, 'course': Course,
           'attended': int, 'hours': float, 'week': 1-5}, ...
      ],
      'by_type': {
          course_type: {'w1': h, 'w2': h, 'w3': h, 'w4': h, 'w5': h, 'total': h}, ...
      },
      'weekly_totals': {1: h, 2: h, 3: h, 4: h, 5: h},
      'auto_total': float,
      'special': [
          {'session': CourseSession, 'course': Course, 'attended': int}, ...
      ]
    }
    """
    SPECIAL_TYPES = {'시그니처', '특강', '모의고사'}

    # 시수 집계 대상 세션:
    #   1) session.status == 'completed' (정상 마킹된 세션)
    #   2) 또는 출결이 입력된 세션 (attendance.checked_at IS NOT NULL).
    #      강사가 학생 출결만 입력하고 '✓ 완료' 버튼을 누르지 않은 경우에도
    #      시수에 정상 반영되도록 한다 (status가 scheduled로 남아있어도 포함).
    attended_subq = (
        db.session.query(Attendance.session_id)
        .filter(Attendance.checked_at.isnot(None))
        .distinct()
        .subquery()
    )
    sessions = (
        CourseSession.query
        .join(Course)
        .filter(
            Course.teacher_id == teacher_id,
            CourseSession.status != 'cancelled',
            or_(
                CourseSession.status == 'completed',
                CourseSession.session_id.in_(db.session.query(attended_subq.c.session_id))
            ),
            extract('year', CourseSession.session_date) == year,
            extract('month', CourseSession.session_date) == month
        )
        .order_by(CourseSession.session_date)
        .all()
    )

    if not sessions:
        return {
            'sessions': [],
            'by_type': {},
            'weekly_totals': {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
            'auto_total': 0.0,
            'special': [],
        }

    session_ids = [s.session_id for s in sessions]

    # 세션별 출석 학생 수 일괄 조회
    count_rows = (
        db.session.query(
            Attendance.session_id,
            func.count(Attendance.attendance_id)
        )
        .filter(
            Attendance.session_id.in_(session_ids),
            Attendance.status.in_(['present', 'late'])
        )
        .group_by(Attendance.session_id)
        .all()
    )
    count_map = {row[0]: row[1] for row in count_rows}

    # 각 세션별 과목 캐시
    course_map = {s.session_id: s.course for s in sessions}

    result_sessions = []
    special = []
    by_type = {}
    weekly_totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}

    # 같은 날짜+시간에 겹치는 보강수업은 원 수업 출석에 합산
    # (별도 1.0시수가 아닌, 원 수업 인원으로 합산 계산)
    from collections import defaultdict
    time_groups = defaultdict(list)
    for s in sessions:
        time_groups[(s.session_date, s.start_time)].append(s)

    merged_skip = set()  # 병합된 보강 세션 ID (개별 집계 제외)
    merged_attended = {}  # session_id → 합산 출석수 (primary session용)

    for key, group in time_groups.items():
        if len(group) < 2:
            continue
        primary = next(
            (s for s in group if not is_makeup_type(course_map[s.session_id].course_type)),
            None
        )
        if primary is None:
            continue
        # 보강 세션 출석을 primary에 합산
        total = sum(count_map.get(s.session_id, 0) for s in group)
        merged_attended[primary.session_id] = total
        for s in group:
            if s.session_id != primary.session_id:
                merged_skip.add(s.session_id)

    for s in sessions:
        if s.session_id in merged_skip:
            continue

        course = course_map[s.session_id]
        attended = merged_attended.get(s.session_id, count_map.get(s.session_id, 0))
        grade_level = get_grade_level(course.grade)
        course_type = course.course_type or '기타'
        hours = calculate_session_hours(course_type, grade_level, attended)
        week = _week_of_month(s.session_date)

        row = {
            'session': s,
            'course': course,
            'attended': attended,
            'hours': hours,
            'week': week,
        }

        if course_type in SPECIAL_TYPES:
            special.append(row)
        else:
            result_sessions.append(row)

        # by_type 집계
        if course_type not in by_type:
            by_type[course_type] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 'total': 0.0}
        by_type[course_type][week] = by_type[course_type].get(week, 0.0) + hours
        by_type[course_type]['total'] += hours

        # weekly_totals (special 포함하지 않음)
        if course_type not in SPECIAL_TYPES:
            weekly_totals[week] = weekly_totals.get(week, 0.0) + hours

    auto_total = sum(weekly_totals.values())

    return {
        'sessions': result_sessions,
        'by_type': by_type,
        'weekly_totals': weekly_totals,
        'auto_total': auto_total,
        'special': special,
    }
