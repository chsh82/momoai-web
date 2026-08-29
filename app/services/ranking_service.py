# -*- coding: utf-8 -*-
"""월간 랭킹 (정책 제7조)

집계 대상: status='confirmed'인 해당 시즌 point_events의 합계.
동점 처리 순서: ① EX01 적립 건수 ② RW01 적립 건수 ③ 해당 점수 도달 시각
  - "해당 점수 도달 시각"은 그 시즌 마지막 confirmed 적립의 created_at으로
    본다(그 적립이 최종 누적 점수를 완성한 시점이므로).
모든 학생을 이름+학년으로 표시한다(2026-08-30 결정사항 - 공개 동의(A항목)
기반 익명 처리를 폐지). mileage_consents A항목은 더 이상 조회하지 않는다 -
테이블과 기존 데이터, B·C항목(우수답안 게시·홍보물 활용) 동의는 그대로 둔다.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from app.models import db
from app.models.student import Student
from app.models.mileage import PointEvent, MonthlyRanking, StudentBadge
from app.services.mileage_rules import get_level_group


def previous_season(now=None):
    """전월의 'YYYY-MM' (KST 기준). 매월 1일 배치가 "전월"을 대상으로 하기 위함."""
    now = now or datetime.utcnow()
    kst_today = (now + timedelta(hours=9)).date()
    first_of_this_month = kst_today.replace(day=1)
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_prev_month.strftime('%Y-%m')


def recent_seasons(n=12, now=None):
    """최근 n개월의 'YYYY-MM' 목록(이번 달 포함, 최신순). 랭킹 페이지 월 선택용."""
    now = now or datetime.utcnow()
    kst_today = (now + timedelta(hours=9)).date()
    seasons = []
    year, month = kst_today.year, kst_today.month
    for _ in range(n):
        seasons.append(f'{year:04d}-{month:02d}')
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return seasons


def _badge_count_by_student(student_ids):
    if not student_ids:
        return {}
    rows = db.session.query(
        StudentBadge.student_id, func.count(StudentBadge.id)
    ).filter(
        StudentBadge.student_id.in_(student_ids),
        StudentBadge.revoked_at.is_(None),
    ).group_by(StudentBadge.student_id).all()
    return {student_id: count for student_id, count in rows}


def _display_label(student):
    """이름+학년으로 표시한다. 학교명·연락처·생년월일 등은 절대 포함하지 않는다."""
    return f'{student.name} {student.grade}'


def _season_points_by_student(season):
    rows = db.session.query(
        PointEvent.student_id, func.sum(PointEvent.points)
    ).filter(
        PointEvent.season == season,
        PointEvent.status == 'confirmed',
    ).group_by(PointEvent.student_id).all()
    return {student_id: points for student_id, points in rows}


def _activity_count_by_student(season, activity_code, student_ids):
    if not student_ids:
        return {}
    rows = db.session.query(
        PointEvent.student_id, func.count(PointEvent.event_id)
    ).filter(
        PointEvent.season == season,
        PointEvent.status == 'confirmed',
        PointEvent.activity_code == activity_code,
        PointEvent.student_id.in_(student_ids),
    ).group_by(PointEvent.student_id).all()
    return {student_id: count for student_id, count in rows}


def _reach_time_by_student(season, student_ids):
    if not student_ids:
        return {}
    rows = db.session.query(
        PointEvent.student_id, func.max(PointEvent.created_at)
    ).filter(
        PointEvent.season == season,
        PointEvent.status == 'confirmed',
        PointEvent.student_id.in_(student_ids),
    ).group_by(PointEvent.student_id).all()
    return {student_id: reached_at for student_id, reached_at in rows}


def _upsert_ranking_row(season, level_group, student_id, rank, points, is_final):
    row = MonthlyRanking.query.filter_by(
        season=season, level_group=level_group, student_id=student_id
    ).first()
    if row:
        row.rank = rank
        row.points = points
        row.is_final = is_final
    else:
        row = MonthlyRanking(
            season=season, level_group=level_group, student_id=student_id,
            rank=rank, points=points, is_final=is_final,
        )
        db.session.add(row)


def build_ranking(season, finalize=False, is_final=False):
    """시즌 포인트를 학년(레벨) 그룹별로 집계해 순위를 산정한다.

    Args:
        season: 'YYYY-MM'
        finalize: True면 monthly_rankings에 저장한다(add/flush까지 - commit은 호출부)
        is_final: finalize=True일 때 저장할 is_final 값.
                 1일 배치는 finalize=True, is_final=False (잠정)
                 3일 배치는 finalize=True, is_final=True (확정)
    Returns:
        list[dict]: level_group/rank 순으로 정렬된 결과. 학년 밴드에 매칭되지
                   않는 학생(데이터 이상)은 결과에서 제외되고 로그로만 남는다.
    """
    student_points = _season_points_by_student(season)
    if not student_points:
        return []

    student_ids = list(student_points.keys())
    students = {s.student_id: s for s in Student.query.filter(Student.student_id.in_(student_ids)).all()}
    ex01_counts = _activity_count_by_student(season, 'EX01', student_ids)
    rw01_counts = _activity_count_by_student(season, 'RW01', student_ids)
    reach_times = _reach_time_by_student(season, student_ids)
    badge_counts = _badge_count_by_student(student_ids)

    grouped = defaultdict(list)
    for student_id, points in student_points.items():
        student = students.get(student_id)
        if not student:
            continue
        group = get_level_group(student.grade)
        if group is None:
            import logging
            logging.getLogger(__name__).warning(
                '랭킹 밴드 매칭 실패 - student_id=%s grade=%r (RANKING_LEVEL_GROUPS 확인 필요)',
                student_id, student.grade,
            )
            continue
        grouped[group].append({
            'student_id': student_id,
            'points': points,
            'grade': student.grade,
            'badge_count': badge_counts.get(student_id, 0),
            'display_name': _display_label(student),
            'ex01_count': ex01_counts.get(student_id, 0),
            'rw01_count': rw01_counts.get(student_id, 0),
            'reach_time': reach_times.get(student_id) or datetime.max,
        })

    results = []
    for group, entries in grouped.items():
        entries.sort(key=lambda e: (-e['points'], -e['ex01_count'], -e['rw01_count'], e['reach_time']))
        for idx, e in enumerate(entries, start=1):
            e['rank'] = idx
            e['level_group'] = group
            e['season'] = season
            del e['reach_time']  # 원본 datetime.max 채움값은 결과에 노출하지 않음
            results.append(e)
            if finalize:
                _upsert_ranking_row(season, group, e['student_id'], idx, e['points'], is_final)

    if finalize:
        db.session.flush()

    results.sort(key=lambda e: (e['level_group'], e['rank']))
    return results


def get_ranking(season, level_group=None):
    """확정된 스냅샷을 조회한다. 없으면 잠정 순위를 실시간 계산해 반환한다."""
    query = MonthlyRanking.query.filter_by(season=season, is_final=True)
    if level_group:
        query = query.filter_by(level_group=level_group)
    rows = query.order_by(MonthlyRanking.level_group, MonthlyRanking.rank).all()

    if rows:
        student_ids = [r.student_id for r in rows]
        badge_counts = _badge_count_by_student(student_ids)
        students = {s.student_id: s for s in Student.query.filter(Student.student_id.in_(student_ids)).all()}
        result = []
        for r in rows:
            student = students.get(r.student_id)
            result.append({
                'student_id': r.student_id,
                'level_group': r.level_group,
                'rank': r.rank,
                'points': r.points,
                'grade': student.grade if student else None,
                'badge_count': badge_counts.get(r.student_id, 0),
                'display_name': _display_label(student) if student else '(탈퇴한 학생)',
                'season': season,
                'is_final': True,
            })
        return result

    live = build_ranking(season, finalize=False)
    for e in live:
        e['is_final'] = False
    if level_group:
        live = [e for e in live if e['level_group'] == level_group]
    return live
