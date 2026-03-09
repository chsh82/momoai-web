# -*- coding: utf-8 -*-
"""강사↔관리자 1:1 대화 스레드 라우트"""
from flask import render_template, redirect, url_for, request, jsonify, abort, flash
from flask_login import login_required, current_user
from datetime import datetime

from app.messages import messages_bp
from app.models import db, User
from app.models.conversation import Conversation, ConversationMessage


def _require_teacher_or_admin():
    """강사 또는 관리자만 접근 가능"""
    if current_user.role not in ('admin', 'teacher'):
        abort(403)


def _get_or_create_conversation(other_user_id):
    """두 사용자 간의 대화 스레드를 찾거나 신규 생성"""
    uid = current_user.user_id
    conv = Conversation.query.filter(
        db.or_(
            db.and_(Conversation.user1_id == uid, Conversation.user2_id == other_user_id),
            db.and_(Conversation.user1_id == other_user_id, Conversation.user2_id == uid)
        )
    ).first()
    if conv is None:
        conv = Conversation(user1_id=uid, user2_id=other_user_id)
        db.session.add(conv)
        db.session.flush()  # conversation_id 확보
    return conv


@messages_bp.route('/')
@login_required
def inbox():
    """받은 메시지함 — 내가 참여한 대화 목록"""
    _require_teacher_or_admin()
    uid = current_user.user_id
    conversations = Conversation.query.filter(
        db.or_(
            Conversation.user1_id == uid,
            Conversation.user2_id == uid
        )
    ).order_by(Conversation.last_message_at.desc()).all()

    # 각 대화별 미읽은 메시지 수 및 마지막 메시지 계산
    unread_map = {}
    last_messages = {}
    for conv in conversations:
        cnt = ConversationMessage.query.filter_by(
            conversation_id=conv.conversation_id,
            is_read=False
        ).filter(ConversationMessage.sender_id != uid).count()
        unread_map[conv.conversation_id] = cnt

        last_msg = ConversationMessage.query.filter_by(
            conversation_id=conv.conversation_id
        ).order_by(ConversationMessage.created_at.desc()).first()
        last_messages[conv.conversation_id] = last_msg

    return render_template('messages/inbox.html',
                           conversations=conversations,
                           unread_map=unread_map,
                           last_messages=last_messages)


@messages_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_conversation():
    """새 대화 시작"""
    _require_teacher_or_admin()

    if request.method == 'POST':
        other_id = request.form.get('other_user_id', '').strip()
        body = request.form.get('body', '').strip()
        if not other_id or not body:
            flash('받는 사람과 메시지 내용을 입력해주세요.', 'error')
            return redirect(url_for('messages.new_conversation'))

        other = User.query.get(other_id)
        if not other or other.role not in ('admin', 'teacher'):
            flash('유효하지 않은 수신자입니다.', 'error')
            return redirect(url_for('messages.new_conversation'))

        # 강사는 master_admin(role_level=1)에게만 전송 가능
        if current_user.role == 'teacher' and other.role_level != 1:
            flash('강사는 Master 관리자에게만 메시지를 보낼 수 있습니다.', 'error')
            return redirect(url_for('messages.new_conversation'))

        conv = _get_or_create_conversation(other_id)
        msg = ConversationMessage(
            conversation_id=conv.conversation_id,
            sender_id=current_user.user_id,
            body=body
        )
        conv.last_message_at = datetime.utcnow()
        db.session.add(msg)
        db.session.commit()

        # 푸시 알림
        _send_dm_notification(other, conv.conversation_id, body)

        return redirect(url_for('messages.conversation', conv_id=conv.conversation_id))

    # 대화 상대 목록
    # 강사: master_admin(role_level=1)만 / 관리자: 강사+관리자 전체(본인 제외)
    if current_user.role == 'teacher':
        peers = User.query.filter(
            User.role_level == 1,
            User.user_id != current_user.user_id,
            User.is_active == True
        ).order_by(User.name).all()
    else:
        peers = User.query.filter(
            User.role.in_(['admin', 'teacher']),
            User.user_id != current_user.user_id,
            User.is_active == True
        ).order_by(User.name).all()

    return render_template('messages/new_conversation.html', peers=peers)


