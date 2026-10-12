# -*- coding: utf-8 -*-
"""헤르메스(관리자 전용 자연어 명령 에이전트) 라우트.

확인 게이트 없이 자연어 지시를 바로 실행한다 - CLAUDE.md "안전 원칙" 섹션의
의도적 예외(2026-10-12 사용자 승인). master_admin 전용으로 시작한다(결석 처리가
학생 출결/시수 집계에 영향을 주고, 확인 게이트가 없는 유일한 화면이라 가장
높은 권한으로 시작 - 나중에 신뢰가 쌓이면 낮출 수 있음).

기존 admin/routes.py가 이미 3900줄+로 커서, 새로 만드는 민감한 기능은 이
파일로 분리해 리뷰/롤백을 쉽게 한다."""
import json
import uuid
from datetime import date, datetime, timedelta

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.models import db, HermesCommandLog
from app.utils.decorators import requires_permission_level

_HERMES_LLM_HOURLY_LIMIT = 30


def _hermes_llm_rate_limited():
    from app.models.api_usage_log import ApiUsageLog
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_calls = ApiUsageLog.query.filter(
        ApiUsageLog.user_id == current_user.user_id,
        ApiUsageLog.usage_type == 'hermes_parse',
        ApiUsageLog.created_at >= one_hour_ago,
    ).count()
    return recent_calls >= _HERMES_LLM_HOURLY_LIMIT


def _log_hermes_llm_usage(usage):
    from app.models.api_usage_log import ApiUsageLog
    if not usage:
        return
    db.session.add(ApiUsageLog(
        user_id=current_user.user_id,
        api_type='claude',
        model_name='claude-sonnet-4-6',
        usage_type='hermes_parse',
        input_tokens=usage['input_tokens'],
        output_tokens=usage['output_tokens'],
        cost_usd=ApiUsageLog.calc_claude_cost(usage['input_tokens'], usage['output_tokens']),
    ))


def _open_clarification(thread_id):
    """같은 thread_id에 아직 답을 못 받은 명확화 질문이 있으면 그 로그를 반환한다."""
    return (
        HermesCommandLog.query
        .filter_by(thread_id=thread_id, status='needs_clarification')
        .order_by(HermesCommandLog.created_at.desc())
        .first()
    )


def _write_log(**kwargs):
    log = HermesCommandLog(log_id=str(uuid.uuid4()), **kwargs)
    db.session.add(log)
    db.session.commit()
    return log


@admin_bp.route('/hermes')
@login_required
@requires_permission_level(1)
def hermes():
    """헤르메스 대화 화면 - 최근 명령 50건을 transcript로 보여준다."""
    recent_logs = (
        HermesCommandLog.query
        .order_by(HermesCommandLog.created_at.asc())
        .limit(50)
        .all()
    )
    return render_template('admin/hermes.html', recent_logs=recent_logs)


