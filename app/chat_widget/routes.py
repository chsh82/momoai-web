# -*- coding: utf-8 -*-
"""학부모 대화 위젯 JSON API.

세 신청 유형(상담/보강/환불)을 하나의 시간순 타임라인으로 보여준다. 각
신청은 상태 변화(접수/확정/반려 등)를 "시스템 메시지"로 합성하고, 실제
주고받은 메시지(parent_conversation_id)를 그 사이에 끼워 넣어 하나의
대화처럼 보이게 한다 - 별도의 이벤트 로그 테이블을 새로 만들지 않고
기존 필드(status, created_at, responded_at 등)에서 매번 계산한다.
"""
import os
import uuid as _uuid
from datetime import datetime, timedelta

from flask import abort, current_app, jsonify, request, send_from_directory, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.chat_widget import chat_widget_bp
from app.models import db, User, Notification
from app.models.consultation_request import ConsultationRequest, CATEGORY_CHOICES
from app.models.refund_request import RefundRequest
from app.models.makeup_request import MakeupClassRequest
from app.models.conversation import Conversation, ConversationMessage
from app.models.parent_student import ParentStudent
from app.utils.decorators import requires_role

KST_FMT = '%Y-%m-%d %H:%M'

# app.messages._save_attachment와 같은 규칙(허용 확장자/저장 위치)을 그대로
# 따른다 - 다만 파일 서빙은 별도 라우트(attachment())로 둔다. 일반 메신저의
# download_attachment는 강사/관리자 전용이라 학부모(parent)가 못 본다.
_ALLOWED_ATTACHMENT_EXT = {'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'hwp'}
_IMAGE_EXT = {'jpg', 'jpeg', 'png', 'gif'}


def _save_attachment(file):
    if not file or not file.filename:
        return None, None
    ext = os.path.splitext(secure_filename(file.filename))[1].lstrip('.').lower()
    if ext not in _ALLOWED_ATTACHMENT_EXT:
        return None, None
    save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'dm_attachments')
    os.makedirs(save_dir, exist_ok=True)
    unique_name = f"{_uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(save_dir, unique_name))
    return f"dm_attachments/{unique_name}", file.filename


def _is_image(name):
    if not name:
        return False
    ext = os.path.splitext(name)[1].lstrip('.').lower()
    return ext in _IMAGE_EXT


def _my_children():
    relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, is_active=True
    ).all()
    return [pr.student for pr in relations if pr.student]


def _my_children_ids():
    return [c.student_id for c in _my_children()]


def _get_or_create_parent_conversation(admin_id):
    """이 신청 건 전용 대화 스레드를 새로 만든다. 같은 학부모-관리자 사이에도
    신청 건마다 독립된 Conversation을 쓴다 - 기존 대화를 검색해서 재사용하면
    상담 신청 스레드와 보강 신청 스레드가 우연히 하나로 합쳐져 버린다(실제로
    이 버그를 검증 중 재현해서 고쳤다). 호출부가 obj.parent_conversation_id가
    비어 있을 때만 이 함수를 부르므로 매번 새로 만들어도 중복 생성되지 않는다."""
    uid = current_user.user_id
    conv = Conversation(user1_id=uid, user2_id=admin_id)
    db.session.add(conv)
    db.session.flush()
    return conv


def _any_admin_id():
    admin = User.query.filter(User.role_level <= 2, User.is_active == True).order_by(User.role_level).first()
    return admin.user_id if admin else None


def _thread_messages(conversation_id):
    if not conversation_id:
        return []
    msgs = ConversationMessage.query.filter_by(conversation_id=conversation_id) \
        .order_by(ConversationMessage.created_at).all()
    return [{
        'kind': 'me' if m.sender_id == current_user.user_id else 'them',
        'who': None if m.sender_id == current_user.user_id else (m.sender.name if m.sender else '담당자'),
        'text': m.body,
        'time': m.created_at.strftime(KST_FMT),
        'attachment_url': url_for('chat_widget.attachment', msg_id=m.message_id) if m.attachment_url else None,
        'attachment_name': m.attachment_name,
        'is_image': _is_image(m.attachment_name) if m.attachment_url else False,
        '_ts': m.created_at,
    } for m in msgs]


def _unread_in(conversation_id):
    if not conversation_id:
        return False
    return ConversationMessage.query.filter(
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.sender_id != current_user.user_id,
        ConversationMessage.is_read == False,
    ).count() > 0


def _mark_read(conversation_id):
    if not conversation_id:
        return
    unread = ConversationMessage.query.filter(
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.sender_id != current_user.user_id,
        ConversationMessage.is_read == False,
    ).all()
    for m in unread:
        m.mark_read()
    if unread:
        db.session.commit()


