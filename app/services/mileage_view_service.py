# -*- coding: utf-8 -*-
"""마일리지 화면(학생 마이페이지 / 학부모 자녀 화면) 공용 데이터 조립

두 화면이 보여주는 정보가 완전히 같아서(등급·이번 달 점수·뱃지판·적립내역·
공개설정), 로직을 한 곳에 두고 app/profile/routes.py와
app/parent_portal/routes.py 양쪽에서 가져다 쓴다. 블루프린트의 routes.py는
서로를 import하면 안 되므로(순환 참조 위험, 역할도 애매해짐) 서비스
계층에 둔다.
"""
from datetime import datetime, timedelta

from flask import request

from app.services import mileage_service, badge_service, ranking_service
from app.services.mileage_rules import POINT_RULES, SEASON_ACTIVITY_SUMMARY, get_level_group

MILEAGE_CONSENT_DOC_VERSION = 'v1.0'  # docs/mileage/03_공개_및_저작물_활용_동의서.md 버전
MILEAGE_HISTORY_PER_PAGE = 20


def is_under_14(birth_date):
    if not birth_date:
        return False  # 생년월일 미입력 - 판단 불가 시 제한하지 않음(관리자가 별도 확인)
    today = (datetime.utcnow() + timedelta(hours=9)).date()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age < 14


def _build_activity_summary(student_id, season):
    """SEASON_ACTIVITY_SUMMARY 순서 그대로, 0건인 활동도 포함해 반환한다
    (개발지시서 16 3항 - "안 한 것이 보여야 동기가 생긴다")."""
    counts = mileage_service.get_season_activity_summary(student_id, season)
    summary = []
    for item in SEASON_ACTIVITY_SUMMARY:
        stat = counts.get(item['activity_code'], {'count': 0, 'points': 0})
        summary.append({
            'activity_code': item['activity_code'],
            'label': item['label'],
            'unit': item['unit'],
            'count': stat['count'],
            'points': stat['points'],
        })
    return summary


def build_mileage_context(student, page=None):
    """마이페이지·자녀 상세 화면에서 공용으로 쓰는 마일리지 데이터 묶음.

    page를 생략하면 요청 쿼리스트링의 mpage 파라미터를 쓴다(마이페이지처럼
    같은 페이지 안에서 적립내역만 다시 로드하는 경우). 학부모 화면처럼
    별도 라우트에서 페이지 번호를 직접 관리하고 싶으면 page를 넘긴다.
    """
    total_points = mileage_service.get_total_points(student.student_id)
    pending_points = mileage_service.get_pending_points(student.student_id)
    season = mileage_service.get_season()
    season_points = mileage_service.get_season_points(student.student_id, season)
    tier = mileage_service.get_tier(total_points)
    badge_board_all = badge_service.get_badge_board(student.student_id)
    # 정책 8.1 - 3×3 수집판은 BG01~BG09만. 최종 뱃지(BG10)는 판 위에 별도 표시.
    badge_board = [b for b in badge_board_all if not b['is_final']]
    final_badge = next((b for b in badge_board_all if b['is_final']), None)
    # 마이페이지 대시보드용 - "N개 중 M개"는 최종 뱃지까지 포함한 전체 개수 기준(개발지시서 16 4항).
    owned_badges = [b for b in badge_board_all if b['owned']]
    badge_total_count = len(badge_board_all)
    # 미획득 뱃지 중 진행도가 가장 높은 것 - "가장 얻기 쉬운 미획득 뱃지" 안내용.
    # 최종 뱃지(BG10)는 다른 뱃지를 전부 모아야 하는 조건이라 "쉬운 다음 목표"로
    # 안내할 대상이 아니므로 badge_board(비최종)에서만 고른다.
    unearned = [b for b in badge_board if not b['owned']]
    easiest_unearned_badge = max(unearned, key=lambda b: b['progress']) if unearned else None

    if page is None:
        page = request.args.get('mpage', 1, type=int)
    per_page = MILEAGE_HISTORY_PER_PAGE
    total_history = mileage_service.count_point_history(student.student_id)
    total_pages = max(1, -(-total_history // per_page))  # ceil
    page = min(max(page, 1), total_pages)
    history = mileage_service.get_point_history(student.student_id, limit=per_page, offset=(page - 1) * per_page)
    # 대시보드 요약에는 최근 5건만(개발지시서 16 5항) - 전체 이력(history)과 별개로 둔다.
    recent_history = mileage_service.get_point_history(student.student_id, limit=5, offset=0)

    # 이번 달 잠정 순위 - 확정 스냅샷을 만들기 전이라 실시간 계산만 가능
    my_rank = None
    my_group = get_level_group(student.grade)
    if my_group:
        live_ranking = ranking_service.build_ranking(season, finalize=False)
        for row in live_ranking:
            if row['level_group'] == my_group and row['student_id'] == student.student_id:
                my_rank = row['rank']
                break

    consent_status = mileage_service.get_consent_status(student.student_id)
    activity_summary = _build_activity_summary(student.student_id, season)

    return {
        'total_points': total_points,
        'pending_points': pending_points,
        'season': season,
        'season_points': season_points,
        'tier': tier,
        'activity_summary': activity_summary,
        'badge_board': badge_board,
        'final_badge': final_badge,
        'owned_badges': owned_badges,
        'badge_total_count': badge_total_count,
        'easiest_unearned_badge': easiest_unearned_badge,
        'history': history,
        'recent_history': recent_history,
        'history_page': page,
        'history_total_pages': total_pages,
        'my_rank': my_rank,
        'my_group': my_group,
        'consent_status': consent_status,
        'under_14': is_under_14(student.birth_date),
        'point_rules': POINT_RULES,
    }
