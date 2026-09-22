# -*- coding: utf-8 -*-
"""환불 요청 라우트."""
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.refund_request import refund_request_bp
from app.models import db, User, Payment, ParentStudent, Notification
from app.models.refund_request import RefundRequest
from app.models.conversation import Conversation, ConversationMessage
from app.utils.decorators import requires_role


def _can_access_payment(payment):
    if current_user.role == 'admin':
        return True
    if current_user.role == 'parent':
        return ParentStudent.query.filter_by(
            parent_id=current_user.user_id, student_id=payment.student_id, is_active=True
        ).first() is not None
    return False


def _notify_admins_new_request(req):
    admins = User.query.filter(User.role_level <= 2, User.is_active == True).all()
    link = url_for('refund_request.admin_detail', request_id=req.request_id)
    for admin in admins:
        db.session.add(Notification(
            user_id=admin.user_id,
            notification_type='refund_request',
            title=f'💰 새 환불 요청: {req.payment.amount:,}원',
            message=req.reason[:80],
            related_entity_type='refund_request',
            related_entity_id=req.request_id,
            link_url=link,
        ))


def _notify_requester_response(req):
    if not req.requester_id:
        return
    if req.status == 'approved':
        title = '✅ 환불 요청이 승인되었습니다'
        message = req.admin_notes or f'{req.payment.amount:,}원 환불 처리되었습니다.'
    elif req.status == 'rejected':
        title = '환불 요청이 반려되었습니다'
        message = req.admin_notes or ''
    else:
        return
    db.session.add(Notification(
        user_id=req.requester_id,
        notification_type='refund_request',
        title=title,
        message=message,
        related_entity_type='refund_request',
        related_entity_id=req.request_id,
        link_url=url_for('refund_request.detail', request_id=req.request_id),
    ))


# ==================== 학부모 ====================

@refund_request_bp.route('/')
@requires_role('parent', 'admin')
def index():
    """내 환불 요청 목록"""
    requests = RefundRequest.query.filter_by(
        requester_id=current_user.user_id
    ).order_by(RefundRequest.created_at.desc()).all()
    return render_template('refund_request/parent_list.html', requests=requests)


@refund_request_bp.route('/new/<payment_id>', methods=['GET', 'POST'])
@requires_role('parent', 'admin')
def new(payment_id):
    """환불 요청서 작성"""
    payment = Payment.query.get_or_404(payment_id)
    if not _can_access_payment(payment):
        abort(403)
    if payment.status != 'completed':
        flash('납부 완료된 결제 건만 환불을 요청할 수 있습니다.', 'error')
        return redirect(url_for('parent.all_payments'))

    existing = RefundRequest.query.filter_by(payment_id=payment_id, status='pending').first()
    if existing:
        flash('이미 처리 대기 중인 환불 요청이 있습니다.', 'error')
        return redirect(url_for('refund_request.detail', request_id=existing.request_id))

    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        if not reason:
            flash('환불 요청 사유를 입력해주세요.', 'error')
            return redirect(url_for('refund_request.new', payment_id=payment_id))

        req = RefundRequest(
            payment_id=payment_id,
            requester_id=current_user.user_id,
            reason=reason,
            status='pending',
        )
        db.session.add(req)
        db.session.flush()
        _notify_admins_new_request(req)
        db.session.commit()

        flash('환불 요청이 접수되었습니다. 관리자 확인 후 답변드립니다.', 'success')
        return redirect(url_for('refund_request.detail', request_id=req.request_id))

    return render_template('refund_request/new.html', payment=payment)


@refund_request_bp.route('/<request_id>')
@requires_role('parent', 'admin')
def detail(request_id):
    """환불 요청 상세"""
    req = RefundRequest.query.get_or_404(request_id)
    if current_user.role == 'parent' and req.requester_id != current_user.user_id:
        abort(403)
    return render_template('refund_request/detail.html', req=req)


# ==================== 관리자 ====================

@refund_request_bp.route('/admin')
@requires_role('admin')
def admin_list():
    """환불 요청 접수함"""
    status_filter = request.args.get('status', '')
    query = RefundRequest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    requests = query.order_by(RefundRequest.created_at.desc()).all()
    pending_count = RefundRequest.query.filter_by(status='pending').count()
    return render_template('refund_request/admin_list.html',
                            requests=requests, status_filter=status_filter,
                            pending_count=pending_count)