# ==================== 홈 요약 ====================

@chat_widget_bp.route('/widget/summary')
@requires_role('parent', 'admin')
def summary():
    child_ids = _my_children_ids()
    threads = []

    consults = ConsultationRequest.query.filter(
        ConsultationRequest.student_id.in_(child_ids)
    ).order_by(ConsultationRequest.updated_at.desc()).limit(10).all() if child_ids else []
    for c in consults:
        threads.append({
            'type': 'consult', 'id': c.request_id,
            'title': '상담 신청', 'who': c.student.display_name if c.student else '',
            'status': c.status, 'status_label': _consult_status_label(c),
            'preview': _consult_preview(c),
            'time': c.updated_at.strftime(KST_FMT),
            'unread': _unread_in(c.parent_conversation_id),
            '_ts': c.updated_at,
        })

    makeups = MakeupClassRequest.query.filter(
        MakeupClassRequest.student_id.in_(child_ids)
    ).order_by(MakeupClassRequest.updated_at.desc()).limit(10).all() if child_ids else []
    for m in makeups:
        threads.append({
            'type': 'makeup', 'id': m.request_id,
            'title': '보강 신청', 'who': m.student.display_name if m.student else '',
            'status': m.status, 'status_label': _makeup_status_label(m),
            'preview': _makeup_preview(m),
            'time': m.updated_at.strftime(KST_FMT),
            'unread': _unread_in(m.parent_conversation_id),
            '_ts': m.updated_at,
        })

    refunds = RefundRequest.query.filter_by(requester_id=current_user.user_id) \
        .order_by(RefundRequest.updated_at.desc()).limit(10).all()
    for r in refunds:
        threads.append({
            'type': 'refund', 'id': r.request_id,
            'title': '환불 요청', 'who': f'{r.payment.amount:,}원' if r.payment else '',
            'status': r.status, 'status_label': _refund_status_label(r),
            'preview': _refund_preview(r),
            'time': r.updated_at.strftime(KST_FMT),
            'unread': _unread_in(r.parent_conversation_id),
            '_ts': r.updated_at,
        })

    threads.sort(key=lambda t: t['_ts'], reverse=True)
    for t in threads:
        del t['_ts']

    return jsonify({
        'unread_total': sum(1 for t in threads if t['unread']),
        'threads': threads[:20],
        'categories': CATEGORY_CHOICES,
        'children': [{'id': c.student_id, 'name': c.display_name} for c in _my_children()],
    })


# ==================== 상태 라벨/미리보기 헬퍼 ====================

def _consult_status_label(c):
    return {'pending': '접수 대기', 'scheduled': '일정 확정', 'rejected': '반려', 'completed': '완료'}.get(c.status, c.status)

def _consult_preview(c):
    if c.status == 'scheduled':
        return f'✅ 상담 일정이 확정되었습니다 · {c.scheduled_date.strftime("%Y-%m-%d") if c.scheduled_date else ""}'
    if c.status == 'rejected':
        return f'반려: {c.reject_reason or ""}'
    return c.reason[:60] if c.reason else ''

def _makeup_status_label(m):
    return {'pending': '접수 대기', 'approved': '보강 확정', 'rejected': '반려'}.get(m.status, m.status)

def _makeup_preview(m):
    if m.status == 'approved':
        return '✅ 보강 일정이 확정되었습니다'
    if m.status == 'rejected':
        return f'반려: {m.admin_notes or ""}'
    if m.teacher_confirmed:
        return '강사 확인 완료 · 관리자 승인 대기중'
    return m.reason[:60] if m.reason else ''

def _refund_status_label(r):
    return {'pending': '검토 대기', 'approved': '승인됨', 'rejected': '반려'}.get(r.status, r.status)

def _refund_preview(r):
    if r.status == 'approved':
        return '✅ 환불이 승인되었습니다'
    if r.status == 'rejected':
        return f'반려: {r.admin_notes or ""}'
    return r.reason[:60] if r.reason else ''


# ==================== 스레드 상세 ====================

def _load_and_check(kind, request_id):
    if kind == 'consult':
        obj = ConsultationRequest.query.get_or_404(request_id)
        if current_user.role == 'parent' and obj.requester_id != current_user.user_id:
            return None
        return obj
    if kind == 'makeup':
        obj = MakeupClassRequest.query.get_or_404(request_id)
        if current_user.role == 'parent' and obj.student_id not in _my_children_ids():
            return None
        return obj
    if kind == 'refund':
        obj = RefundRequest.query.get_or_404(request_id)
        if current_user.role == 'parent' and obj.requester_id != current_user.user_id:
            return None
        return obj
    return None