@admin_bp.route('/hermes/message', methods=['POST'])
@login_required
@requires_permission_level(1)
def hermes_message():
    """자연어 명령 한 턴을 처리한다 - 파싱 → 엔티티 해석 → (모호하면 재질문,
    아니면) 즉시 실행 + 알림 발송. 모든 결과를 HermesCommandLog에 남긴다."""
    from app.utils.hermes_agent import parse_hermes_command
    from app.utils.hermes_resolver import (
        resolve_course_for_student, resolve_student,
    )

    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    thread_id = body.get('thread_id') or str(uuid.uuid4())

    if not text:
        return jsonify({'error': '메시지를 입력해주세요.'}), 400

    # 같은 thread에 미답변 명확화 질문이 있으면, 이번 입력은 그 답이다 -
    # 원문 지시 + 답변을 합쳐서 다시 해석한다(이 코드베이스엔 LLM 호출
    # "이어가기" 기능이 없어 텍스트를 합치는 방식을 쓴다).
    pending = _open_clarification(thread_id)
    effective_text = f'{pending.raw_text}\n(추가 설명: {text})' if pending else text

    if _hermes_llm_rate_limited():
        log = _write_log(
            thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
            status='failed', error_detail='잠시 후 다시 시도해 주세요(요청이 너무 잦습니다).',
        )
        return jsonify({'reply_text': log.error_detail, 'status': 'failed',
                        'log_id': log.log_id, 'thread_id': thread_id})

    parsed = parse_hermes_command(effective_text, today=date.today())
    usage = parsed.pop('_usage', None)
    try:
        _log_hermes_llm_usage(usage)
        db.session.commit()
    except Exception:
        from flask import current_app
        current_app.logger.exception('[admin.hermes_message] 사용량 로그 저장 실패')

    if parsed['action_type'] == 'unrecognized':
        question = parsed.get('unclear_reason') or '무엇을 해야 할지 이해하지 못했습니다. 다시 말씀해 주시겠어요?'
        log = _write_log(
            thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
            parsed_action=json.dumps(parsed, ensure_ascii=False),
            action_type='unrecognized', status='needs_clarification',
            clarification_question=question,
        )
        return jsonify({'reply_text': question, 'status': 'needs_clarification',
                        'log_id': log.log_id, 'thread_id': thread_id})

    student, student_candidates = resolve_student(parsed.get('student_name'))
    if student is None:
        if student_candidates:
            listing = ', '.join(f"{s.name}({s.grade or '학년 미상'}, {s.school or '학교 미상'})"
                                for s in student_candidates)
            question = f"이름이 같은 학생이 여러 명입니다: {listing}. 어느 학생인지 학년이나 학교로 알려주세요."
        else:
            question = f"이름이 '{parsed.get('student_name') or ''}'인 학생을 찾을 수 없습니다. 정확한 이름을 알려주세요."
        log = _write_log(
            thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
            parsed_action=json.dumps(parsed, ensure_ascii=False),
            action_type=parsed['action_type'], status='needs_clarification',
            clarification_question=question,
        )
        return jsonify({'reply_text': question, 'status': 'needs_clarification',
                        'log_id': log.log_id, 'thread_id': thread_id})

    course, course_candidates = resolve_course_for_student(student, parsed.get('course_hint'))
    if course is None:
        if course_candidates:
            listing = ', '.join(c.course_name for c in course_candidates)
            question = f"{student.name} 학생이 수강 중인 수업이 여러 개입니다: {listing}. 어느 수업 기준인가요?"
        else:
            question = f"{student.name} 학생의 활성 수강 수업을 찾을 수 없습니다."
        log = _write_log(
            thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
            parsed_action=json.dumps(parsed, ensure_ascii=False),
            resolved_params=json.dumps({'student_id': student.student_id}, ensure_ascii=False),
            action_type=parsed['action_type'], status='needs_clarification',
            clarification_question=question,
        )
        return jsonify({'reply_text': question, 'status': 'needs_clarification',
                        'log_id': log.log_id, 'thread_id': thread_id})

    resolved_params = {'student_id': student.student_id, 'course_id': course.course_id,
                       'date': parsed.get('date'), 'time': parsed.get('time'),
                       'status': parsed.get('status')}

    if parsed['action_type'] == 'schedule_makeup':
        reply_text, status, entity = _run_schedule_makeup(student, course, parsed)
    else:
        reply_text, status, entity = _run_mark_absence(student, course, parsed)

    log = _write_log(
        thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
        parsed_action=json.dumps(parsed, ensure_ascii=False),
        resolved_params=json.dumps(resolved_params, ensure_ascii=False),
        action_type=parsed['action_type'], status=status,
        result_summary=reply_text if status == 'success' else None,
        error_detail=reply_text if status == 'failed' else None,
        clarification_question=reply_text if status == 'needs_clarification' else None,
        related_entity_type=entity[0] if entity else None,
        related_entity_id=entity[1] if entity else None,
        resolved_at=datetime.utcnow() if status != 'needs_clarification' else None,
    )
    return jsonify({'reply_text': reply_text, 'status': status,
                    'log_id': log.log_id, 'thread_id': thread_id})


def _run_schedule_makeup(student, source_course, parsed):
    """(reply_text, status, (entity_type, entity_id) 또는 None) 반환."""
    from app.utils.hermes_actions import execute_schedule_makeup

    date_str = parsed.get('date')
    if not date_str:
        return (f'{student.name} 학생의 보강 날짜를 알려주세요.', 'needs_clarification', None)
    try:
        makeup_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return (f"날짜 '{date_str}'를 이해하지 못했습니다. YYYY-MM-DD로 다시 알려주세요.",
                'needs_clarification', None)

    time_str = parsed.get('time')
    makeup_time = None
    if time_str:
        try:
            makeup_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return (f"시간 '{time_str}'을 이해하지 못했습니다. HH:MM로 다시 알려주세요.",
                    'needs_clarification', None)

    try:
        makeup_course = execute_schedule_makeup(
            student, source_course, makeup_date, makeup_time=makeup_time,
            created_by=current_user.user_id,
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_message] 보강 일정 생성 실패')
        return (f'보강 일정 생성 중 오류가 발생했습니다: {e}', 'failed', None)

    when = makeup_date.strftime('%m/%d')
    if makeup_time:
        when += f' {makeup_time.strftime("%H:%M")}'
    reply = f'{student.name} 학생 보강 수업을 생성했습니다: {when}, {source_course.course_name} 기준. 학부모와 강사에게 알림을 보냈습니다.'
    return (reply, 'success', ('course', makeup_course.course_id))


