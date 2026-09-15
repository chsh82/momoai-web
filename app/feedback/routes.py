# -*- coding: utf-8 -*-
"""수업 문자 자동 생성기 - Anthropic API 서버 프록시.

브라우저가 api.anthropic.com을 직접 부르면 API 키가 노출되므로, 서버가
키를 쥐고 대신 호출한다. 프롬프트 조립·검증 로직은 전부 프론트(JS)에
그대로 있고, 이 라우트는 순수 프록시 역할만 한다 - 프롬프트 본문이나
응답 본문은 어디에도 저장·로그하지 않는다(학생 개인정보 보호,
system-spec-v2.md §7.7 보안 점검표).

사용량 로그는 새 모델을 만들지 않고 기존 ApiUsageLog(essay 첨삭에서
쓰는 것과 동일 테이블, usage_type으로 구분)를 재사용한다 - 이미
강사별/기간별 집계용 admin 대시보드가 이 테이블 기준으로 있어서,
새 테이블을 또 만들면 그 집계에서 빠지고 중복 스키마만 늘어난다.
"""
from datetime import datetime, timedelta, date

import anthropic
from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from app.feedback import feedback_bp
from app.utils.decorators import requires_role
from app.models import db
from app.models.api_usage_log import ApiUsageLog
from app.models.course import Course, CourseEnrollment
from app.models.student import Student
from app.models.sms_session import SmsSession, SmsMessage
from config import Config

MODEL_NAME = 'claude-sonnet-4-6'
DEFAULT_MAX_TOKENS = 1500
MAX_PROMPT_LEN = 60_000
HOURLY_LIMIT_PER_TEACHER = 100
USAGE_TYPE = 'teacher_feedback'

# essays/routes.py의 하크니스 모델 게이트(_Course.course_type.in_(['하크니스',
# '시그니처']))와 동일 기준 - "보강(하크니스)" 등 보강 하위유형은 기존 코드도
# 하크니스로 안 치므로 여기서도 안 넣는다(인원수 기반 그룹/1:1로 자연스럽게 분류됨).
HARKNESS_COURSE_TYPES = ('하크니스', '시그니처')


@feedback_bp.route('/teacher/class-sms')
@login_required
@requires_role('teacher', 'admin')
def feedback_index():
    """수업 문자 자동 생성 화면 (demo.html 이식, 독립 페이지).

    경로 주의: 명세서(step1-flask-proxy.md)는 /teacher/feedback을 제안했지만,
    app/teacher/routes.py에 이미 같은 경로(@teacher_bp.route('/feedback') ->
    /teacher/feedback)로 등록된 무관한 기존 기능("강사 피드백" 작성/열람,
    TeacherFeedback 모델)이 있어 그대로 쓰면 그 라우트가 이걸 가린다.
    그래서 겹치지 않는 /teacher/class-sms로 바꿨다.
    """
    return render_template('feedback/index.html')


