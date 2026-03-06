# -*- coding: utf-8 -*-
"""Web Push 알림 발송 유틸리티"""
import json


def send_push_to_user(user_id, title, body, url='/notifications'):
    """특정 사용자의 모든 Push 구독에 알림 발송"""
    from flask import current_app
    from app.models.push_subscription import PushSubscription
    from app.models import db

    vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
    vapid_claims_sub = current_app.config.get('VAPID_CLAIMS_SUB', 'mailto:contact@momoai.kr')

    if not vapid_private_key:
        current_app.logger.warning('[Push] VAPID_PRIVATE_KEY not set — skipping push')
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        current_app.logger.warning('[Push] pywebpush not installed — skipping push')
        return

    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subscriptions:
        current_app.logger.info(f'[Push] No subscriptions for user {user_id}')
        return

    current_app.logger.info(f'[Push] Sending to user {user_id}: {len(subscriptions)} subscription(s)')
    expired_ids = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}
                },
                data=json.dumps({'title': title, 'body': body, 'url': url}),
                vapid_private_key=vapid_private_key,
                vapid_claims={'sub': vapid_claims_sub}
            )
            current_app.logger.info(f'[Push] Sent OK to sub #{sub.id}')
        except WebPushException as e:
            status = e.response.status_code if e.response else 'no-response'
            current_app.logger.warning(f'[Push] WebPushException sub#{sub.id} status={status}: {e}')
            if e.response and e.response.status_code in (400, 403, 404, 410):
                expired_ids.append(sub.id)
        except Exception as e:
            current_app.logger.warning(f'[Push] Unexpected error sub#{sub.id}: {e}')

    if expired_ids:
        current_app.logger.info(f'[Push] Removing {len(expired_ids)} expired subscription(s)')
        PushSubscription.query.filter(PushSubscription.id.in_(expired_ids)).delete()
        db.session.commit()
