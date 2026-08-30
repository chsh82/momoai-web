# -*- coding: utf-8 -*-
"""뱃지 판정 엔진 (정책 제8조)

badges.rule_type별 판정 방식:
  first_event      해당 활동 코드의 confirmed 적립이 1건 이상 (BG01~BG06)
                   단, BG01("최초 게시글 작성")은 point_events가 아니라 실제
                   Post 테이블을 직접 본다 - 게시글 작성 자체는 점수를 안 주는
                   활동이라(QS01은 질문 카테고리에 한정) point_events로는
                   "게시글을 썼다"는 사실 자체를 못 잡기 때문이다.
  external_metric  받은 좋아요/댓글 수 집계 (BG07)
  count_threshold  분기 완주(AT02) 누적 건수 (BG08)
  manual           관리자 수여만 (BG09) - 자동 판정 대상 아님
  all_badges       지정된 뱃지 전부 보유 (BG10)

호출 시점 두 가지:
  - 포인트 적립 직후: evaluate_badges(student_id, trigger_codes=[...]) 즉시 반응
  - 매일 새벽 배치: run_badge_sweep()으로 전체 학생 검사(누락 보정용)
"""
import json
import logging
from datetime import datetime

from sqlalchemy import func

from app.models import db
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.community import Post, Comment, PostLike
from app.models.essay import Essay
from app.models.mileage import Badge, StudentBadge, PointEvent
from app.models.notification import Notification
from app.services.mileage_rules import BADGE_EMOJI_FALLBACK, MILEAGE_START_DATETIME_UTC

logger = logging.getLogger(__name__)


def _load_config(badge):
    return json.loads(badge.rule_config) if badge.rule_config else {}


def _first_event_count(student_id, config):
    """activity_code가 있으면 point_events를, source_type만 있으면(BG01) 실제
    콘텐츠 테이블을 직접 센다."""
    activity_code = config.get('activity_code')
    if activity_code:
        return PointEvent.query.filter_by(
            student_id=student_id, activity_code=activity_code,
            entry_type='award', status='confirmed',
        ).count()

    source_type = config.get('source_type')
    if source_type == 'post':
        student = Student.query.get(student_id)
        if not student or not student.user_id:
            return 0  # 학생 계정 미연결 - 판정 불가(0건 취급)
        return Post.query.filter_by(user_id=student.user_id).count()

    if source_type == 'essay':
        # BG01(전체 유형)/BG03(리라이팅) - point_events가 아니라 essays
        # 테이블을 직접 본다. 첨삭 확정(포인트 지급) 전인 업로드 시점에도
        # 바로 판정할 수 있어야 하고, BG01은 마일리지 시작일 게이트와
        # 무관하게(2026-08-29 결정사항) 기존에 쌓인 과제에도 소급 적용된다.
        query = Essay.query.filter_by(student_id=student_id)
        essay_type = config.get('essay_type')
        if essay_type:
            query = query.filter_by(essay_type=essay_type)
        return query.count()

    return 0


def _received_likes_count(student):
    # BG07은 마일리지 시작일(2026-09-01, KST) 이후 받은 좋아요만 센다
    # (2026-08-29 결정사항) - RW01/RW02와 마찬가지로 시작일 이전 활동은
    # 마일리지 체계 밖으로 취급한다.
    if not student.user_id:
        return 0
    return db.session.query(func.count(PostLike.post_id)).join(
        Post, Post.post_id == PostLike.post_id
    ).filter(
        Post.user_id == student.user_id,
        PostLike.user_id != student.user_id,
        PostLike.created_at >= MILEAGE_START_DATETIME_UTC,
    ).scalar() or 0


def _received_comments_count(student):
    if not student.user_id:
        return 0
    return db.session.query(func.count(Comment.comment_id)).join(
        Post, Post.post_id == Comment.post_id
    ).filter(
        Post.user_id == student.user_id,
        Comment.user_id != student.user_id,
        Comment.is_deleted == False,  # noqa: E712
        Comment.created_at >= MILEAGE_START_DATETIME_UTC,
    ).scalar() or 0


def _quarter_completed_count(student):
    return PointEvent.query.filter_by(
        student_id=student.student_id, activity_code='AT02',
        entry_type='award', status='confirmed',
    ).count()