_STATUS_LABEL = {'absent': '결석', 'absent_makeup': '결석(보강 처리)', 'late': '지각', 'excused': '인정결석'}


def _run_mark_absence(student, course, parsed):
    """(reply_text, status, (entity_type, entity_id) 또는 None) 반환.

    오늘/과거 날짜만 처리한다(app/utils/hermes_resolver.resolve_session_for_date로
    그 수업의 해당 날짜 세션을 찾아야 함). 미래 날짜("내일 결석 예정" 같은
    사전 예고)는 아직 지원하지 않는다 - Attendance 레코드가 미래 세션에는
    아예 안 생기는 기존 설계(app/utils/course_utils.py) 때문에 별도
    AbsenceNotice 경로가 필요하고, 그 설계는 사용자 확인 후 다음 단계로
    추가한다."""
    from app.utils.hermes_actions import HermesActionError, execute_mark_absence
    from app.utils.hermes_resolver import resolve_session_for_date

    date_str = parsed.get('date')
    status = parsed.get('status')
    if not date_str:
        return (f'{student.name} 학생의 날짜를 알려주세요.', 'needs_clarification', None)
    if not status:
        return (f'{student.name} 학생을 결석/지각/인정결석 중 어떤 상태로 처리할까요?',
                'needs_clarification', None)
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return (f"날짜 '{date_str}'를 이해하지 못했습니다. YYYY-MM-DD로 다시 알려주세요.",
                'needs_clarification', None)

    if target_date > date.today():
        return _run_mark_absence_future(student, course, target_date, status, parsed.get('reason'))

    session = resolve_session_for_date(course, target_date)
    if session is None:
        return (
            f'{course.course_name}에 {target_date.strftime("%m/%d")} 세션을 찾을 수 없습니다. '
            f'날짜를 다시 확인해 주세요.',
            'needs_clarification', None,
        )

    try:
        result = execute_mark_absence(
            student, course, session, status,
            reason=parsed.get('reason'), checked_by=current_user.user_id,
        )
    except HermesActionError as e:
        return (str(e), 'needs_clarification', None)
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_message] 결석 처리 실패')
        return (f'결석 처리 중 오류가 발생했습니다: {e}', 'failed', None)

    label = _STATUS_LABEL.get(result['final_status'], result['final_status'])
    reply = f'{student.name} 학생을 {target_date.strftime("%m/%d")} {course.course_name} 수업에서 {label} 처리했습니다.'
    if result['converted_to_makeup']:
        reply += ' (다른 보강 수업에 참여 중이라 결석(보강 처리)으로 자동 전환됨)'
    if result['notified_parent_ids']:
        reply += ' 학부모에게 알림을 보냈습니다.'
    return (reply, 'success', ('attendance', result['attendance'].attendance_id))


def _run_mark_absence_future(student, course, target_date, status, reason):
    """(reply_text, status, (entity_type, entity_id) 또는 None) 반환.

    미래 날짜는 Attendance 레코드가 아직 없어(세션 출결 체크 시점에 생성됨,
    app/utils/course_utils.py) 기존 "결석 예고"(AbsenceNotice) 기능과 같은
    개념으로 처리한다 - 사용자 확인 후 채택(2026-10-12)."""
    from app.utils.absence_utils import create_absence_notice_with_notification

    if status not in ('absent', 'late'):
        return (
            '인정결석(excused)은 출결 체크 시점에 교사가 판단하는 항목이라 '
            '미래 날짜로 미리 지정할 수 없습니다. 결석 또는 지각으로 다시 알려주세요.',
            'needs_clarification', None,
        )
    if not reason:
        return (f'{student.name} 학생이 {target_date.strftime("%m/%d")} 결석/지각하는 사유를 알려주세요.',
                'needs_clarification', None)

    try:
        notice = create_absence_notice_with_notification(
            student, course, target_date, reason, notice_type=status,
            created_by=current_user.user_id, created_by_role='admin',
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_message] 결석 예고 생성 실패')
        return (f'결석 예고 생성 중 오류가 발생했습니다: {e}', 'failed', None)

    label = _STATUS_LABEL.get(status, status)
    reply = (f'{student.name} 학생의 {target_date.strftime("%m/%d")} {course.course_name} {label} 예고를 '
             f'등록했습니다. 담당 강사에게 알림을 보냈습니다.')
    return (reply, 'success', ('absence_notice', notice.notice_id))
