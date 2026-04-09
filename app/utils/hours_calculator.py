# -*- coding: utf-8 -*-
"""강사 월별 시수 계산 유틸리티"""
from datetime import date
from sqlalchemy import extract, func
from app.models import db, Course, CourseSession, Attendance


def get_grade_level(course_grade):
    """Course.grade → '초등' or '중등'"""
    return '초등' if str(course_grade or '').startswith('초') else '중등'


def calculate_session_hours(course_type, grade_level, attended_count):
    """
    수업 유형 + 학년 구분 + 출석 학생 수 → 시수(float)
    26-03월 이후 기준:

    - 베이직:             0.5 (고정)
    - 프리미엄:           1.0 (고정)
    - 시그니처/특강/모의고사: 0.0 (별도 수당)
    - 보강수업:           1:1=1.0 / 그룹=0.5
    - 정규반(초등):       1명=1.0 / 2명=2.0 / n>=3: 2.0+(n-2)*0.5
    - 정규반(중등/고등):  1명=1.0 / 2명=2.5 / n>=3: 2.5+(n-2)*0.5
    - 하크니스(초등):     1명=1.0 / 2명=2.5 / n>=3: 2.5+(n-2)*0.5
    - 하크니스(중등/고등): 1명=1.0 / 2명=3.0 / n>=3: 3.0+(n-2)*0.5
    - 체험단:             1명=1.0 / n>=2: 정규반 공식 동일
    """
    n = max(0, attended_count or 0)

    if course_type == '베이직':
        return 0.5
    if course_type == '프리미엄':
        return 1.0
    if course_type in ('시그니처', '특강', '모의고사'):
        return 0.0
    if course_type == '보강수업':
        return 1.0 if n <= 1 else 0.5

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
        return 1.0 if n <= 1 else regular(n)

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

    # completed 세션 조회 (해당 강사, 해당 월)
    sessions = (
        CourseSession.query
        .join(Course)
        .filter(
            Course.teacher_id == teacher_id,
            CourseSession.status == 'completed',
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
            (s for s in group if course_map[s.session_id].course_type != '보강수업'),
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
