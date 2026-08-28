# -*- coding: utf-8 -*-
"""마일리지 적립 엔진

라우트에서 point_events에 직접 INSERT하지 않는다. 반드시 award_points()를
거치게 해서 중복 방지·상한 검사를 한 곳에서 처리한다(docs/mileage/05_DB설계서.md 4절).

DB 커밋은 호출부에서 한다. 이 모듈의 함수들은 db.session.add()/flush()까지만
하고 commit()은 하지 않는다 - 기존 라우트가 커밋 시점을 자체적으로 관리하기 때문이다.
"""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models import db
from app.models.mileage import PointEvent
from app.services.mileage_rules import POINT_RULES, TIER_TABLE

KST_OFFSET = timedelta(hours=9)


def _to_kst(dt):
    """UTC datetime을 KST datetime으로 변환(naive, +9h 단순 오프셋).

    기존 app/__init__.py의 kst 템플릿 필터와 동일한 방식을 쓴다.
    """
    return dt + KST_OFFSET


def get_kst_day_range(dt=None):
    """dt(UTC, 생략 시 현재)가 속한 KST 하루의 [시작, 끝) 을 UTC datetime 튜플로 반환.

    occurred_at >= start and occurred_at < end 로 사용한다.
    """
    dt = dt or datetime.utcnow()
    kst_dt = _to_kst(dt)
    kst_day_start = kst_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_day_start = kst_day_start - KST_OFFSET
    utc_day_end = utc_day_start + timedelta(days=1)
    return utc_day_start, utc_day_end


def get_kst_week_range(dt=None):
    """dt(UTC, 생략 시 현재)가 속한 KST 주(월요일 00:00 ~ 다음 월요일 00:00)의
    [시작, 끝) 을 UTC datetime 튜플로 반환.
    """
    dt = dt or datetime.utcnow()
    kst_dt = _to_kst(dt)
    kst_day_start = kst_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    kst_week_start = kst_day_start - timedelta(days=kst_dt.weekday())  # 월요일=0
    utc_week_start = kst_week_start - KST_OFFSET
    utc_week_end = utc_week_start + timedelta(days=7)
    return utc_week_start, utc_week_end


def get_season(dt=None):
    """dt(UTC, 생략 시 현재)를 KST로 변환해 'YYYY-MM' 반환."""
    dt = dt or datetime.utcnow()
    return _to_kst(dt).strftime('%Y-%m')


def _validate_points(rule, activity_code, points):
    """points 파라미터를 규칙에 맞게 검증하고 최종 지급 점수를 반환한다."""
    if rule['points'] is not None:
        # 고정 점수 코드: 호출부가 값을 넘기면 규칙과 정확히 같아야 한다.
        # (값을 임의로 바꾸지 못하게 막는다 - 05_DB설계서.md 1.3절)
        if points is not None and points != rule['points']:
            raise ValueError(
                f"{activity_code}는 고정 {rule['points']}점 코드라 다른 값({points})을 지정할 수 없습니다."
            )
        return rule['points']

    # 범위 지급 코드(EV01 등): points를 반드시 명시해야 한다.
    if points is None:
        raise ValueError(
            f"{activity_code}는 points를 반드시 지정해야 합니다 "
            f"(허용 범위 {rule['points_min']}~{rule['points_max']})."
        )
    if not (rule['points_min'] <= points <= rule['points_max']):
        raise ValueError(
            f"{activity_code}의 points({points})가 허용 범위 "
            f"{rule['points_min']}~{rule['points_max']}를 벗어났습니다."
        )
    return points