def _build_timeline(kind, obj):
    events = []
    if kind == 'consult':
        events.append({'kind': 'sys', 'text': '상담 신청이 접수되었습니다', 'time': obj.created_at.strftime(KST_FMT), '_ts': obj.created_at})
        if obj.status == 'scheduled' and obj.responded_at:
            events.append({'kind': 'sys', 'text': f'✅ 상담 일정이 확정되었습니다 · {obj.scheduled_date.strftime("%Y-%m-%d") if obj.scheduled_date else ""} {obj.scheduled_note or ""}'.strip(),
                            'time': obj.responded_at.strftime(KST_FMT), '_ts': obj.responded_at})
        elif obj.status == 'rejected' and obj.responded_at:
            events.append({'kind': 'sys', 'text': f'반려되었습니다: {obj.reject_reason or ""}', 'time': obj.responded_at.strftime(KST_FMT), '_ts': obj.responded_at})
        thread_msgs = _thread_messages(obj.parent_conversation_id)
    elif kind == 'makeup':
        events.append({'kind': 'sys', 'text': '보강 신청이 접수되었습니다', 'time': obj.created_at.strftime(KST_FMT), '_ts': obj.created_at})
        if obj.teacher_confirmed and obj.teacher_confirmed_at:
            events.append({'kind': 'sys', 'text': '강사가 보강 가능 시간을 확인했습니다',
                            'time': obj.teacher_confirmed_at.strftime(KST_FMT), '_ts': obj.teacher_confirmed_at})
        if obj.status == 'approved' and obj.admin_response_date:
            course = obj.created_makeup_course
            when = f'{course.start_date.strftime("%Y-%m-%d")} {course.start_time.strftime("%H:%M")}' if course and course.start_date and course.start_time else ''
            events.append({'kind': 'sys', 'text': f'✅ 보강 일정이 확정되었습니다 · {when}'.strip(),
                            'time': obj.admin_response_date.strftime(KST_FMT), '_ts': obj.admin_response_date})
        elif obj.status == 'rejected' and obj.admin_response_date:
            events.append({'kind': 'sys', 'text': f'반려되었습니다: {obj.admin_notes or ""}', 'time': obj.admin_response_date.strftime(KST_FMT), '_ts': obj.admin_response_date})
        thread_msgs = _thread_messages(obj.parent_conversation_id)
    else:  # refund
        events.append({'kind': 'sys', 'text': '환불 요청이 접수되었습니다', 'time': obj.created_at.strftime(KST_FMT), '_ts': obj.created_at})
        if obj.status == 'approved' and obj.responded_at:
            events.append({'kind': 'sys', 'text': f'✅ 환불이 승인되었습니다 · {obj.admin_notes or ""}'.strip(),
                            'time': obj.responded_at.strftime(KST_FMT), '_ts': obj.responded_at})
        elif obj.status == 'rejected' and obj.responded_at:
            events.append({'kind': 'sys', 'text': f'반려되었습니다: {obj.admin_notes or ""}', 'time': obj.responded_at.strftime(KST_FMT), '_ts': obj.responded_at})
        thread_msgs = _thread_messages(obj.parent_conversation_id)

    timeline = events + thread_msgs
    timeline.sort(key=lambda e: e['_ts'])
    for e in timeline:
        del e['_ts']
    return timeline


def _fields(kind, obj):
    if kind == 'consult':
        f = {'자녀': obj.student.display_name if obj.student else '', '분류': obj.category}
        if obj.status == 'scheduled':
            f['확정 일정'] = obj.scheduled_date.strftime('%Y-%m-%d') if obj.scheduled_date else ''
        elif obj.preferred_date:
            f['희망일'] = obj.preferred_date.strftime('%Y-%m-%d')
        return f
    if kind == 'makeup':
        f = {
            '자녀': obj.student.display_name if obj.student else '',
            '수업': obj.requested_course.course_name if obj.requested_course else '',
        }
        course = obj.created_makeup_course
        if obj.status == 'approved' and course and course.start_date:
            when = course.start_date.strftime('%Y-%m-%d')
            if course.start_time:
                when += ' ' + course.start_time.strftime('%H:%M')
            f['확정 일정'] = when
        else:
            f['희망일'] = obj.requested_date.strftime('%Y-%m-%d') if obj.requested_date else '특별히 없음'
            f['강사 확인'] = '완료' if obj.teacher_confirmed else '대기중'
        return f
    if kind == 'refund':
        return {
            '금액': f'{obj.payment.amount:,}원' if obj.payment else '',
            '수업': obj.payment.course.course_name if obj.payment and obj.payment.course else '',
        }
    return {}