@messages_bp.route('/<int:conv_id>')
@login_required
def conversation(conv_id):
    """대화 스레드 상세 보기"""
    _require_teacher_or_admin()
    uid = current_user.user_id

    conv = Conversation.query.get_or_404(conv_id)
    if conv.user1_id != uid and conv.user2_id != uid:
        abort(403)

    # 상대방이 보낸 메시지를 읽음 처리
    unread_msgs = ConversationMessage.query.filter_by(
        conversation_id=conv_id, is_read=False
    ).filter(ConversationMessage.sender_id != uid).all()
    for m in unread_msgs:
        m.mark_read()
    if unread_msgs:
        db.session.commit()

    messages = conv.messages.all()
    other = conv.get_other_user(uid)
    return render_template('messages/conversation.html',
                           conv=conv, messages=messages, other=other)


@messages_bp.route('/<int:conv_id>/reply', methods=['POST'])
@login_required
def reply(conv_id):
    """대화 스레드에 답장"""
    _require_teacher_or_admin()
    uid = current_user.user_id

    conv = Conversation.query.get_or_404(conv_id)
    if conv.user1_id != uid and conv.user2_id != uid:
        abort(403)

    body = request.form.get('body', '').strip()
    if not body:
        flash('메시지 내용을 입력해주세요.', 'error')
        return redirect(url_for('messages.conversation', conv_id=conv_id))

    msg = ConversationMessage(
        conversation_id=conv_id,
        sender_id=uid,
        body=body
    )
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()

    other = conv.get_other_user(uid)
    _send_dm_notification(other, conv_id, body)

    return redirect(url_for('messages.conversation', conv_id=conv_id))


@messages_bp.route('/<int:conv_id>/poll')
@login_required
def poll(conv_id):
    """AJAX 폴링: since_id 이후의 새 메시지 반환"""
    _require_teacher_or_admin()
    uid = current_user.user_id

    conv = Conversation.query.get_or_404(conv_id)
    if conv.user1_id != uid and conv.user2_id != uid:
        abort(403)

    since_id = request.args.get('since', 0, type=int)
    new_msgs = ConversationMessage.query.filter(
        ConversationMessage.conversation_id == conv_id,
        ConversationMessage.message_id > since_id
    ).order_by(ConversationMessage.created_at).all()

    # 상대방 메시지 읽음 처리
    for m in new_msgs:
        if m.sender_id != uid and not m.is_read:
            m.mark_read()
    if any(m.sender_id != uid for m in new_msgs):
        db.session.commit()

    return jsonify([{
        'id': m.message_id,
        'body': m.body,
        'is_mine': m.sender_id == uid,
        'sender_name': m.sender.name if m.sender else '',
        'created_at': m.created_at.strftime('%m/%d %H:%M'),
        'is_read': m.is_read,
    } for m in new_msgs])


@messages_bp.route('/unread-count')
@login_required
def unread_count():
    """AJAX: 미읽은 DM 총 개수"""
    if current_user.role not in ('admin', 'teacher'):
        return jsonify({'count': 0})
    uid = current_user.user_id
    count = ConversationMessage.query.join(
        Conversation,
        ConversationMessage.conversation_id == Conversation.conversation_id
    ).filter(
        db.or_(Conversation.user1_id == uid, Conversation.user2_id == uid),
        ConversationMessage.sender_id != uid,
        ConversationMessage.is_read == False
    ).count()
    return jsonify({'count': count})


def _send_dm_notification(recipient, conv_id, body_preview):
    """DM 수신 알림 전송"""
    try:
        from app.models.notification import Notification
        notif = Notification(
            user_id=recipient.user_id,
            notification_type='dm',
            title=f'💬 {current_user.name}님의 새 메시지',
            message=body_preview[:80] + ('...' if len(body_preview) > 80 else ''),
            link_url=url_for('messages.conversation', conv_id=conv_id),
            related_user_id=current_user.user_id
        )
        db.session.add(notif)
        db.session.commit()

        # Web Push
        try:
            from app.utils.push_utils import send_push_to_user
            send_push_to_user(
                user_id=recipient.user_id,
                title=f'💬 {current_user.name}님의 새 메시지',
                body=body_preview[:80],
                url=url_for('messages.conversation', conv_id=conv_id, _external=False)
            )
        except Exception:
            pass
    except Exception:
        pass
