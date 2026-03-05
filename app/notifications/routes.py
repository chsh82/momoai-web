# -*- coding: utf-8 -*-
"""알림 라우트"""
from flask import render_template, redirect, url_for, jsonify, request, current_app
from flask_login import login_required, current_user

from app.notifications import notifications_bp
from app.models import db, Notification
from app.models.push_subscription import PushSubscription


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


# ── Web Push API ──────────────────────────────────────────────────

@notifications_bp.route('/push/vapid-public-key')
def vapid_public_key():
    """브라우저에 VAPID 공개키 제공"""
    key = current_app.config.get('VAPID_PUBLIC_KEY', '')
    return jsonify({'public_key': key})


@notifications_bp.route('/push/status')
@login_required
def push_status():
    """현재 사용자의 Push 구독 존재 여부 반환"""
    count = PushSubscription.query.filter_by(user_id=current_user.user_id).count()
    return jsonify({'subscribed': count > 0, 'count': count})


@notifications_bp.route('/push/test')
@login_required
def push_test():
    """현재 사용자에게 테스트 Push 발송 — 결과를 JSON으로 반환"""
    import traceback, json as _json

    result = {
        'vapid_key_set': bool(current_app.config.get('VAPID_PRIVATE_KEY')),
        'vapid_pub_set': bool(current_app.config.get('VAPID_PUBLIC_KEY')),
        'subscriptions': [],
        'send_results': [],
        'error': None
    }

    subs = PushSubscription.query.filter_by(user_id=current_user.user_id).all()
    result['subscriptions'] = [{'id': s.id, 'endpoint_prefix': s.endpoint[:60]} for s in subs]

    if not subs:
        result['error'] = 'No subscriptions found for this user'
        return jsonify(result)

    if not result['vapid_key_set']:
        result['error'] = 'VAPID_PRIVATE_KEY not set in config'
        return jsonify(result)

    try:
        from pywebpush import webpush, WebPushException
    except ImportError as e:
        result['error'] = f'pywebpush not installed: {e}'
        return jsonify(result)

    vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
    vapid_claims_sub = current_app.config.get('VAPID_CLAIMS_SUB', 'mailto:contact@momoai.kr')

    for sub in subs:
        sub_result = {'id': sub.id, 'ok': False, 'error': None}
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}
                },
                data=_json.dumps({'title': '🔔 테스트 알림', 'body': 'Push 알림이 정상 동작합니다!', 'url': '/notifications'}),
                vapid_private_key=vapid_private_key,
                vapid_claims={'sub': vapid_claims_sub}
            )
            sub_result['ok'] = True
        except WebPushException as e:
            status = e.response.status_code if e.response else 'no-response'
            sub_result['error'] = f'WebPushException status={status}: {str(e)}'
        except Exception as e:
            sub_result['error'] = f'{type(e).__name__}: {str(e)}\n{traceback.format_exc()}'
        result['send_results'].append(sub_result)

    return jsonify(result)


@notifications_bp.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    """Push 구독 정보 저장"""
    data = request.json or {}
    endpoint = data.get('endpoint')
    p256dh = data.get('p256dh')
    auth = data.get('auth')

    if not all([endpoint, p256dh, auth]):
        return jsonify({'success': False, 'message': '구독 정보가 부족합니다.'}), 400

    # 이미 존재하면 업데이트, 없으면 생성
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        sub.user_id = current_user.user_id
        sub.p256dh = p256dh
        sub.auth = auth
    else:
        sub = PushSubscription(
            user_id=current_user.user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    """Push 구독 해제"""
    data = request.json or {}
    endpoint = data.get('endpoint')

    if endpoint:
        PushSubscription.query.filter_by(
            endpoint=endpoint,
            user_id=current_user.user_id
        ).delete()
        db.session.commit()

    return jsonify({'success': True})
