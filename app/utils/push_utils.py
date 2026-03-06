# -*- coding: utf-8 -*-
"""Web Push 알림 발송 유틸리티"""
import json
import threading


def send_push_to_user(user_id, title, body, url='/notifications'):
    """특정 사용자의 모든 Push 구독에 알림 발송 (백그라운드 스레드)"""
    from flask import current_app
    app = current_app._get_current_object()
    t = threading.Thread(target=_do_send_push, args=(app, user_id, title, body, url), daemon=True)
    t.start()


def _do_send_push(app, user_id, title, body, url):
    """실제 Push 발송 (백그라운드에서 실행)"""
    with app.app_context():
        from app.models.push_subscription import PushSubscription
        from app.models import db

        vapid_private_key = app.config.get('VAPID_PRIVATE_KEY')
        vapid_claims_sub = app.config.get('VAPID_CLAIMS_SUB', 'mailto:contact@momoai.kr')

        if not vapid_private_key:
            app.logger.warning('[Push] VAPID_PRIVATE_KEY not set — skipping push')
            return

        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            app.logger.warning('[Push] pywebpush not installed — skipping push')
            return

        subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
        if not subscriptions:
            app.logger.info(f'[Push] No subscriptions for user {user_id}')
            return

        app.logger.info(f'[Push] Sending to user {user_id}: {len(subscriptions)} subscription(s)')
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
                app.logger.info(f'[Push] Sent OK to sub #{sub.id}')
            except WebPushException as e:
                status = e.response.status_code if e.response else 'no-response'
                app.logger.warning(f'[Push] WebPushException sub#{sub.id} status={status}: {e}')
                if e.response and e.response.status_code in (400, 403, 404, 410):
                    expired_ids.append(sub.id)
            except Exception as e:
                app.logger.warning(f'[Push] Unexpected error sub#{sub.id}: {e}')

        if expired_ids:
            app.logger.info(f'[Push] Removing {len(expired_ids)} expired subscription(s)')
            PushSubscription.query.filter(PushSubscription.id.in_(expired_ids)).delete()
            db.session.commit()