@chat_widget_bp.route('/widget/thread/<kind>/<request_id>')
@requires_role('parent', 'admin')
def thread(kind, request_id):
    obj = _load_and_check(kind, request_id)
    if obj is None:
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    conv_id = obj.parent_conversation_id
    _mark_read(conv_id)

    label_fn = {'consult': _consult_status_label, 'makeup': _makeup_status_label, 'refund': _refund_status_label}[kind]
    return jsonify({
        'type': kind,
        'title': {'consult': '상담 신청', 'makeup': '보강 신청', 'refund': '환불 요청'}[kind],
        'status': obj.status,
        'status_label': label_fn(obj),
        'fields': _fields(kind, obj),
        'reason': getattr(obj, 'reason', None),
        'timeline': _build_timeline(kind, obj),
    })


@chat_widget_bp.route('/widget/thread/<kind>/<request_id>/reply', methods=['POST'])
@requires_role('parent', 'admin')
def reply(kind, request_id):
    obj = _load_and_check(kind, request_id)
    if obj is None:
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    body = (request.form.get('body') or '').strip()
    att_url, att_name = _save_attachment(request.files.get('attachment'))
    if not body and not att_url:
        return jsonify({'error': '메시지를 입력해주세요.'}), 400

    admin_id = _any_admin_id()
    if not admin_id:
        return jsonify({'error': '문의를 받을 관리자가 없습니다.'}), 500

    if not obj.parent_conversation_id:
        conv = _get_or_create_parent_conversation(admin_id)
        obj.parent_conversation_id = conv.conversation_id
    else:
        conv = Conversation.query.get(obj.parent_conversation_id)

    msg = ConversationMessage(
        conversation_id=conv.conversation_id, sender_id=current_user.user_id,
        body=body or '(사진을 보냈습니다)', attachment_url=att_url, attachment_name=att_name,
    )
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)

    type_label = {'consult': '상담 신청', 'makeup': '보강 신청', 'refund': '환불 요청'}[kind]
    detail_url = {
        'consult': lambda: url_for('consultation_request.admin_detail', request_id=obj.request_id),
        'makeup': lambda: url_for('admin.makeup_requests'),
        'refund': lambda: url_for('refund_request.admin_detail', request_id=obj.request_id),
    }[kind]()

    # 이 스레드에 이미 참여 중인 상대(관리자든 다른 참여자든)에게 알림
    other_id = conv.user2_id if conv.user1_id == current_user.user_id else conv.user1_id
    db.session.add(Notification(
        user_id=other_id,
        notification_type='dm',
        title=f'💬 {current_user.name}님의 새 메시지',
        message=f'[{type_label}] {(body or msg.body)[:80]}',
        link_url=detail_url,
        related_user_id=current_user.user_id,
    ))
    db.session.commit()

    return jsonify({'ok': True})


@chat_widget_bp.route('/widget/attachment/<int:msg_id>')
@requires_role('parent', 'admin')
def attachment(msg_id):
    """대화 중 첨부파일 서빙. app.messages.download_attachment은 강사/관리자
    전용이라 학부모가 못 본다 - 여기는 학부모도 자기 대화에 한해 볼 수 있게
    별도로 둔다. 관리자는 어느 상담 건이든(이 conv에 user1/user2로 없어도)
    admin_detail 화면에서 볼 수 있어야 하므로 role만으로 허용한다."""
    msg = ConversationMessage.query.get_or_404(msg_id)
    if not msg.attachment_url:
        abort(404)
    if current_user.role == 'parent':
        conv = Conversation.query.get_or_404(msg.conversation_id)
        uid = current_user.user_id
        if conv.user1_id != uid and conv.user2_id != uid:
            abort(403)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_dir = os.path.dirname(os.path.join(upload_folder, msg.attachment_url))
    file_name = os.path.basename(msg.attachment_url)
    return send_from_directory(file_dir, file_name, download_name=msg.attachment_name or file_name)


# ==================== 빠른 상담 신청 (위젯 안에서 바로 작성) ====================