_METRIC_FUNCS = {
    'received_likes': _received_likes_count,
    'received_comments': _received_comments_count,
    'quarter_completed': _quarter_completed_count,
}


def _metric_value(student, metric_name):
    func_ = _METRIC_FUNCS.get(metric_name)
    return func_(student) if func_ else 0


def _check_count_or_metric(student_id, config):
    """external_metric(BG07, or_metric 있음)과 count_threshold(BG08, 단일 지표)
    공통 처리. (충족 여부, 대표 수치) 반환."""
    student = Student.query.get(student_id)
    if not student:
        return False, 0

    primary = _metric_value(student, config['metric'])
    if primary >= config['threshold']:
        return True, primary

    if 'or_metric' in config:
        alt = _metric_value(student, config['or_metric'])
        if alt >= config['or_threshold']:
            return True, alt
        return False, max(primary, alt)

    return False, primary


def _check_all_badges(config, owned_codes):
    required = config.get('required_badges', [])
    return all(code in owned_codes for code in required), 1


def _notify_badge_earned(student_id, badge):
    student = Student.query.get(student_id)
    if not student:
        return

    if student.user_id:
        try:
            Notification.create_notification(
                user_id=student.user_id, notification_type='badge',
                title=f'뱃지 획득: {badge.name}',
                message=badge.description,
                related_entity_type='badge', related_entity_id=badge.badge_code,
            )
        except Exception:
            logger.exception('뱃지 알림 발송 실패(학생, badge=%s)', badge.badge_code)

    # 학부모에게도 알림 - app/essays/routes.py의 ParentStudent 조회 패턴을 따른다
    try:
        links = ParentStudent.query.filter_by(student_id=student_id, is_active=True).all()
        for link in links:
            Notification.create_notification(
                user_id=link.parent_id, notification_type='badge',
                title=f'{student.name} 학생이 뱃지를 획득했습니다: {badge.name}',
                message=badge.description,
                related_entity_type='badge', related_entity_id=badge.badge_code,
            )
    except Exception:
        logger.exception('뱃지 알림 발송 실패(학부모, badge=%s)', badge.badge_code)


def _create_student_badge(student_id, badge, earned_count=1, granted_by=None, notify=True, memo=None):
    now = datetime.utcnow()
    sb = StudentBadge(
        student_id=student_id, badge_code=badge.badge_code, earned_count=earned_count,
        first_earned_at=now, last_earned_at=now, granted_by=granted_by, memo=memo,
    )
    db.session.add(sb)
    db.session.flush()
    if notify:
        _notify_badge_earned(student_id, badge)
    return sb


def evaluate_badges(student_id, trigger_codes=None, dry_run=False, notify=True):
    """해당 학생의 미획득 뱃지 조건을 검사해 충족분을 부여한다.

    trigger_codes를 주면 first_event 계열 중 무관한 코드는 건너뛰어 배치
    호출 시 불필요한 쿼리를 줄인다(선택적 최적화 - 결과는 생략해도 동일).

    notify=False로 호출하면 이번 호출에서 새로 부여되는 뱃지에 한해
    알림을 보내지 않는다 - BG01처럼 essay_type 기능 도입으로 기존 데이터에
    소급 적용되는 조건 변경을 배치로 반영할 때, 재원생 전체에게 한꺼번에
    알림이 발송되는 것을 막기 위한 용도다(scripts/backfill_bg01_badge.py
    전용, 2026-08-29 결정사항). 평소 실시간 트리거/야간 배치는 기본값(True)을
    그대로 쓴다.

    Returns:
        list: dry_run=False면 부여/갱신된 StudentBadge 목록,
             dry_run=True면 {'badge_code','name','action'} 딕셔너리 목록(미리보기)
    """
    granted = []
    badges = Badge.query.filter_by(is_active=True).order_by(Badge.sort_order).all()
    owned = {sb.badge_code: sb for sb in StudentBadge.query.filter_by(student_id=student_id).all()}
    owned_codes = set(owned.keys())

    for badge in badges:
        if badge.badge_code in owned and not badge.is_repeatable:
            continue

        config = _load_config(badge)

        if badge.rule_type == 'manual':
            continue
        elif badge.rule_type == 'first_event':
            if trigger_codes is not None:
                badge_code_hint = config.get('activity_code') or config.get('source_type')
                if badge_code_hint and badge_code_hint not in trigger_codes:
                    continue
            count = _first_event_count(student_id, config)
            met, value = count > 0, count
        elif badge.rule_type in ('external_metric', 'count_threshold'):
            met, value = _check_count_or_metric(student_id, config)
        elif badge.rule_type == 'all_badges':
            met, value = _check_all_badges(config, owned_codes)
        else:
            continue

        if not met:
            continue

        existing = owned.get(badge.badge_code)
        new_count = value if badge.is_repeatable else 1

        if existing is None:
            if dry_run:
                granted.append({'badge_code': badge.badge_code, 'name': badge.name,
                               'action': f'would_grant(x{new_count})'})
            else:
                sb = _create_student_badge(student_id, badge, earned_count=new_count, notify=notify)
                granted.append(sb)
                owned[badge.badge_code] = sb
                owned_codes.add(badge.badge_code)
        elif badge.is_repeatable and new_count > existing.earned_count:
            if dry_run:
                granted.append({'badge_code': badge.badge_code, 'name': badge.name,
                               'action': f'would_increment({existing.earned_count}->{new_count})'})
            else:
                existing.earned_count = new_count
                existing.last_earned_at = datetime.utcnow()
                if notify:
                    _notify_badge_earned(student_id, badge)
                granted.append(existing)

    return granted


