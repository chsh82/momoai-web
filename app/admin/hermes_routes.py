# -*- coding: utf-8 -*-
"""모모 에이전트(관리자 전용 자연어 명령 에이전트, 내부 코드명 헤르메스) 라우트.

CLAUDE.md의 표준 "확인 후 실행" 원칙을 그대로 따른다: 자연어 지시를 해석해
실행 계획을 세우고(schedule_makeup/mark_absence), **매니저가 확인 버튼을
눌러야 비로소 실행·발송**한다(2026-10-12, 실사용 피드백으로 무확인 실행
방식에서 전환).

권한 범위(2026-10-13, 강사 공유 추가): master_admin/manager/staff
(role_level 1~3)는 지금까지처럼 전체 학생/수업 범위를 그대로 본다. teacher
(role_level 4)는 **본인이 담당하는 수업에 등록된 학생으로만 범위가 좁혀진다**
(`_teacher_scope_id()` - app/utils/hermes_resolver.py의 resolve_student/
resolve_course_for_student가 이 scope로 필터링). 보강을 다른 강사에게
위임(`teacher_name` 지정)하는 건 관리자만 가능 - 강사가 남의 시간을 동의
없이 커밋하는 걸 막기 위함(사용자 확인, 2026-10-13).

기존 admin/routes.py가 이미 3900줄+로 커서, 새로 만드는 민감한 기능은 이
파일로 분리해 리뷰/롤백을 쉽게 한다.

상태 흐름: 파싱 → (액션별) 엔티티 해석+필드 검증(모호하면 needs_clarification,
답변을 받아 재시도) → 전부 통과하면 실행 대신 미리보기 생성 +
pending_confirmation 저장 → 매니저가 확인(`/confirm`)하면 그제서야 실행,
취소(`/cancel`)하면 아무 것도 안 하고 끝. 복합 명령(한 문장에 여러 액션)은
한 thread_id 아래 pending_confirmation 로그를 액션 수만큼 쌓아두고,
확인/취소도 그 thread의 pending 전부에 한 번에 적용한다 - 검증 전부 통과한
뒤에야 확인 대기 상태가 되므로, 재질문/재입력으로 인한 중복 실행 위험이
애초에 없다(확인 전엔 실행 자체가 안 일어남)."""
import json
import uuid
from datetime import date, datetime, timedelta

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.models import db, HermesCommandLog
from app.utils.decorators import requires_permission_level

_HERMES_LLM_HOURLY_LIMIT = 30
_STATUS_LABEL = {'absent': '결석', 'absent_makeup': '결석(보강 처리)', 'late': '지각', 'excused': '인정결석'}
_STATUS_DISPLAY_LABEL = {
    'needs_clarification': '답변 필요', 'pending_confirmation': '확인 대기',
    'success': '완료', 'failed': '실패', 'cancelled': '취소됨',
}


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


def _teacher_scope_id():
    """None이면 전체 범위(master_admin/manager/staff, role_level 1~3) - 지금까지
    처럼 모든 학생/수업을 본다. 그 외(teacher, role_level 4)는 current_user.user_id를
    돌려줘서 본인이 담당하는 수업에 등록된 학생으로만 조회 범위를 좁힌다
    (2026-10-13 강사 공유 추가, 사용자 확인)."""
    return None if current_user.role_level <= 3 else current_user.user_id


def _respond_clarification(thread_id, raw_text, actions, question, clarification=None):
    """clarification이 주어지면({'type': 'course_choice', 'options': [...]} 또는
    {'type': 'date'}) 프론트가 자유 텍스트 입력 대신 버튼/날짜 선택 UI를
    보여줄 수 있게 함께 내려준다(2026-10-13, "직관적으로 선택하게" 요청).
    resolved_params는 pending_confirmation 전용이 아니라 범용 JSON 저장칸이라
    needs_clarification 행에도 그대로 재사용한다 - thread 재조회 시에도 같은
    선택 UI를 복원하기 위함(hermes_thread_detail 참고)."""
    log = _write_log(
        thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=raw_text,
        parsed_action=json.dumps(actions, ensure_ascii=False),
        action_type=actions[0]['action_type'] if actions else None,
        status='needs_clarification', clarification_question=question,
        resolved_params=json.dumps(clarification, ensure_ascii=False) if clarification else None,
    )
    payload = {'reply_text': question, 'status': 'needs_clarification',
               'log_id': log.log_id, 'thread_id': thread_id}
    if clarification:
        payload['clarification'] = clarification
    return jsonify(payload)