@refund_request_bp.route('/admin/<request_id>')
@requires_role('admin')
def admin_detail(request_id):
    """환불 요청 상세 (관리자) - 승인/거절 액션 포함"""
    req = RefundRequest.query.get_or_404(request_id)
    parent_messages = []
    if req.parent_conversation_id:
        parent_messages = ConversationMessage.query.filter_by(
            conversation_id=req.parent_conversation_id
        ).order_by(ConversationMessage.created_at).all()
    return render_template('refund_request/admin_detail.html', req=req, parent_messages=parent_messages)


@refund_request_bp.route('/admin/<request_id>/parent-reply', methods=['POST'])
@requires_role('admin')
def parent_reply(request_id):
    """학부모(위젯)에게 답장 - app.chat_widget이 학부모 쪽 답장을 담당하고
    여기는 관리자 쪽 답장만 처리한다."""
    req = RefundRequest.query.get_or_404(request_id)
    body = request.form.get('body', '').strip()
    if not body:
        flash('메시지를 입력해주세요.', 'error')
        return redirect(url_for('refund_request.admin_detail', request_id=request_id))

    uid = current_user.user_id
    if not req.parent_conversation_id:
        if not req.requester_id:
            flash('신청자 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('refund_request.admin_detail', request_id=request_id))
        # 신청 건마다 독립된 Conversation을 쓴다(기존 대화 재사용 금지) - 재사용하면
        # 같은 학부모의 다른 신청(상담/보강) 스레드와 뒤섞인다.
        conv = Conversation(user1_id=uid, user2_id=req.requester_id)
        db.session.add(conv)
        db.session.flush()
        req.parent_conversation_id = conv.conversation_id
    else:
        conv = Conversation.query.get(req.parent_conversation_id)

    msg = ConversationMessage(conversation_id=conv.conversation_id, sender_id=uid, body=body)
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)

    if req.requester_id:
        db.session.add(Notification(
            user_id=req.requester_id,
            notification_type='dm',
            title=f'💬 {current_user.name}님의 새 메시지',
            message=f'[환불 요청] {body[:80]}',
            related_user_id=uid,
        ))
    db.session.commit()

    flash('답장을 보냈습니다.', 'success')
    return redirect(url_for('refund_request.admin_detail', request_id=request_id))


@refund_request_bp.route('/admin/<request_id>/approve', methods=['POST'])
@requires_role('admin')
def approve(request_id):
    """환불 승인 - 실제 송금/취소는 관리자가 시스템 밖에서 처리했다는 것을 전제로
    Payment.status만 'refunded'로 남긴다. 자동으로 결제대행사에 취소 요청을 보내지 않는다."""
    req = RefundRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('이미 처리된 요청입니다.', 'warning')
        return redirect(url_for('refund_request.admin_detail', request_id=request_id))

    notes = request.form.get('admin_notes', '').strip()
    req.status = 'approved'
    req.admin_notes = notes
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    req.payment.status = 'refunded'
    _notify_requester_response(req)
    db.session.commit()

    flash('환불 요청을 승인하고 결제 상태를 환불 완료로 변경했습니다.', 'success')
    return redirect(url_for('refund_request.admin_detail', request_id=request_id))


@refund_request_bp.route('/admin/<request_id>/reject', methods=['POST'])
@requires_role('admin')
def reject(request_id):
    """환불 거절 (사유 필수)"""
    req = RefundRequest.query.get_or_404(request_id)
    if req.status != 'pending':
        flash('이미 처리된 요청입니다.', 'warning')
        return redirect(url_for('refund_request.admin_detail', request_id=request_id))

    reason = request.form.get('admin_notes', '').strip()
    if not reason:
        flash('거절 사유를 입력해주세요.', 'error')
        return redirect(url_for('refund_request.admin_detail', request_id=request_id))

    req.status = 'rejected'
    req.admin_notes = reason
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    _notify_requester_response(req)
    db.session.commit()

    flash('환불 요청을 거절했습니다.', 'success')
    return redirect(url_for('refund_request.admin_detail', request_id=request_id))