def award_points(student_id, activity_code, source_type, source_id,
                 occurred_at=None, points=None, granted_by=None, memo=None):
    """포인트를 적립한다.

    Returns:
        PointEvent: 새로 생성된 적립 기록
        None: 중복 지급이거나 상한을 초과해 지급하지 않은 경우
    Raises:
        ValueError: 알 수 없는 activity_code, 허용되지 않은 source_type,
                   points 값이 규칙과 맞지 않는 경우
    """
    rule = POINT_RULES.get(activity_code)
    if rule is None:
        raise ValueError(f"알 수 없는 활동 코드: {activity_code}")

    allowed_source_types = rule['allowed_source_types']
    if source_type not in allowed_source_types:
        raise ValueError(
            f"{activity_code}는 source_type {allowed_source_types}만 허용합니다 "
            f"(받은 값: {source_type!r})."
        )

    final_points = _validate_points(rule, activity_code, points)

    occurred_at = occurred_at or datetime.utcnow()
    source_id = str(source_id)
    season = get_season(occurred_at)

    # 중복 확인 (조회) - DB 유니크 제약이 최종 방어선이지만, 불필요한 상한 계산을 줄이기 위해 먼저 확인한다.
    existing = PointEvent.query.filter_by(
        student_id=student_id, activity_code=activity_code,
        source_type=source_type, source_id=source_id, entry_type='award',
    ).first()
    if existing is not None:
        return None

    # 일일 건수 상한 (KST 기준 하루)
    if rule['daily_cap'] is not None:
        day_start, day_end = get_kst_day_range(occurred_at)
        today_count = PointEvent.query.filter(
            PointEvent.student_id == student_id,
            PointEvent.activity_code == activity_code,
            PointEvent.entry_type == 'award',
            PointEvent.occurred_at >= day_start,
            PointEvent.occurred_at < day_end,
        ).count()
        if today_count >= rule['daily_cap']:
            return None

    # 월간 점수 상한 (취소되지 않은 적립만 합산)
    if rule['monthly_cap'] is not None:
        month_points = db.session.query(func.coalesce(func.sum(PointEvent.points), 0)).filter(
            PointEvent.student_id == student_id,
            PointEvent.activity_code == activity_code,
            PointEvent.season == season,
            PointEvent.status != 'cancelled',
        ).scalar()
        if month_points + final_points > rule['monthly_cap']:
            return None

    confirm_delay_hours = rule['confirm_delay_hours']
    if confirm_delay_hours == 0:
        status = 'confirmed'
        confirmed_at = occurred_at
    else:
        status = 'pending'
        confirmed_at = None

    event = PointEvent(
        student_id=student_id,
        activity_code=activity_code,
        entry_type='award',
        points=final_points,
        status=status,
        source_type=source_type,
        source_id=source_id,
        season=season,
        occurred_at=occurred_at,
        confirmed_at=confirmed_at,
        granted_by=granted_by,
        memo=memo,
    )
    db.session.add(event)
    try:
        db.session.flush()
    except IntegrityError:
        # 동시 요청으로 유니크 제약을 위반한 경우 - 조회만으로는 못 막는다.
        db.session.rollback()
        return None

    return event


def cancel_points(source_type, source_id, reason, student_id=None):
    """해당 대상의 award 행을 취소 처리한다.

    원본 행의 status를 'cancelled'로 바꾸고, entry_type='cancel'인 음수 행을
    새로 추가한다. 이미 취소된 건은 건너뛴다.

    Returns:
        int: 처리(신규 취소)된 건수
    """
    source_id = str(source_id)
    query = PointEvent.query.filter(
        PointEvent.source_type == source_type,
        PointEvent.source_id == source_id,
        PointEvent.entry_type == 'award',
        PointEvent.status != 'cancelled',
    )
    if student_id is not None:
        query = query.filter(PointEvent.student_id == student_id)

    events = query.all()
    now = datetime.utcnow()
    count = 0
    for original in events:
        original.status = 'cancelled'
        original.cancelled_at = now
        original.cancel_reason = reason

        cancel_event = PointEvent(
            student_id=original.student_id,
            activity_code=original.activity_code,
            entry_type='cancel',
            points=-original.points,
            status='cancelled',
            source_type=original.source_type,
            source_id=original.source_id,
            season=original.season,
            occurred_at=now,
            confirmed_at=now,
            cancelled_at=now,
            cancel_reason=reason,
            related_event_id=original.event_id,
        )
        db.session.add(cancel_event)
        count += 1

    if count:
        db.session.flush()
    return count