def grant_badge(student_id, badge_code, granted_by=None, memo=None, notify=True):
    """수동 수여. 반복 가능 뱃지는 earned_count를 늘린다.

    memo는 BG09(장원) 등 "어느 회차에 대한 수여인지" 근거가 필요한 뱃지에 쓴다
    (4단계 지시서 E항 "회차 정보를 메모로 입력받는다"). 반복 수여 시에는 가장
    최근 memo로 덮어쓴다 - 과거 회차 이력까지 누적해서 남기는 요구사항은 아니었음.

    notify=False는 evaluate_badges()와 동일하게 소급 일괄 수여 시 알림을
    끄는 용도다(2026-08-29 결정사항) - 이 함수는 관리자 수동 수여(BG09 등)
    경로라 평소에는 거의 항상 기본값(True)을 쓴다.
    """
    badge = Badge.query.get(badge_code)
    if not badge:
        raise ValueError(f"알 수 없는 뱃지 코드: {badge_code}")

    existing = StudentBadge.query.filter_by(student_id=student_id, badge_code=badge_code).first()
    if existing:
        if not badge.is_repeatable:
            return None
        existing.earned_count += 1
        existing.last_earned_at = datetime.utcnow()
        if granted_by:
            existing.granted_by = granted_by
        if memo:
            existing.memo = memo
        db.session.flush()
        if notify:
            _notify_badge_earned(student_id, badge)
        result = existing
    else:
        result = _create_student_badge(student_id, badge, earned_count=1, granted_by=granted_by,
                                       memo=memo, notify=notify)

    _check_and_grant_bg10(student_id)
    return result


def revoke_badge(student_id, badge_code, reason):
    sb = StudentBadge.query.filter_by(student_id=student_id, badge_code=badge_code).first()
    if not sb:
        return False
    sb.revoked_at = datetime.utcnow()
    db.session.flush()
    return True


def _check_and_grant_bg10(student_id):
    """BG10은 다른 뱃지가 부여될 때마다 함께 검사한다(정책 8.2.7).
    evaluate_badges()는 sort_order 순회로 이미 자연스럽게 이 검사를 포함하지만,
    grant_badge()의 수동 수여 경로는 별도 루프를 안 타므로 여기서 직접 확인한다.
    """
    bg10 = Badge.query.get('BG10')
    if not bg10 or bg10.rule_type != 'all_badges':
        return None
    if StudentBadge.query.filter_by(student_id=student_id, badge_code='BG10').first():
        return None
    owned_codes = {sb.badge_code for sb in StudentBadge.query.filter_by(student_id=student_id).all()}
    config = _load_config(bg10)
    met, _ = _check_all_badges(config, owned_codes)
    if met:
        return _create_student_badge(student_id, bg10, earned_count=1)
    return None