@admin_bp.route('/hermes')
@login_required
@requires_permission_level(4)
def hermes():
    """모모 에이전트 대화 화면 - 슬랙처럼 왼쪽 스레드 목록 + 오른쪽 대화창인
    전용 페이지(2026-10-12, 좁은 팝업 대신 전환). 화면 자체는 빈 틀만
    내려주고, 스레드 목록/대화 내용은 전부 /hermes/threads, /hermes/thread/<id>
    JS fetch로 채운다(templates/admin/hermes.html 참고). 사이드바 메뉴와
    우측 하단 FAB 아이콘(templates/partials/momo_agent_widget.html) 둘 다
    이 라우트로 바로 연결된다."""
    return render_template('admin/hermes.html')


@admin_bp.route('/hermes/threads')
@login_required
@requires_permission_level(4)
def hermes_threads():
    """최근 스레드 목록(히스토리) - 팝업 위젯 홈 화면용."""
    logs = (
        HermesCommandLog.query
        .filter_by(admin_user_id=current_user.user_id)
        .order_by(HermesCommandLog.created_at.asc())
        .limit(2000)
        .all()
    )
    by_thread = {}
    for log in logs:
        by_thread.setdefault(log.thread_id, []).append(log)

    threads = []
    for thread_id, thread_logs in by_thread.items():
        first, last = thread_logs[0], thread_logs[-1]
        threads.append({
            'thread_id': thread_id,
            'preview': (first.raw_text or '')[:60],
            'status': last.status,
            'status_label': _STATUS_DISPLAY_LABEL.get(last.status, last.status),
            'time': last.created_at.strftime('%Y-%m-%d %H:%M') if last.created_at else '',
            '_ts': last.created_at or datetime.min,
        })
    threads.sort(key=lambda t: t['_ts'], reverse=True)
    for t in threads:
        del t['_ts']
    return jsonify({'threads': threads[:30]})


@admin_bp.route('/hermes/thread/<thread_id>')
@login_required
@requires_permission_level(4)
def hermes_thread_detail(thread_id):
    """한 스레드의 로그 전부(시간순) - 팝업 위젯의 대화 렌더링용."""
    logs = (
        HermesCommandLog.query
        .filter_by(thread_id=thread_id)
        .order_by(HermesCommandLog.created_at.asc())
        .all()
    )
    if not logs:
        return jsonify({'error': '스레드를 찾을 수 없습니다.'}), 404

    items = []
    for log in logs:
        item = {
            'log_id': log.log_id,
            'raw_text': log.raw_text,
            'status': log.status,
            'status_label': _STATUS_DISPLAY_LABEL.get(log.status, log.status),
            'agent_text': log.clarification_question or log.result_summary or log.error_detail,
            'action_type': log.action_type,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else '',
        }
        if log.status == 'needs_clarification' and log.resolved_params:
            item['clarification'] = json.loads(log.resolved_params)
        items.append(item)
    return jsonify({'thread_id': thread_id, 'items': items})


