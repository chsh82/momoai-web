# -*- coding: utf-8 -*-
"""상담 신청 라우트.

학부모 접수 -> 관리자 처리(접수 확인/내부 협의/일정 확정 또는 거절) ->
(실제 상담 후) teacher.create_consultation에서 상담 기록과 연결, 순서로
진행된다. 강사는 이 신청 건을 직접 승인/거절하지 않고, 관리자가 내부
협의로 요청했을 때만 기존 메신저(app.messages)로 회신한다.
"""
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.consultation_request import consultation_request_bp
from app.models import db, User, Student, ParentStudent, Notification
from app.models.consultation_request import ConsultationRequest, CATEGORY_CHOICES
from app.models.conversation import Conversation, ConversationMessage
from app.utils.decorators import requires_role


def _my_children():
    relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, is_active=True
    ).all()
    return [pr.student for pr in relations if pr.student]


def _notify_admins_new_request(req):
    admins = User.query.filter(User.role_level <= 2, User.is_active == True).all()
    link = url_for('consultation_request.admin_detail', request_id=req.request_id)
    for admin in admins:
        db.session.add(Notification(
            user_id=admin.user_id,
            notification_type='consultation_request',
            title=f'📋 새 상담 신청: {req.student.display_name if req.student else ""}',
            message=f'{req.category} · {req.reason[:60]}',
            related_entity_type='consultation_request',
            related_entity_id=req.request_id,
            link_url=link,
        ))


def _notify_parent_response(req):
    if not req.requester_id:
        return
    if req.status == 'scheduled':
        title = '✅ 상담 일정이 확정되었습니다'
        message = f'{req.scheduled_date.strftime("%Y-%m-%d")} · {req.scheduled_note or ""}'
    elif req.status == 'rejected':
        title = '상담 신청이 반려되었습니다'
        message = req.reject_reason or ''
    else:
        return
    db.session.add(Notification(
        user_id=req.requester_id,
        notification_type='consultation_request',
        title=title,
        message=message,
        related_entity_type='consultation_request',
        related_entity_id=req.request_id,
        link_url=url_for('consultation_request.detail', request_id=req.request_id),
    ))


# ==================== 학부모 ====================

@consultation_request_bp.route('/')
@requires_role('parent', 'admin')
def index():
    """내 상담 신청 목록 (학부모)"""
    if current_user.role == 'parent':
        child_ids = [c.student_id for c in _my_children()]
        requests = ConsultationRequest.query.filter(
            ConsultationRequest.student_id.in_(child_ids)
        ).order_by(ConsultationRequest.created_at.desc()).all() if child_ids else []
    else:
        requests = ConsultationRequest.query.filter_by(
            requester_id=current_user.user_id
        ).order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('consultation_request/parent_list.html', requests=requests)