def _badge_progress(student_id, student, badge, config, owned_codes):
    """뱃지 하나의 미획득 상태 진행도(0.0~1.0)와 안내 문구를 계산한다.
    3×3 수집판에서 잠긴 칸에 "달성 조건 + 진행도"를 보여주기 위한 것(4단계
    화면 지시서 1항) - evaluate_badges()의 판정 로직과 별개로 표시용으로만 쓴다."""
    if badge.rule_type == 'manual':
        return 0.0, badge.description
    if badge.rule_type == 'all_badges':
        required = config.get('required_badges', [])
        have = sum(1 for c in required if c in owned_codes)
        total = len(required) or 1
        return have / total, f'{badge.description} ({have}/{total})'
    if badge.rule_type == 'first_event':
        count = _first_event_count(student_id, config)
        return (1.0 if count > 0 else 0.0), badge.description
    if badge.rule_type in ('external_metric', 'count_threshold'):
        primary = _metric_value(student, config['metric'])
        best_ratio = primary / config['threshold'] if config['threshold'] else 0.0
        best_value, threshold = primary, config['threshold']
        if 'or_metric' in config:
            alt = _metric_value(student, config['or_metric'])
            alt_ratio = alt / config['or_threshold'] if config['or_threshold'] else 0.0
            if alt_ratio > best_ratio:
                best_ratio, best_value, threshold = alt_ratio, alt, config['or_threshold']
        return min(1.0, best_ratio), f'{badge.description} ({best_value}/{threshold})'
    return 0.0, badge.description


def get_badge_board(student_id):
    """마이페이지 3×3 수집판에 쓸 뱃지 전체 목록(획득/미획득 공통 표시용).

    Returns:
        list[dict]: sort_order 순. 각 항목:
            {badge_code, name, description, category, icon, is_final,
             is_repeatable, owned, earned_count, first_earned_at,
             progress(0.0~1.0), progress_label}
    """
    student = Student.query.get(student_id)
    badges = Badge.query.filter_by(is_active=True).order_by(Badge.sort_order).all()
    owned = {sb.badge_code: sb for sb in StudentBadge.query.filter_by(student_id=student_id).all()
             if sb.revoked_at is None}
    owned_codes = set(owned.keys())

    board = []
    for badge in badges:
        config = _load_config(badge)
        sb = owned.get(badge.badge_code)
        if sb:
            progress, label = 1.0, badge.description
        elif student is None:
            progress, label = 0.0, badge.description
        else:
            progress, label = _badge_progress(student_id, student, badge, config, owned_codes)

        board.append({
            'badge_code': badge.badge_code,
            'name': badge.name,
            'description': badge.description,
            'category': badge.category,
            'icon_path': badge.icon_path,
            'icon_emoji': BADGE_EMOJI_FALLBACK.get(badge.badge_code, '🏅'),
            'is_final': badge.rule_type == 'all_badges',
            'is_repeatable': badge.is_repeatable,
            'owned': sb is not None,
            'earned_count': sb.earned_count if sb else 0,
            'first_earned_at': sb.first_earned_at if sb else None,
            'progress': progress,
            'progress_label': label,
        })
    return board


def run_badge_sweep(dry_run=False, notify=True):
    """매일 새벽 배치 - 전체 활성 학생을 검사한다(누락 보정용).

    학생 수 증가를 감안해 yield_per로 스트리밍 처리한다(전체를 한 번에 메모리에 안 올림).
    notify는 evaluate_badges()에 그대로 전달한다 - 평소 야간 배치는 기본값(True)
    그대로 두고, 알림을 꺼야 하는 일회성 소급 반영은 이 함수 대신
    scripts/backfill_bg01_badge.py처럼 trigger_codes로 범위를 좁힌 별도
    스크립트를 쓴다(전체 학생·전체 뱃지를 한 번에 침묵시키는 것은 의도와 다름).
    """
    results = []
    for student in Student.query.filter_by(status='active').yield_per(200):
        try:
            granted = evaluate_badges(student.student_id, dry_run=dry_run, notify=notify)
            if granted:
                results.append({'student_id': student.student_id, 'name': student.name, 'granted': granted})
        except Exception:
            logger.exception('뱃지 스윕 개별 처리 실패 (student_id=%s)', student.student_id)
    return results
