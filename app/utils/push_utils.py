# -*- coding: utf-8 -*-
"""Web Push 알림 발송 유틸리티"""
import json


def send_push_to_user(user_id, title, body, url='/notifications'):
    """특정 사용자의 모든 Push 구독에 알림 발송"""
    from flask import current_app
    from app.models.push_subscription import PushSubscription
    from app.models import db

    vapid_private_key = current_app.config.get('VAPID_PRIVATE_KEY')
    vapid_claims_sub = current_app.config.get('VAPID_CLAIMS_SUB', 'mailto:contact@momoai.com')

    if not vapid_private_key:
        return  # VAPID 키 미설정 시 무시

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return  # pywebpush 미설치 시 무시

    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
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
        except WebPushException as e:
            # 410 Gone / 404 = 구독 만료 → 삭제
            if e.response and e.response.status_code in (404, 410):
                expired_ids.append(sub.id)
            else:
                current_app.logger.warning(f'[Push] send failed: {e}')
        except Exception as e:
            current_app.logger.warning(f'[Push] error: {e}')

    if expired_ids:
        PushSubscription.query.filter(PushSubscription.id.in_(expired_ids)).delete()
        db.session.commit()