@admin_bp.route('/hermes/message', methods=['POST'])
@login_required
@requires_permission_level(4)
def hermes_message():
    """자연어 명령 한 턴을 처리한다 - 파싱 → (액션별) 엔티티 해석+필드 검증 →
    전부 통과하면 "실행"이 아니라 "미리보기 + 확인 대기"로 응답한다. 실제
    실행은 /hermes/thread/<id>/confirm이 담당."""
    from app.utils.hermes_agent import parse_hermes_command
    from app.utils.hermes_resolver import resolve_course_for_student, resolve_student

    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    thread_id = body.get('thread_id') or str(uuid.uuid4())

    if not text:
        return jsonify({'error': '메시지를 입력해주세요.'}), 400

    # 같은 thread에 미답변 명확화 질문이 있으면, 이번 입력은 그 답이다 -
    # 원문 지시 + 답변을 합쳐서 다시 해석한다(이 코드베이스엔 LLM 호출
    # "이어가기" 기능이 없어 텍스트를 합치는 방식을 쓴다). 확인 전엔 아무것도
    # 실행되지 않으므로 재파싱해도 중복 실행 위험이 없다.
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

    actions = parsed['actions']
    scope_id = _teacher_scope_id()

    # 1단계: 전부 검증(엔티티 해석 + 필드 검증)만 하고 아무것도 실행하지 않는다.
    plans = []
    for action in actions:
        if action['action_type'] == 'unrecognized':
            question = action.get('unclear_reason') or '무엇을 해야 할지 이해하지 못했습니다. 다시 말씀해 주시겠어요?'
            return _respond_clarification(thread_id, text, actions, question)

        student, student_candidates = resolve_student(action.get('student_name'), teacher_scope_id=scope_id)
        if student is None:
            if student_candidates:
                listing = ', '.join(f"{s.name}({s.grade or '학년 미상'}, {s.school or '학교 미상'})"
                                    for s in student_candidates)
                question = f"이름이 같은 학생이 여러 명입니다: {listing}. 어느 학생인지 학년이나 학교로 알려주세요."
            elif scope_id:
                question = f"'{action.get('student_name') or ''}' 학생은 선생님이 담당하는 수업에 등록되어 있지 않습니다."
            else:
                question = f"이름이 '{action.get('student_name') or ''}'인 학생을 찾을 수 없습니다. 정확한 이름을 알려주세요."
            return _respond_clarification(thread_id, text, actions, question)

        course, course_candidates = resolve_course_for_student(student, action.get('course_hint'), teacher_scope_id=scope_id)
        if course is None:
            clarification = None
            if course_candidates:
                listing = ', '.join(c.course_name for c in course_candidates)
                question = f"{student.name} 학생이 수강 중인 수업이 여러 개입니다: {listing}. 어느 수업 기준인가요?"
                clarification = {'type': 'course_choice', 'options': [
                    {'course_id': c.course_id, 'label': c.course_name} for c in course_candidates
                ]}
            elif scope_id:
                question = f"{student.name} 학생은 선생님이 담당하는 수업에 등록되어 있지 않습니다."
            else:
                question = f"{student.name} 학생의 활성 수강 수업을 찾을 수 없습니다."
            return _respond_clarification(thread_id, text, actions, question, clarification=clarification)

        if action['action_type'] == 'schedule_makeup':
            plan, error, clarification = _validate_schedule_makeup(action, teacher_scope_id=scope_id)
        else:
            plan, error, clarification = _validate_mark_absence(course, action)
        if error:
            return _respond_clarification(thread_id, text, actions, error, clarification=clarification)

        plans.append({'action': action, 'student': student, 'course': course, 'plan': plan})

    # 2단계: 전부 검증 통과 - 실행하지 않고 미리보기 + 확인 대기 로그만 남긴다.
    previews = []
    logs = []
    for p in plans:
        action_type = p['action']['action_type']
        if action_type == 'schedule_makeup':
            preview_text = _preview_schedule_makeup(p['student'], p['course'], p['plan'])
        else:
            preview_text = _preview_mark_absence(p['student'], p['course'], p['plan'])

        resolved_params = {
            'student_id': p['student'].student_id, 'course_id': p['course'].course_id,
            **_serialize_plan(action_type, p['plan']),
        }
        log = _write_log(
            thread_id=thread_id, admin_user_id=current_user.user_id, raw_text=text,
            parsed_action=json.dumps(p['action'], ensure_ascii=False),
            resolved_params=json.dumps(resolved_params, ensure_ascii=False),
            action_type=action_type, status='pending_confirmation',
            clarification_question=preview_text,
        )
        previews.append(preview_text)
        logs.append(log)

    combined = '\n'.join(previews) + '\n\n확인하시겠습니까?'
    return jsonify({'reply_text': combined, 'status': 'pending_confirmation',
                    'log_id': logs[-1].log_id if logs else None, 'thread_id': thread_id})