@consultation_request_bp.route('/new', methods=['GET', 'POST'])
@requires_role('parent', 'admin')
def new():
    """상담 신청서 작성 (학부모)"""
    children = _my_children()

    if request.method == 'POST':
        student_id = request.form.get('student_id', '')
        category = request.form.get('category', '')
        reason = request.form.get('reason', '').strip()
        preferred_date_raw = request.form.get('preferred_date', '').strip()
        preferred_note = request.form.get('preferred_note', '').strip()

        if student_id not in [c.student_id for c in children]:
            flash('자녀를 올바르게 선택해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))
        if category not in CATEGORY_CHOICES:
            flash('상담 분류를 선택해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))
        if not reason:
            flash('상담 사유를 입력해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))

        preferred_date = None
        if preferred_date_raw:
            try:
                preferred_date = datetime.strptime(preferred_date_raw, '%Y-%m-%d').date()
            except ValueError:
                pass

        req = ConsultationRequest(
            student_id=student_id,
            requester_id=current_user.user_id,
            category=category,
            reason=reason,
            preferred_date=preferred_date,
            preferred_note=preferred_note or None,
            status='pending',
        )
        db.session.add(req)
        db.session.flush()
        _notify_admins_new_request(req)
        db.session.commit()

        flash('상담 신청이 접수되었습니다.', 'success')
        return redirect(url_for('consultation_request.detail', request_id=req.request_id))

    return render_template('consultation_request/new.html', children=children,
                            categories=CATEGORY_CHOICES)


@consultation_request_bp.route('/<request_id>')
@requires_role('parent', 'admin')
def detail(request_id):
    """상담 신청 상세 - 학부모 시점(내부 협의 스레드는 노출하지 않음)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    if current_user.role == 'parent' and req.requester_id != current_user.user_id:
        abort(403)
    return render_template('consultation_request/detail.html', req=req)


# ==================== 관리자 ====================

@consultation_request_bp.route('/admin')
@requires_role('admin')
def admin_list():
    """상담 신청 접수함 (관리자)"""
    status_filter = request.args.get('status', '')
    query = ConsultationRequest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    requests = query.order_by(ConsultationRequest.created_at.desc()).all()
    pending_count = ConsultationRequest.query.filter_by(status='pending').count()
    return render_template('consultation_request/admin_list.html',
                            requests=requests, status_filter=status_filter,
                            pending_count=pending_count)


@consultation_request_bp.route('/admin/<request_id>')
@requires_role('admin')
def admin_detail(request_id):
    """상담 신청 상세 - 관리자 시점(내부 협의 시작/일정확정/거절 액션 포함)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    teachers = User.query.filter(
        User.role == 'teacher', User.is_active == True
    ).order_by(User.name).all()
    internal_messages = []
    if req.internal_conversation_id:
        internal_messages = ConversationMessage.query.filter_by(
            conversation_id=req.internal_conversation_id
        ).order_by(ConversationMessage.created_at).all()
    return render_template('consultation_request/admin_detail.html',
                            req=req, teachers=teachers, internal_messages=internal_messages)


@consultation_request_bp.route('/admin/<request_id>/internal-consult', methods=['POST'])
@requires_role('admin')
def internal_consult(request_id):
    """강사에게 내부 협의 요청 - 기존 강사<->관리자 메신저(Conversation) 재사용"""
    req = ConsultationRequest.query.get_or_404(request_id)
    teacher_id = request.form.get('teacher_id', '')
    body = request.form.get('body', '').strip()
    teacher = User.query.filter_by(user_id=teacher_id, role='teacher').first()
    if not teacher:
        flash('강사를 올바르게 선택해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))
    if not body:
        flash('강사에게 전달할 내용을 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    uid = current_user.user_id
    conv = Conversation.query.filter(
        db.or_(
            db.and_(Conversation.user1_id == uid, Conversation.user2_id == teacher_id),
            db.and_(Conversation.user1_id == teacher_id, Conversation.user2_id == uid),
        )
    ).first()
    if conv is None:
        conv = Conversation(user1_id=uid, user2_id=teacher_id)
        db.session.add(conv)
        db.session.flush()

    student_name = req.student.display_name if req.student else ''
    prefix = f'[상담 신청 - {student_name} / {req.category}]\n'
    msg = ConversationMessage(conversation_id=conv.conversation_id, sender_id=uid, body=prefix + body)
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)

    if not req.internal_conversation_id:
        req.internal_conversation_id = conv.conversation_id

    db.session.add(Notification(
        user_id=teacher_id,
        notification_type='dm',
        title=f'💬 {current_user.name}님의 새 메시지',
        message=(prefix + body)[:80],
        link_url=url_for('messages.conversation', conv_id=conv.conversation_id),
        related_user_id=uid,
    ))
    db.session.commit()

    flash('강사에게 내부 협의를 요청했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))


@consultation_request_bp.route('/admin/<request_id>/schedule', methods=['POST'])
@requires_role('admin')
def schedule(request_id):
    """학부모와 일정 확정"""
    req = ConsultationRequest.query.get_or_404(request_id)
    date_raw = request.form.get('scheduled_date', '').strip()
    note = request.form.get('scheduled_note', '').strip()
    try:
        scheduled_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        flash('일정을 올바르게 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    req.status = 'scheduled'
    req.scheduled_date = scheduled_date
    req.scheduled_note = note or None
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    _notify_parent_response(req)
    db.session.commit()

    flash('상담 일정을 확정했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))


@consultation_request_bp.route('/admin/<request_id>/reject', methods=['POST'])
@requires_role('admin')
def reject(request_id):
    """상담 신청 거절 (사유 필수)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    reason = request.form.get('reject_reason', '').strip()
    if not reason:
        flash('거절 사유를 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    req.status = 'rejected'
    req.reject_reason = reason
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    _notify_parent_response(req)
    db.session.commit()

    flash('상담 신청을 거절했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))
