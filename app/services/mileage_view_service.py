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
from app.services.mileage_rules import POINT_RULES, get_level_group

MILEAGE_CONSENT_DOC_VERSION = 'v1.0'  # docs/mileage/03_공개_및_저작물_활용_동의서.md 버전
MILEAGE_HISTORY_PER_PAGE = 20


def is_under_14(birth_date):
    if not birth_date:
        return False  # 생년월일 미입력 - 판단 불가 시 제한하지 않음(관리자가 별도 확인)
    today = (datetime.utcnow() + timedelta(hours=9)).date()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age < 14


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

    if page is None:
        page = request.args.get('mpage', 1, type=int)
    per_page = MILEAGE_HISTORY_PER_PAGE
    total_history = mileage_service.count_point_history(student.student_id)
    total_pages = max(1, -(-total_history // per_page))  # ceil
    page = min(max(page, 1), total_pages)
    history = mileage_service.get_point_history(student.student_id, limit=per_page, offset=(page - 1) * per_page)

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

    return {
        'total_points': total_points,
        'pending_points': pending_points,
        'season': season,
        'season_points': season_points,
        'tier': tier,
        'badge_board': badge_board,
        'final_badge': final_badge,
        'history': history,
        'history_page': page,
        'history_total_pages': total_pages,
        'my_rank': my_rank,
        'my_group': my_group,
        'consent_status': consent_status,
        'under_14': is_under_14(student.birth_date),
        'point_rules': POINT_RULES,
    }