@admin_bp.route('/hermes/thread/<thread_id>/confirm', methods=['POST'])
@login_required
@requires_permission_level(4)
def hermes_thread_confirm(thread_id):
    """해당 thread의 pending_confirmation 로그 전부를 실제로 실행한다."""
    from app.models import Course, Student
    from app.utils.hermes_actions import HermesActionError

    pending_logs = (
        HermesCommandLog.query
        .filter_by(thread_id=thread_id, status='pending_confirmation')
        .order_by(HermesCommandLog.created_at.asc())
        .all()
    )
    if not pending_logs:
        return jsonify({'reply_text': '이미 처리됐거나 만료된 요청입니다.',
                        'status': 'failed', 'thread_id': thread_id})

    replies = []
    overall_status = 'success'
    for log in pending_logs:
        # 동시 확인 클릭(이중 클릭 등) 경합 방지 - 실행 직전에 아직
        # pending_confirmation인지 다시 확인한다.
        fresh = HermesCommandLog.query.filter_by(log_id=log.log_id, status='pending_confirmation').first()
        if fresh is None:
            continue

        params = json.loads(log.resolved_params or '{}')
        student = Student.query.get(params.get('student_id'))
        course = Course.query.get(params.get('course_id'))
        if not student or not course:
            log.status, log.error_detail = 'failed', '학생 또는 수업 정보를 더 이상 찾을 수 없습니다.'
            log.resolved_at = datetime.utcnow()
            db.session.commit()
            replies.append(log.error_detail)
            overall_status = 'failed'
            continue

        try:
            plan = _rehydrate_plan(log.action_type, params)
        except HermesActionError as e:
            log.status, log.error_detail = 'failed', str(e)
            log.resolved_at = datetime.utcnow()
            db.session.commit()
            replies.append(log.error_detail)
            overall_status = 'failed'
            continue

        if log.action_type == 'schedule_makeup':
            reply_text, status, entity = _execute_schedule_makeup(student, course, plan)
        else:
            reply_text, status, entity = _execute_mark_absence(student, course, plan)

        log.status = status
        log.result_summary = reply_text if status == 'success' else None
        log.error_detail = reply_text if status == 'failed' else None
        log.related_entity_type = entity[0] if entity else None
        log.related_entity_id = entity[1] if entity else None
        log.resolved_at = datetime.utcnow()
        db.session.commit()

        replies.append(reply_text)
        if status != 'success':
            overall_status = 'failed'

    return jsonify({'reply_text': '\n'.join(replies), 'status': overall_status, 'thread_id': thread_id})


@admin_bp.route('/hermes/thread/<thread_id>/cancel', methods=['POST'])
@login_required
@requires_permission_level(4)
def hermes_thread_cancel(thread_id):
    """해당 thread의 pending_confirmation 로그 전부를 취소한다 - 아무것도 실행하지 않는다."""
    pending_logs = HermesCommandLog.query.filter_by(thread_id=thread_id, status='pending_confirmation').all()
    if not pending_logs:
        return jsonify({'reply_text': '이미 처리됐거나 만료된 요청입니다.',
                        'status': 'failed', 'thread_id': thread_id})

    now = datetime.utcnow()
    for log in pending_logs:
        log.status = 'cancelled'
        log.result_summary = '관리자가 취소했습니다.'
        log.resolved_at = now
    db.session.commit()
    return jsonify({'reply_text': '취소했습니다.', 'status': 'cancelled', 'thread_id': thread_id})