def confirm_pending_points(now=None):
    """status='pending'이면서 확정 시각(occurred_at + confirm_delay_hours)이 지난 행을 확정한다.

    Returns:
        int: 확정 처리된 건수
    """
    now = now or datetime.utcnow()
    pending = PointEvent.query.filter_by(entry_type='award', status='pending').all()

    count = 0
    for event in pending:
        rule = POINT_RULES.get(event.activity_code)
        if rule is None:
            continue
        due_at = event.occurred_at + timedelta(hours=rule['confirm_delay_hours'])
        if now >= due_at:
            event.status = 'confirmed'
            event.confirmed_at = now
            count += 1

    if count:
        db.session.flush()
    return count


def get_total_points(student_id):
    """누적 포인트 (취소분 제외 - status != 'cancelled'인 행의 합)."""
    total = db.session.query(func.coalesce(func.sum(PointEvent.points), 0)).filter(
        PointEvent.student_id == student_id,
        PointEvent.status != 'cancelled',
    ).scalar()
    return int(total)


def get_season_points(student_id, season=None):
    """시즌(월) 포인트 (취소분 제외)."""
    season = season or get_season()
    total = db.session.query(func.coalesce(func.sum(PointEvent.points), 0)).filter(
        PointEvent.student_id == student_id,
        PointEvent.season == season,
        PointEvent.status != 'cancelled',
    ).scalar()
    return int(total)


def get_point_history(student_id, limit=50, offset=0):
    """최근 순 적립·취소 이력."""
    return PointEvent.query.filter_by(student_id=student_id) \
        .order_by(PointEvent.created_at.desc()) \
        .offset(offset).limit(limit).all()


def get_tier(total_points):
    """정책 8.3(등급)·8.4(별 진행도)를 함께 반환.

    Returns:
        dict: {'level', 'name', 'stars', 'next_at', 'progress'}
             마스터(최고 등급)는 stars/progress가 None (표시 안 함)
    """
    current = TIER_TABLE[0]
    next_tier = None
    for i, tier in enumerate(TIER_TABLE):
        level, name, threshold = tier
        if total_points >= threshold:
            current = tier
            next_tier = TIER_TABLE[i + 1] if i + 1 < len(TIER_TABLE) else None
        else:
            break

    level, name, threshold = current
    if next_tier is None:
        return {'level': level, 'name': name, 'stars': None, 'next_at': None, 'progress': None}

    next_at = next_tier[2]
    span = next_at - threshold
    progressed = total_points - threshold
    progress = progressed / span if span > 0 else 0.0
    stars = min(4, int(progress * 4))

    return {'level': level, 'name': name, 'stars': stars, 'next_at': next_at, 'progress': progress}


def award_quiz_points(student_id, session_id, score, occurred_at=None):
    """퀴즈 세션 채점 결과에 따라 QZ01(정답률 60% 이상)·QZ02(만점 보너스)를 적립한다.

    어휘퀴즈·스키마퀴즈 양쪽에서 이 함수 하나를 공통으로 호출한다(2단계 지시서 4.2절).
    정책상 "회차당 1회"이나 세션 모델에 회차 컬럼이 없어서, source_id를 세션 ID로 써서
    point_events의 유니크 제약이 "세션당 1회"를 강제하도록 한다.

    Returns:
        dict: {'QZ01': PointEvent|None, 'QZ02': PointEvent|None} - 조건을 만족하지 않아
             애초에 시도하지 않은 코드는 키 자체가 없음
    """
    results = {}
    if score is None:
        return results

    source_id = str(session_id)
    if score >= 60:
        results['QZ01'] = award_points(
            student_id=student_id, activity_code='QZ01',
            source_type='quiz_session', source_id=source_id,
            occurred_at=occurred_at,
        )
    if score >= 100:
        results['QZ02'] = award_points(
            student_id=student_id, activity_code='QZ02',
            source_type='quiz_session', source_id=source_id,
            occurred_at=occurred_at,
        )
    return results
