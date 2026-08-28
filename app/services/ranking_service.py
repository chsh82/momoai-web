# -*- coding: utf-8 -*-
"""월간 랭킹 (정책 제7조)

집계 대상: status='confirmed'인 해당 시즌 point_events의 합계.
동점 처리 순서: ① EX01 적립 건수 ② RW01 적립 건수 ③ 해당 점수 도달 시각
  - "해당 점수 도달 시각"은 그 시즌 마지막 confirmed 적립의 created_at으로
    본다(그 적립이 최종 누적 점수를 완성한 시점이므로).
랭킹 공개 비동의 학생은 순위 산정에는 포함하되(다른 학생 등수 왜곡 방지),
결과 항목에 anonymous=True를 표시한다 - 실제 익명 표시는 4단계 화면 몫이다.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from app.models import db
from app.models.student import Student
from app.models.mileage import PointEvent, MonthlyRanking, MileageConsent
from app.services.mileage_rules import get_level_group


def previous_season(now=None):
    """전월의 'YYYY-MM' (KST 기준). 매월 1일 배치가 "전월"을 대상으로 하기 위함."""
    now = now or datetime.utcnow()
    kst_today = (now + timedelta(hours=9)).date()
    first_of_this_month = kst_today.replace(day=1)
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_prev_month.strftime('%Y-%m')


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


def _consent_map(student_ids):
    """정책 A항목(랭킹 공개) 동의 여부. 같은 학생의 여러 행 중 가장 최근 것을 채택한다."""
    if not student_ids:
        return {}
    rows = MileageConsent.query.filter(
        MileageConsent.student_id.in_(student_ids),
        MileageConsent.consent_type == 'A',
    ).order_by(MileageConsent.agreed_at.desc()).all()

    result = {}
    for c in rows:
        if c.student_id in result:
            continue  # 이미 최신 행을 채택함
        result[c.student_id] = bool(c.is_agreed) and c.revoked_at is None
    return result


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
    consents = _consent_map(student_ids)

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
            'ex01_count': ex01_counts.get(student_id, 0),
            'rw01_count': rw01_counts.get(student_id, 0),
            'reach_time': reach_times.get(student_id) or datetime.max,
            'consent': consents.get(student_id, False),
        })

    results = []
    for group, entries in grouped.items():
        entries.sort(key=lambda e: (-e['points'], -e['ex01_count'], -e['rw01_count'], e['reach_time']))
        for idx, e in enumerate(entries, start=1):
            e['rank'] = idx
            e['level_group'] = group
            e['season'] = season
            e['anonymous'] = not e['consent']
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
        consents = _consent_map([r.student_id for r in rows])
        return [
            {
                'student_id': r.student_id,
                'level_group': r.level_group,
                'rank': r.rank,
                'points': r.points,
                'season': season,
                'anonymous': not consents.get(r.student_id, False),
                'is_final': True,
            }
            for r in rows
        ]

    live = build_ranking(season, finalize=False)
    for e in live:
        e['is_final'] = False
    if level_group:
        live = [e for e in live if e['level_group'] == level_group]
    return live