def _serialize_plan(action_type, plan):
    """plan dict(날짜/시간/ORM 객체 포함)를 HermesCommandLog.resolved_params에
    저장할 수 있는 JSON-safe dict로 바꾼다. 확인 시점엔 재파싱 없이 이 값만
    가지고 _rehydrate_plan()으로 복원해서 실행한다."""
    if action_type == 'schedule_makeup':
        return {
            'makeup_date': plan['makeup_date'].isoformat(),
            'makeup_time': plan['makeup_time'].strftime('%H:%M') if plan['makeup_time'] else None,
            'teacher_id': plan['teacher'].user_id if plan['teacher'] else None,
        }
    data = {
        'branch': plan['branch'], 'target_date': plan['target_date'].isoformat(),
        'status': plan['status'], 'reason': plan['reason'],
    }
    if plan['branch'] == 'past':
        data['session_id'] = plan['session'].session_id
    return data


def _rehydrate_plan(action_type, params):
    """_serialize_plan의 역변환 - resolved_params(JSON)에서 실행 가능한 plan
    dict로 복원한다. 확인 시점에 참조 대상(강사/세션)이 이미 사라졌으면
    HermesActionError를 던진다(호출부가 failed로 처리)."""
    from app.models import CourseSession, User
    from app.utils.hermes_actions import HermesActionError

    if action_type == 'schedule_makeup':
        teacher = None
        if params.get('teacher_id'):
            teacher = User.query.get(params['teacher_id'])
            if teacher is None:
                raise HermesActionError('지정한 강사를 더 이상 찾을 수 없습니다.')
        return {
            'makeup_date': datetime.strptime(params['makeup_date'], '%Y-%m-%d').date(),
            'makeup_time': (datetime.strptime(params['makeup_time'], '%H:%M').time()
                           if params.get('makeup_time') else None),
            'teacher': teacher,
        }

    plan = {
        'branch': params['branch'], 'target_date': datetime.strptime(params['target_date'], '%Y-%m-%d').date(),
        'status': params['status'], 'reason': params.get('reason'),
    }
    if params['branch'] == 'past':
        session = CourseSession.query.get(params.get('session_id'))
        if session is None:
            raise HermesActionError('해당 세션을 더 이상 찾을 수 없습니다.')
        plan['session'] = session
    return plan


def _validate_schedule_makeup(action, teacher_scope_id=None):
    """(plan_dict, error_message, clarification) 반환. plan_dict가 None이면
    error_message가 채워진다. 아무것도 실행하지 않는다.

    teacher_scope_id가 주어지면(강사 본인) 다른 강사에게 보강을 위임하는
    기능(teacher_name)은 막는다 - 본인 동의 없이 남의 시간을 커밋하게 되는
    셈이라 관리자 전용으로 둔다(사용자 확인, 2026-10-13). 보강 날짜는 원
    정규 수업 일정에서 추론할 수 없는 값이라(원래 "보강"이 기존 시간과
    다른 새 슬롯을 잡는 것) _validate_mark_absence와 달리 날짜를 추측하지
    않고 빈 날짜 선택기만 띄운다."""
    from app.utils.hermes_resolver import resolve_teacher

    date_str = action.get('date')
    if not date_str:
        return None, '보강 날짜를 알려주세요.', {'type': 'date'}
    try:
        makeup_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None, f"날짜 '{date_str}'를 이해하지 못했습니다. YYYY-MM-DD로 다시 알려주세요.", None

    time_str = action.get('time')
    makeup_time = None
    if time_str:
        try:
            makeup_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return None, f"시간 '{time_str}'을 이해하지 못했습니다. HH:MM로 다시 알려주세요.", None

    teacher = None
    teacher_name = action.get('teacher_name')
    if teacher_name:
        if teacher_scope_id:
            return None, '다른 강사에게 보강을 맡기는 건 관리자만 할 수 있습니다. 관리자에게 요청해주세요.', None
        teacher, teacher_candidates = resolve_teacher(teacher_name)
        if teacher is None:
            if teacher_candidates:
                listing = ', '.join(t.name for t in teacher_candidates)
                return None, f"강사 이름이 같은 분이 여러 명입니다: {listing}. 누구인지 더 알려주세요.", None
            return None, f"'{teacher_name}' 강사를 찾을 수 없습니다. 정확한 이름을 알려주세요.", None

    return {'makeup_date': makeup_date, 'makeup_time': makeup_time, 'teacher': teacher}, None, None


