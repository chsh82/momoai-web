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
from datetime import date, datetime, timedelta

# 마일리지 적립 시작일(KST 기준). 이보다 이전 활동에는 포인트를 부여하지
# 않는다(2026-08-29 결정사항, 2026-08-30 8/31로 앞당김) - mileage_service.award_points()의
# 게이트와 mileage_batch_service.run_weekly_attendance_batch()의 주간 배치
# 게이트가 이 상수 하나만 참조한다. 나중에 게이트를 걷어낼 때 이 상수와 두
# 참조 지점만 지우면 된다(app/services/mileage_service.py, app/services/mileage_batch_service.py).
MILEAGE_START_DATE = date(2026, 8, 31)
# MILEAGE_START_DATE(KST 자정)에 해당하는 UTC 시각. BG07처럼 point_events가
# 아니라 다른 테이블(post_likes/comments)의 created_at(naive UTC)을 직접
# 비교해야 하는 게이트에서 쓴다 - award_points()처럼 매번 KST로 변환할 필요
# 없이 이 상수 하나로 UTC 컬럼과 바로 비교할 수 있다.
MILEAGE_START_DATETIME_UTC = datetime.combine(MILEAGE_START_DATE, datetime.min.time()) - timedelta(hours=9)

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
    'RW02': {
        'name': '기본과제글 제출',
        'points': 100,
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

# 과제 유형(Essay.essay_type) -> 첨삭 확정 시 지급할 포인트 코드
# (2026-08-29 결정사항 - 과제 업로드 시 유형 선택 기능). 'etc'는 지급 대상이
# 아니므로 None. finalize_essay()/manual_correction()이 이 표만 참조하면
# 되게 해, 새 유형이 늘어나도 여기 한 곳만 고치면 된다.
ESSAY_TYPE_POINT_CODE = {
    'rewriting': 'RW01',
    'basic': 'RW02',
    'etc': None,
}

# 정책 8.3 회원 등급 (누적 포인트 기준, 오름차순) - 2026-08-29 개정
# (RW02 신설로 기본과제글도 매 회 적립되어 누적 속도가 빨라진 것을 반영).
TIER_TABLE = [
    (1, '브론즈', 0),
    (2, '실버', 2000),
    (3, '골드', 8000),
    (4, '다이아', 20000),
    (5, '마스터', 45000),
]

# 정책 제7조 3항 - 월간 랭킹 그룹 (학년 밴드). Student.grade(초1~고3, 12개 값)를
# 그대로 그룹으로 쓰면 그룹당 인원이 너무 적어 순위가 무의미해질 수 있어
# 5개 밴드로 묶는다(2026-08-28 결정사항). 나중에 밴드를 조정할 수 있도록
# 상수로 분리해 둔다 - 코드 변경 없이 이 딕셔너리만 고치면 됨.
RANKING_LEVEL_GROUPS = {
    'elem12': {'label': '초1~2', 'grades': ['초1', '초2']},
    'elem34': {'label': '초3~4', 'grades': ['초3', '초4']},
    'elem56': {'label': '초5~6', 'grades': ['초5', '초6']},
    'middle': {'label': '중1~3', 'grades': ['중1', '중2', '중3']},
    'high': {'label': '고1~3', 'grades': ['고1', '고2', '고3']},
}


# AT01/AT02 출결 판정 기준 status 값(2026-08-28 결정사항).
# Attendance 모델 주석에는 present/absent/late/excused 4가지만 적혀 있지만
# 실데이터 확인 결과 absent_makeup(보강 처리된 결석)도 존재했다. 결석 판정에
# 쓰는 값을 여기서 명시적으로 관리해, 나중에 또 다른 status가 나타나도
# 코드를 안 뒤지고 이 목록만 보면 되게 한다. 목록에 없는 값을 만나면
# 배치가 경고 로그를 남긴다(mileage_batch_service.py).
ATTENDANCE_ATTENDED_STATUSES = ('present', 'late')
ATTENDANCE_ABSENT_STATUSES = ('absent', 'absent_makeup', 'excused')
# absent_makeup은 "결석했고 보강 처리됨"이라는 뜻이라 결석에 포함한다 - 실제
# 보강 출석 여부는 makeup_attended_count가 별도로 확인하므로, 여기서 빼면
# 보강 신청만 하고 출석 안 한 학생이 통과한다. excused도 사유 불문 결석
# 처리한다(정책 4.5.4).
ATTENDANCE_KNOWN_STATUSES = ATTENDANCE_ATTENDED_STATUSES + ATTENDANCE_ABSENT_STATUSES

# 중복 정규 세션(강사 교체 등으로 병행 생성된 Course) 출결 채택 우선순위
# (2026-08-28 재결정 - "가장 나쁜 상태 채택"에서 변경).
# 근거: 같은 시각에 강좌가 두 개 등록돼 있어도 학생은 한 곳에만 있을 수
# 있다. 한쪽에 present가 찍혔으면 실제로 출석한 것이고, 다른 쪽의 absent는
# 관리되지 않는 중복 레코드의 잔재일 가능성이 크다(실제로 동일 시간대에
# 병행 생성된 정규 강좌가 있던 학생 사례에서 확인됨 - 한쪽 강좌가 8주 내내
# absent로 방치돼 있었음). 출석은
# 확인해야 찍히지만 결석은 방치해도 남으므로, "체크된 좋은 기록"을 우선한다.
# 숫자가 낮을수록 먼저 채택된다. 체크 자체가 안 된 기록(None)은 이 표와
# 무관하게 항상 가장 마지막 순위다.
ATTENDANCE_STATUS_PRIORITY = {
    'present': 0,
    'late': 1,
    'absent_makeup': 2,
    'excused': 3,
    'absent': 4,
}


# AT02(분기 완주) 판정에서 "보강 수업"을 구분하는 기준(2026-08-28 결정사항).
# 실데이터 확인 결과 Course.course_type이 '보강수업'/'보강(정규반)'/'보강(프리미엄)'/
# '보강(하크니스)' 등으로 다양하게 찍히지만 전부 '보강'으로 시작한다. 강좌 유형이
# 늘어날 수 있어 하드코딩하지 않고 여기서 접두어 하나로 관리한다.
MAKEUP_COURSE_TYPE_PREFIX = '보강'


def is_makeup_course_type(course_type):
    """course_type이 보강 수업 계열인지 여부."""
    return (course_type or '').startswith(MAKEUP_COURSE_TYPE_PREFIX)


# 뱃지 아이콘 자산(static/badges/*)이 아직 없어 임시로 쓰는 이모지 매핑
# (2026-08-28 결정사항, 4단계 화면 작업). Badge.icon_path가 채워지면 그쪽을
# 우선 쓰고, 없을 때만 이 표를 fallback으로 쓴다 - badge_service.get_badge_board()에서 사용.
BADGE_EMOJI_FALLBACK = {
    'BG01': '🖊️',
    'BG02': '❓',
    'BG03': '✏️',
    'BG04': '✨',
    'BG05': '🌱',
    'BG06': '👣',
    'BG07': '❤️',
    'BG08': '🌳',
    'BG09': '🏆',
    'BG10': '📚',
}


# 마이페이지 대시보드 "이번 달 활동 요약"에 표시할 활동 (개발지시서 16 3항).
# EX01/QS02(특별 선정)·AT02(분기 단위)·EV01(재량 지급)·QZ02(만점 보너스)는
# "이번 달에 무엇을 했는지" 요약과 성격이 안 맞아 제외한다.
SEASON_ACTIVITY_SUMMARY = [
    {'activity_code': 'RW01', 'label': '리라이팅', 'unit': '편'},
    {'activity_code': 'RW02', 'label': '기본과제글', 'unit': '편'},
    {'activity_code': 'QZ01', 'label': '퀴즈', 'unit': '회'},
    {'activity_code': 'QS01', 'label': '질문', 'unit': '건'},
    {'activity_code': 'CM01', 'label': '댓글', 'unit': '건'},
    {'activity_code': 'AT01', 'label': '출석', 'unit': '주'},
]


def get_level_group(grade):
    """학생의 grade 값으로 랭킹 그룹 코드를 반환한다. 매칭되는 밴드가 없으면 None."""
    for code, info in RANKING_LEVEL_GROUPS.items():
        if grade in info['grades']:
            return code
    return None