@chat_widget_bp.route('/widget/quick/consult', methods=['POST'])
@requires_role('parent', 'admin')
def quick_consult():
    data = request.get_json(silent=True) or {}
    student_id = data.get('student_id', '')
    category = data.get('category', '')
    reason = (data.get('reason') or '').strip()

    if student_id not in _my_children_ids():
        return jsonify({'error': '자녀를 올바르게 선택해주세요.'}), 400
    if category not in CATEGORY_CHOICES:
        return jsonify({'error': '상담 분류를 선택해주세요.'}), 400
    if not reason:
        return jsonify({'error': '상담 사유를 입력해주세요.'}), 400

    req = ConsultationRequest(
        student_id=student_id, requester_id=current_user.user_id,
        category=category, reason=reason, status='pending',
    )
    db.session.add(req)
    db.session.flush()

    admins = User.query.filter(User.role_level <= 2, User.is_active == True).all()
    for admin in admins:
        db.session.add(Notification(
            user_id=admin.user_id, notification_type='consultation_request',
            title=f'📋 새 상담 신청: {req.student.display_name if req.student else ""}',
            message=f'{req.category} · {req.reason[:60]}',
            related_entity_type='consultation_request', related_entity_id=req.request_id,
            link_url=url_for('consultation_request.admin_detail', request_id=req.request_id),
        ))
    db.session.commit()

    return jsonify({'ok': True, 'id': req.request_id})


# ==================== 대화형 진입 - 자유 텍스트 의도 분류 ====================
# 학부모가 위젯을 열고 처음 던지는 한 문장만 보고 4개 카테고리 중 하나로
# 라우팅한다. 분류 이후의 실제 데이터 입력(자녀 선택, 사유, 금액 등)은 전부
# 기존 구조화된 폼을 그대로 쓴다 - LLM은 "입구"에서만 판단하고, 보강 일정·
# 환불 금액처럼 틀리면 안 되는 값은 절대 대화 중 자동으로 채우지 않는다.

_WIDGET_LLM_HOURLY_LIMIT = 30
_WIDGET_INTENTS = ('consult', 'makeup', 'refund', 'inquiry')


def _widget_llm_rate_limited():
    from app.models.api_usage_log import ApiUsageLog
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_calls = ApiUsageLog.query.filter(
        ApiUsageLog.user_id == current_user.user_id,
        ApiUsageLog.usage_type == 'widget_intent_classify',
        ApiUsageLog.created_at >= one_hour_ago,
    ).count()
    return recent_calls >= _WIDGET_LLM_HOURLY_LIMIT


def _log_widget_llm_usage(usage):
    from app.models.api_usage_log import ApiUsageLog
    db.session.add(ApiUsageLog(
        user_id=current_user.user_id,
        api_type='claude',
        model_name='claude-sonnet-4-6',
        usage_type='widget_intent_classify',
        input_tokens=usage['input_tokens'],
        output_tokens=usage['output_tokens'],
        cost_usd=ApiUsageLog.calc_claude_cost(usage['input_tokens'], usage['output_tokens']),
    ))


@chat_widget_bp.route('/widget/classify', methods=['POST'])
@requires_role('parent', 'admin')
def classify_intent():
    from app.utils.llm_assist import call_claude_text, extract_json_block

    text = (request.get_json(silent=True) or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': '메시지를 입력해주세요.'}), 400
    text = text[:500]

    fallback = {'intent': 'inquiry', 'reply': '네, 확인 후 답변드릴게요. 아래에서 문의를 남겨주세요.'}

    if _widget_llm_rate_limited():
        return jsonify(fallback)

    prompt = f"""당신은 국어 학원 학부모 채팅창의 안내 담당자입니다.
학부모가 보낸 메시지 한 줄만 보고 아래 4가지 중 하나로 분류하세요.

- consult: 신규/퇴원/분기별/진로진학 등 상담 신청
- makeup: 결석 등으로 인한 보강 수업 신청
- refund: 결제 내역 확인, 환불 요청
- inquiry: 위 3가지에 해당하지 않는 그 외 일반 문의

학부모 메시지: "{text}"

다음 JSON 형식으로만 답하세요. 다른 설명은 절대 붙이지 마세요.
{{"intent": "consult 또는 makeup 또는 refund 또는 inquiry", "reply": "학부모에게 보여줄 짧고 다정한 한 문장 안내(존댓말, 20자 내외, 이모지 없이)"}}"""

    try:
        raw, usage = call_claude_text(prompt, max_tokens=150)
    except Exception:
        current_app.logger.exception('[chat_widget.classify_intent] 호출 실패')
        return jsonify(fallback)

    try:
        _log_widget_llm_usage(usage)
        db.session.commit()
    except Exception:
        current_app.logger.exception('[chat_widget.classify_intent] 사용량 로그 저장 실패')

    parsed = extract_json_block(raw) or {}
    intent = parsed.get('intent') if parsed.get('intent') in _WIDGET_INTENTS else 'inquiry'
    reply = parsed.get('reply') or fallback['reply']
    return jsonify({'intent': intent, 'reply': reply})