def _preview_schedule_makeup(student, course, plan):
    when = plan['makeup_date'].strftime('%m/%d')
    if plan['makeup_time']:
        when += f' {plan["makeup_time"].strftime("%H:%M")}'
    teacher_note = f', {plan["teacher"].name} 강사 담당' if plan['teacher'] else ''
    return (f'{student.name} 학생 보강 수업을 {when}, {course.course_name} 기준{teacher_note}으로 '
            f'만들려고 합니다. 학부모와 강사에게 알림이 발송됩니다.')


def _execute_schedule_makeup(student, source_course, plan):
    """(reply_text, status, (entity_type, entity_id) 또는 None) 반환."""
    from app.utils.hermes_actions import execute_schedule_makeup

    try:
        makeup_course = execute_schedule_makeup(
            student, source_course, plan['makeup_date'], makeup_time=plan['makeup_time'],
            teacher=plan['teacher'], created_by=current_user.user_id,
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_thread_confirm] 보강 일정 생성 실패')
        return (f'보강 일정 생성 중 오류가 발생했습니다: {e}', 'failed', None)

    when = plan['makeup_date'].strftime('%m/%d')
    if plan['makeup_time']:
        when += f' {plan["makeup_time"].strftime("%H:%M")}'
    teacher_note = f', {plan["teacher"].name} 강사 담당' if plan['teacher'] else ''
    reply = (f'{student.name} 학생 보강 수업을 생성했습니다: {when}, {source_course.course_name} 기준'
             f'{teacher_note}. 학부모와 강사에게 알림을 보냈습니다.')
    return (reply, 'success', ('course', makeup_course.course_id))


def _suggest_absence_date(course):
    """"이번주 결석 예정"처럼 날짜를 아예 안 준 경우, 수업의 요일(course.weekday)
    기준으로 이번주 그 요일 날짜를 추정해 매니저에게 확인받을 수 있게 한다
    (빈 날짜 선택기를 띄워 사람이 직접 찾게 하는 대신 - 2026-10-13 사용자
    요청). 실제로 그 날짜에 CourseSession이 있는지까지 확인해서, 휴강/일정
    변경으로 세션이 없으면 추측하지 않고 None을 돌려준다 - 틀린 추측을
    확인 없이 내놓는 것보다 평범한 질문이 낫다."""
    from app.utils.hermes_resolver import resolve_session_for_date

    if course.weekday is None:
        return None
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    candidate = this_monday + timedelta(days=course.weekday)
    if resolve_session_for_date(course, candidate) is None:
        return None
    weekday_names = ['월', '화', '수', '목', '금', '토', '일']
    return candidate, f'{weekday_names[course.weekday]}요일'


def _validate_mark_absence(course, action):
    """(plan_dict, error_message, clarification) 반환. plan_dict가 None이면
    error_message가 채워진다. 아무것도 실행하지 않는다.

    plan_dict['branch']가 'past'면 Attendance 경로(session 포함), 'future'면
    결석 예고(AbsenceNotice) 경로다."""
    from app.utils.hermes_resolver import resolve_session_for_date

    date_str = action.get('date')
    status = action.get('status')
    if not date_str:
        suggestion = _suggest_absence_date(course)
        if suggestion:
            sug_date, sug_label = suggestion
            question = (f'{course.course_name}는 이번주 {sug_label}({sug_date.strftime("%m/%d")})에 수업이 있는데, '
                        f'그 수업 기준으로 결석 처리할까요? 다른 날짜면 아래에서 선택해주세요.')
            return None, question, {'type': 'date', 'suggested_date': sug_date.isoformat()}
        return None, '결석/지각 날짜를 알려주세요.', {'type': 'date'}
    if not status:
        return None, '결석/지각/인정결석 중 어떤 상태로 처리할까요?', None
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None, f"날짜 '{date_str}'를 이해하지 못했습니다. YYYY-MM-DD로 다시 알려주세요.", None

    reason = action.get('reason')

    if target_date > date.today():
        if status not in ('absent', 'late'):
            return None, ('인정결석(excused)은 출결 체크 시점에 교사가 판단하는 항목이라 '
                          '미래 날짜로 미리 지정할 수 없습니다. 결석 또는 지각으로 다시 알려주세요.'), None
        if not reason:
            return None, f'{target_date.strftime("%m/%d")} 결석/지각하는 사유를 알려주세요.', None
        return {'branch': 'future', 'target_date': target_date, 'status': status, 'reason': reason}, None, None

    session = resolve_session_for_date(course, target_date)
    if session is None:
        return None, (f'{course.course_name}에 {target_date.strftime("%m/%d")} 세션을 찾을 수 없습니다. '
                      f'날짜를 다시 확인해 주세요.'), None
    return {'branch': 'past', 'session': session, 'target_date': target_date, 'status': status, 'reason': reason}, None, None


