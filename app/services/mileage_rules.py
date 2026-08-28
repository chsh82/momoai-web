# -*- coding: utf-8 -*-
"""마일리지 적립 규칙 상수

docs/mileage/01_마일리지_운영정책.md 제4조 적립표를 그대로 옮긴 것.
점수·상한을 바꿀 때는 이 파일만 고치면 되고, 이미 확정된 point_events 이력은
소급 변경되지 않는다(docs/mileage/05_DB설계서.md 1.3절).

각 필드:
  name                코드명
  points               고정 점수. 범위 지급(EV01)이면 None
  points_min/points_max  points가 None일 때 허용 범위 (award_points 호출 시 points를 반드시 지정)
  allowed_source_types 이 코드가 허용하는 source_type 목록(화이트리스트).
                       award_points()가 여기 없는 source_type이 들어오면 ValueError를 던진다.
  confirm_delay_hours   0이면 즉시 confirmed, 그 외에는 occurred_at + N시간 후 confirm_pending_points()가 확정
  daily_cap            같은 활동 코드의 KST 하루 건수 상한 (건수 기준). None이면 검사 안 함
  monthly_cap          같은 활동 코드의 KST 월 누적 점수 상한. None이면 검사 안 함

AT01(주 1회)·AT02(분기당 1회)·RW01(과제당 1회)·QZ01/QZ02(회차당 1회)는
daily_cap/monthly_cap이 아니라 point_events의 (student_id, activity_code,
source_type, source_id, entry_type) 유니크 제약이 상한 역할을 한다 — 주간·분기
배치가 소스ID를 `{student_id}-{연도}-W{주차}` / `{student_id}-{연도}Q{분기}`
형태로 만들어 호출하므로 같은 기간에 두 번 지급될 수 없다.

EX01("강사당 주 3명")은 학생이 아니라 지급자(강사) 기준 상한이라 이 딕셔너리
구조로 표현할 수 없다. 1단계 award_points()는 이 상한을 검사하지 않으며,
2단계에서 "우수답안 선정" 라우트가 직접 검사한다.
"""

POINT_RULES = {
    'RW01': {
        'name': '리라이팅 제출',
        'points': 500,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['essay'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'EX01': {
        'name': '우수답안 선정',
        'points': 1000,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['essay', 'post'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'QZ01': {
        'name': '퀴즈 응시(정답률 60% 이상)',
        'points': 100,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['quiz_session'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'QZ02': {
        'name': '퀴즈 만점 보너스',
        'points': 100,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['quiz_session'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'QS01': {
        'name': '질문 등록',
        'points': 100,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['post'],
        'confirm_delay_hours': 24,
        'daily_cap': 2,
        'monthly_cap': 1000,
    },
    'QS02': {
        'name': '우수질문 선정',
        'points': 500,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['post'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'CM01': {
        'name': '댓글 작성',
        'points': 10,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['comment'],
        'confirm_delay_hours': 24,
        'daily_cap': 5,
        'monthly_cap': None,
    },
    'AT01': {
        'name': '주 5일 이상 출석',
        'points': 100,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['attendance_week'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'AT02': {
        'name': '분기 무결석 완주',
        'points': 1000,
        'points_min': None,
        'points_max': None,
        'allowed_source_types': ['attendance_quarter'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': None,
    },
    'EV01': {
        'name': '이벤트·교사 재량 지급',
        'points': None,  # 범위 지급 - award_points 호출 시 points를 반드시 지정해야 함
        'points_min': 100,
        'points_max': 500,
        'allowed_source_types': ['manual'],
        'confirm_delay_hours': 0,
        'daily_cap': None,
        'monthly_cap': 500,
    },
}

# 정책 8.3 회원 등급 (누적 포인트 기준, 오름차순)
TIER_TABLE = [
    (1, '브론즈', 0),
    (2, '실버', 5000),
    (3, '골드', 20000),
    (4, '다이아', 50000),
    (5, '마스터', 100000),
]
