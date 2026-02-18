# -*- coding: utf-8 -*-
"""알림 라우트"""
from flask import render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user

from app.notifications import notifications_bp
from app.models import db, Notification


@notifications_bp.route('/')
@login_required
def index():
    """알림 센터"""
    # 필터
    filter_type = request.args.get('type', 'all')

    # 기본 쿼리
    query = Notification.query.filter_by(user_id=current_user.user_id)

    # 타입 필터
    if filter_type != 'all':
        if filter_type == 'unread':
            query = query.filter_by(is_read=False)
        else:
            query = query.filter_by(notification_type=filter_type)

    # 최신순 정렬
    notifications = query.order_by(Notification.created_at.desc()).all()

    # 읽지 않은 알림 수
    unread_count = Notification.get_unread_count(current_user.user_id)

    return render_template('notifications/index.html',
                         notifications=notifications,
                         unread_count=unread_count,
                         filter_type=filter_type)


@notifications_bp.route('/<notification_id>/read', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """알림을 읽음으로 표시"""
    notification = Notification.query.get_or_404(notification_id)

    # 권한 확인
    if notification.user_id != current_user.user_id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    notification.mark_as_read()

    return jsonify({
        'success': True,
        'unread_count': Notification.get_unread_count(current_user.user_id)
    })


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """모든 알림을 읽음으로 표시"""
    Notification.mark_all_as_read(current_user.user_id)

    return jsonify({
        'success': True,
        'unread_count': 0
    })


@notifications_bp.route('/api/unread-count')
@login_required
def api_unread_count():
    """읽지 않은 알림 수 조회 API"""
    unread_count = Notification.get_unread_count(current_user.user_id)

    return jsonify({
        'unread_count': unread_count
    })


@notifications_bp.route('/<notification_id>/delete', methods=['POST'])
@login_required
def delete(notification_id):
    """알림 삭제"""
    notification = Notification.query.get_or_404(notification_id)

    # 권한 확인
    if notification.user_id != current_user.user_id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    db.session.delete(notification)
    db.session.commit()

    return jsonify({
        'success': True,
        'unread_count': Notification.get_unread_count(current_user.user_id)
    })