@feedback_bp.route('/api/classes')
def api_classes():
    """로그인한 교사의 반 목록 (하드코딩 PRESETS 대체용).

    teacher 역할은 자기 담당 반만(Course.teacher_id 기준 - app/teacher/
    routes.py 대시보드 등에서 이미 쓰는 것과 동일한 필터), admin은 전체.
    JSON API이므로 /api/generate와 동일하게 미로그인/권한없음을 401/403
    JSON으로 직접 반환한다(@login_required의 302 리디렉션 대신).

    결석 여부와 무관하게 CourseEnrollment.status='active'인 학생 전원을
    roster에 담는다 - 결석은 별도 Attendance/CourseSession 레코드일 뿐
    수강(enrollment) 자체를 지우지 않으므로, 이 필터만으로 이미 "결석생
    포함 전원"이 된다.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role not in ('teacher', 'admin'):
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    query = Course.query.filter_by(status='active')
    if current_user.role == 'teacher':
        query = query.filter_by(teacher_id=current_user.user_id)
    courses = query.order_by(Course.course_name).all()

    result = []
    for course in courses:
        roster = [
            {'sid': e.student_id, 'name': e.student.name}
            for e in course.enrollments
            if e.status == 'active' and e.student
        ]
        if course.course_type in HARKNESS_COURSE_TYPES:
            ctype = '하크니스'
        else:
            ctype = '1:1' if len(roster) == 1 else '그룹'
        result.append({
            'id': course.course_id,
            'name': course.course_name,
            'type': ctype,
            'teacher': course.teacher.name if course.teacher else '',
            'roster': roster,
        })

    return jsonify(result)


@feedback_bp.route('/api/generate', methods=['POST'])
def generate():
    """Anthropic Messages API 프록시.

    요청: {"prompt": "<문자열>", "max_tokens": <선택>}
    응답: {"text": "<모델 응답>"} 또는 {"error": "<메시지>"}

    @login_required/@requires_role를 안 쓰고 직접 체크한다 - 그 데코레이터들은
    미인증 시 /auth/login으로 302 리디렉션하는데(브라우저 페이지 라우트 기준
    설계), 이 라우트는 fetch()로만 호출되는 JSON API라 명세서(step1-flask-
    proxy.md) 요구대로 401 JSON을 그대로 반환해야 한다.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role not in ('teacher', 'admin'):
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_calls = ApiUsageLog.query.filter(
        ApiUsageLog.user_id == current_user.user_id,
        ApiUsageLog.usage_type == USAGE_TYPE,
        ApiUsageLog.created_at >= one_hour_ago,
    ).count()
    if recent_calls >= HOURLY_LIMIT_PER_TEACHER:
        return jsonify({'error': '잠시 후 다시 시도해 주세요'}), 429

    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt')
    if not isinstance(prompt, str) or not prompt or len(prompt) > MAX_PROMPT_LEN:
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400

    max_tokens = data.get('max_tokens')
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        max_tokens = DEFAULT_MAX_TOKENS

    api_key = Config.ANTHROPIC_API_KEY
    if not api_key:
        current_app.logger.error('[feedback.generate] ANTHROPIC_API_KEY 미설정')
        return jsonify({'error': '생성에 실패했습니다'}), 500

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=max_tokens,
            timeout=120.0,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        message = getattr(e, 'message', None) or str(e)
        return jsonify({'error': message}), 502
    except Exception:
        # 학생 실명이 프롬프트 안에 있을 수 있어 예외 자체는 로그에 남기지 않는다.
        current_app.logger.error(
            '[feedback.generate] 생성 실패 (teacher_id=%s)', current_user.user_id)
        return jsonify({'error': '생성에 실패했습니다'}), 500

    text = ''.join(
        block.text for block in response.content if getattr(block, 'type', None) == 'text'
    )

    try:
        usage = response.usage
        input_tok = getattr(usage, 'input_tokens', 0)
        output_tok = getattr(usage, 'output_tokens', 0)
        log = ApiUsageLog(
            user_id=current_user.user_id,
            api_type='claude',
            model_name=MODEL_NAME,
            usage_type=USAGE_TYPE,
            input_tokens=input_tok,
            output_tokens=output_tok,
            cost_usd=ApiUsageLog.calc_claude_cost(input_tok, output_tok),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        current_app.logger.exception(
            '[feedback.generate] 사용량 로그 저장 실패 (teacher_id=%s)', current_user.user_id)

    return jsonify({'text': text})


@feedback_bp.route('/api/sessions', methods=['POST'])
def save_session():
    """교사가 화면에서 최종 확정한 수업 문자를 저장(또는 갱신)한다.

    저장 대상은 AI 원본이 아니라 요청 본문의 students[].body(교사가 화면에서
    최종 수정한 값)다 - 그게 이 함수의 유일한 책임이고, 검증은 프론트에서
    이미 끝났다고 가정한다. (course_id, class_date) 조합이 이미 있으면
    기존 회차의 메시지를 지우고 새로 넣는 "갱신"으로 처리한다(중복 회차가
    쌓이면 월간 집계가 틀어지므로).

    학생 이름·문자 본문은 의도적으로 DB에 저장하지만(학원 업무 기록),
    이 함수 어디에서도 print/logger에 본문·이름을 남기지 않는다 - 실패
    로그에도 session_id/course_id/학생 수만 남긴다.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role not in ('teacher', 'admin'):
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    data = request.get_json(silent=True) or {}
    course_id = data.get('course_id')
    class_date_raw = data.get('class_date')
    students = data.get('students')

    if not course_id or not class_date_raw:
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400
    if not isinstance(students, list) or not students:
        return jsonify({'error': '저장할 문자가 없습니다'}), 400

    try:
        class_date = date.fromisoformat(str(class_date_raw))
    except ValueError:
        return jsonify({'error': '수업일 형식이 올바르지 않습니다'}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '반을 찾을 수 없습니다'}), 400
    if current_user.role == 'teacher' and course.teacher_id != current_user.user_id:
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    # 이 반에 실제 재적(active)한 학생만 sid로 허용 - 남의 반 학생 sid를
    # 끼워 넣는 것을 막는다.
    enrolled_ids = {
        e.student_id for e in
        CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()
    }
    for s in students:
        sid = s.get('sid') if isinstance(s, dict) else None
        if not sid or sid not in enrolled_ids:
            return jsonify({'error': '이 반 학생이 아닌 대상이 포함되어 있습니다'}), 400
        if not isinstance(s.get('body'), str) or not s.get('body', '').strip():
            return jsonify({'error': '빈 문자가 포함되어 있습니다'}), 400

    try:
        existing = SmsSession.query.filter_by(course_id=course_id, class_date=class_date).first()
        updated = existing is not None

        if existing:
            sms_session = existing
            # cascade='all, delete-orphan'이 걸린 관계이므로 리스트를 비우면
            # 기존 SmsMessage가 실제로 삭제된다(유령 레코드 방지).
            sms_session.messages = []
            db.session.flush()
        else:
            sms_session = SmsSession(course_id=course_id)
            db.session.add(sms_session)

        sms_session.class_date = class_date
        sms_session.teacher_id = current_user.user_id
        sms_session.class_type = data.get('class_type')
        sms_session.book = data.get('book')
        sms_session.week = data.get('week')
        sms_session.raw_summary = data.get('raw_summary')
        sms_session.name_map = data.get('name_map') or []

        for s in students:
            student = Student.query.get(s['sid'])
            sms_session.messages.append(SmsMessage(
                student_id=s['sid'],
                student_name=(student.name if student else s.get('name', '')),
                body=s['body'],
                msg_type=s.get('msg_type'),
            ))

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            '[feedback.save_session] 저장 실패 (course_id=%s, class_date=%s, teacher_id=%s)',
            course_id, class_date_raw, current_user.user_id)
        return jsonify({'error': '저장에 실패했습니다'}), 500

    response = {'session_id': sms_session.sms_session_id, 'saved': len(students), 'updated': updated}
    if updated:
        response['message'] = f'{class_date.month}월 {class_date.day}일 회차를 갱신했습니다.'
    return jsonify(response)


@feedback_bp.route('/api/sessions/report', methods=['POST'])
def save_report():
    """수업 보고문(반 전체 1건)을 이미 저장된 회차에 붙인다(4단계).

    문자(SmsMessage) 저장과 별개의 작은 엔드포인트로 뒀다 - /api/sessions는
    students가 비면 400으로 거절하는데, 보고문만 따로 생성·저장하는
    흐름(문자를 먼저 저장해 둔 뒤 나중에 보고문만 붙이는 경우)에서는
    student 목록을 다시 보낼 이유가 없다. 회차가 아직 없으면 "먼저 이
    수업을 저장하세요"로 명확히 안내한다.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role not in ('teacher', 'admin'):
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    data = request.get_json(silent=True) or {}
    course_id = data.get('course_id')
    class_date_raw = data.get('class_date')
    report_body = data.get('report_body')

    if not course_id or not class_date_raw:
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400
    if not isinstance(report_body, str) or not report_body.strip():
        return jsonify({'error': '저장할 보고문이 없습니다'}), 400

    try:
        class_date = date.fromisoformat(str(class_date_raw))
    except ValueError:
        return jsonify({'error': '수업일 형식이 올바르지 않습니다'}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'error': '반을 찾을 수 없습니다'}), 400
    if current_user.role == 'teacher' and course.teacher_id != current_user.user_id:
        return jsonify({'error': '접근 권한이 없습니다'}), 403

    sms_session = SmsSession.query.filter_by(course_id=course_id, class_date=class_date).first()
    if not sms_session:
        return jsonify({'error': '먼저 이 수업을 저장하세요'}), 400

    try:
        sms_session.report_body = report_body
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            '[feedback.save_report] 보고문 저장 실패 (session_id=%s, teacher_id=%s)',
            sms_session.sms_session_id, current_user.user_id)
        return jsonify({'error': '저장에 실패했습니다'}), 500

    return jsonify({'session_id': sms_session.sms_session_id, 'saved': True})