def _preview_mark_absence(student, course, plan):
    label = _STATUS_LABEL.get(plan['status'], plan['status'])
    if plan['branch'] == 'future':
        return (f'{student.name} 학생의 {plan["target_date"].strftime("%m/%d")} {course.course_name} {label} 예고를 '
                f'등록하려고 합니다. 담당 강사에게 알림이 발송됩니다.')
    return (f'{student.name} 학생을 {plan["target_date"].strftime("%m/%d")} {course.course_name} 수업에서 {label}'
            f'(으)로 처리하려고 합니다. 학부모에게 알림이 발송될 수 있습니다.')


def _execute_mark_absence(student, course, plan):
    """(reply_text, status, (entity_type, entity_id) 또는 None) 반환."""
    if plan['branch'] == 'future':
        return _execute_mark_absence_future(student, course, plan)

    from app.utils.hermes_actions import HermesActionError, execute_mark_absence

    try:
        result = execute_mark_absence(
            student, course, plan['session'], plan['status'],
            reason=plan['reason'], checked_by=current_user.user_id,
        )
    except HermesActionError as e:
        return (str(e), 'failed', None)
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_thread_confirm] 결석 처리 실패')
        return (f'결석 처리 중 오류가 발생했습니다: {e}', 'failed', None)

    label = _STATUS_LABEL.get(result['final_status'], result['final_status'])
    reply = f'{student.name} 학생을 {plan["target_date"].strftime("%m/%d")} {course.course_name} 수업에서 {label} 처리했습니다.'
    if result['converted_to_makeup']:
        reply += ' (다른 보강 수업에 참여 중이라 결석(보강 처리)으로 자동 전환됨)'
    if result['notified_parent_ids']:
        reply += ' 학부모에게 알림을 보냈습니다.'
    return (reply, 'success', ('attendance', result['attendance'].attendance_id))


def _execute_mark_absence_future(student, course, plan):
    """미래 날짜는 Attendance 레코드가 아직 없어(세션 출결 체크 시점에 생성됨,
    app/utils/course_utils.py) 기존 "결석 예고"(AbsenceNotice) 기능과 같은
    개념으로 처리한다 - 사용자 확인 후 채택(2026-10-12)."""
    from app.utils.absence_utils import create_absence_notice_with_notification

    try:
        notice = create_absence_notice_with_notification(
            student, course, plan['target_date'], plan['reason'], notice_type=plan['status'],
            created_by=current_user.user_id, created_by_role='admin',
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.exception('[admin.hermes_thread_confirm] 결석 예고 생성 실패')
        return (f'결석 예고 생성 중 오류가 발생했습니다: {e}', 'failed', None)

    label = _STATUS_LABEL.get(plan['status'], plan['status'])
    reply = (f'{student.name} 학생의 {plan["target_date"].strftime("%m/%d")} {course.course_name} {label} 예고를 '
             f'등록했습니다. 담당 강사에게 알림을 보냈습니다.')
    return (reply, 'success', ('absence_notice', notice.notice_id))
