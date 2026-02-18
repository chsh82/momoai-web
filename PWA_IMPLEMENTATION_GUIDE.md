# MOMOAI PWA 구현 가이드

## 1. PWA 필수 구성 요소

### 1.1 Manifest 파일 생성
**파일:** `static/manifest.json`

```json
{
  "name": "MOMOAI v4.0 - 교육 관리 시스템",
  "short_name": "MOMOAI",
  "description": "첨삭, 출결, 평가를 한곳에서 관리하는 교육 플랫폼",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#6366f1",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/static/icons/icon-72x72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-96x96.png",
      "sizes": "96x96",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-128x128.png",
      "sizes": "128x128",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-144x144.png",
      "sizes": "144x144",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-152x152.png",
      "sizes": "152x152",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-384x384.png",
      "sizes": "384x384",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

### 1.2 Service Worker 생성
**파일:** `static/sw.js`

```javascript
const CACHE_NAME = 'momoai-v1.0.0';
const urlsToCache = [
  '/',
  '/static/css/styles.css',
  '/static/js/main.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// 설치 이벤트
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// 활성화 이벤트 - 오래된 캐시 삭제
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch 이벤트 - 네트워크 우선, 실패 시 캐시
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .catch(() => caches.match(event.request))
  );
});

// 푸시 알림 수신
self.addEventListener('push', event => {
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// 알림 클릭 이벤트
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
```

### 1.3 base.html 헤더에 추가

```html
<!-- PWA Manifest -->
<link rel="manifest" href="{{ url_for('static', filename='manifest.json') }}">

<!-- iOS Meta Tags -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MOMOAI">
<link rel="apple-touch-icon" href="{{ url_for('static', filename='icons/icon-192x192.png') }}">

<!-- Theme Color -->
<meta name="theme-color" content="#6366f1">
```

### 1.4 Service Worker 등록 스크립트

```html
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(registration => {
        console.log('Service Worker registered:', registration);
      })
      .catch(error => {
        console.log('Service Worker registration failed:', error);
      });
  });
}
</script>
```

---

## 2. 웹 푸시 알림 구현

### 2.1 의존성 설치
```bash
pip install pywebpush
```

### 2.2 VAPID 키 생성
**파일:** `generate_vapid_keys.py`

```python
from pywebpush import vapid_admin

vapid_private_key = vapid_admin.Vapid().private_key.export_pem()
vapid_public_key = vapid_admin.Vapid().public_key.export_pem()

print("VAPID_PRIVATE_KEY =", vapid_private_key.decode('utf-8'))
print("VAPID_PUBLIC_KEY =", vapid_public_key.decode('utf-8'))
```

실행: `python generate_vapid_keys.py`

### 2.3 config.py에 추가
```python
# 푸시 알림 설정
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY') or 'your-private-key'
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY') or 'your-public-key'
VAPID_CLAIMS = {
    "sub": "mailto:contact@momoai.com"
}
```

### 2.4 푸시 구독 모델
**파일:** `app/models/push_subscription.py`

```python
from app import db
from datetime import datetime

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='push_subscriptions')
```

### 2.5 푸시 알림 라우트
**파일:** `app/notifications/routes.py` (추가)

```python
from flask import jsonify, request
from flask_login import login_required, current_user
from pywebpush import webpush, WebPushException
from app import db
from app.models.push_subscription import PushSubscription
import json

@notifications_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe_push():
    """푸시 알림 구독"""
    subscription_info = request.get_json()

    # 기존 구독 확인
    existing = PushSubscription.query.filter_by(
        user_id=current_user.user_id,
        endpoint=subscription_info['endpoint']
    ).first()

    if not existing:
        subscription = PushSubscription(
            user_id=current_user.user_id,
            endpoint=subscription_info['endpoint'],
            p256dh=subscription_info['keys']['p256dh'],
            auth=subscription_info['keys']['auth']
        )
        db.session.add(subscription)
        db.session.commit()

    return jsonify({'success': True})

@notifications_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe_push():
    """푸시 알림 구독 해제"""
    subscription_info = request.get_json()

    subscription = PushSubscription.query.filter_by(
        user_id=current_user.user_id,
        endpoint=subscription_info['endpoint']
    ).first()

    if subscription:
        db.session.delete(subscription)
        db.session.commit()

    return jsonify({'success': True})

def send_push_notification(user_id, title, body, url='/'):
    """사용자에게 푸시 알림 전송"""
    from app import app

    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth
                    }
                },
                data=json.dumps({
                    "title": title,
                    "body": body,
                    "url": url
                }),
                vapid_private_key=app.config['VAPID_PRIVATE_KEY'],
                vapid_claims=app.config['VAPID_CLAIMS']
            )
        except WebPushException as e:
            print(f"Push failed: {e}")
            # 만료된 구독은 삭제
            if e.response and e.response.status_code in [404, 410]:
                db.session.delete(subscription)
                db.session.commit()
```

### 2.6 프론트엔드 구독 스크립트
**파일:** `static/js/push-notifications.js`

```javascript
const publicVapidKey = '{{ config.VAPID_PUBLIC_KEY }}';

// URL-safe base64 변환
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// 푸시 알림 구독
async function subscribePush() {
  try {
    // Service Worker 등록 확인
    const registration = await navigator.serviceWorker.ready;

    // 푸시 구독
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
    });

    // 서버에 구독 정보 전송
    await fetch('/notifications/subscribe', {
      method: 'POST',
      body: JSON.stringify(subscription),
      headers: {
        'Content-Type': 'application/json'
      }
    });

    console.log('Push notification subscribed');
    return true;
  } catch (error) {
    console.error('Push subscription failed:', error);
    return false;
  }
}

// 알림 권한 요청
async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    console.log('This browser does not support notifications');
    return false;
  }

  if (Notification.permission === 'granted') {
    return subscribePush();
  }

  if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      return subscribePush();
    }
  }

  return false;
}

// 페이지 로드 시 자동 실행
if ('serviceWorker' in navigator && 'PushManager' in window) {
  // 로그인한 사용자만
  if (document.body.classList.contains('user-logged-in')) {
    requestNotificationPermission();
  }
}
```

---

## 3. 기존 알림 시스템과 통합

**파일:** `app/notifications/routes.py` (수정)

기존 `send_notification()` 함수에 푸시 알림 추가:

```python
def send_notification(user_id, notification_type, title, message, link_url=None,
                     related_user_id=None, related_entity_type=None, related_entity_id=None):
    """알림 생성 및 전송 (웹 + 푸시)"""

    # 기존 DB 알림 생성
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        link_url=link_url,
        related_user_id=related_user_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id
    )
    db.session.add(notification)
    db.session.commit()

    # 푸시 알림 전송 (비동기)
    send_push_notification(user_id, title, message, link_url or '/')

    return notification
```

---

## 4. 사용자 안내 화면

**설치 가이드 페이지 추가:**

```html
<!-- templates/pwa_install.html -->
<div class="card-momo">
    <h2 class="text-2xl font-bold mb-4">📱 앱처럼 사용하기</h2>

    <div class="space-y-6">
        <!-- Android (Chrome) -->
        <div>
            <h3 class="font-bold text-lg mb-2">Android (Chrome)</h3>
            <ol class="list-decimal ml-6 space-y-2">
                <li>Chrome에서 MOMOAI 웹사이트 접속</li>
                <li>우측 상단 메뉴(⋮) 클릭</li>
                <li>"홈 화면에 추가" 선택</li>
                <li>"추가" 버튼 클릭</li>
            </ol>
        </div>

        <!-- iOS (Safari) -->
        <div>
            <h3 class="font-bold text-lg mb-2">iPhone/iPad (Safari)</h3>
            <ol class="list-decimal ml-6 space-y-2">
                <li>Safari에서 MOMOAI 웹사이트 접속</li>
                <li>하단 공유 버튼(↑) 클릭</li>
                <li>"홈 화면에 추가" 선택</li>
                <li>"추가" 버튼 클릭</li>
            </ol>
            <p class="text-sm text-gray-600 mt-2">
                ⚠️ iOS는 반드시 Safari 사용 필요 (Chrome 불가)
            </p>
        </div>

        <!-- PC -->
        <div>
            <h3 class="font-bold text-lg mb-2">PC (Chrome/Edge)</h3>
            <ol class="list-decimal ml-6 space-y-2">
                <li>주소창 우측의 설치 아이콘(⊕) 클릭</li>
                <li>또는 메뉴 → "MOMOAI 설치..." 클릭</li>
            </ol>
        </div>
    </div>

    <div class="mt-6 bg-blue-50 p-4 rounded">
        <p class="text-sm">
            💡 <strong>알림 받기:</strong> 홈 화면에 추가 후 첫 로그인 시
            알림 권한을 허용하면 실시간 푸시 알림을 받을 수 있습니다.
        </p>
    </div>
</div>
```

---

## 5. 아이콘 생성

**필요한 크기:** 72, 96, 128, 144, 152, 192, 384, 512px

**온라인 도구:**
- https://realfavicongenerator.net/
- https://www.pwabuilder.com/imageGenerator

**저장 위치:** `static/icons/`

---

## 6. HTTPS 필수

PWA와 푸시 알림은 **HTTPS에서만 동작**합니다.

**배포 옵션:**
1. **Cloudflare Pages** (무료, 자동 HTTPS)
2. **Heroku** (무료 티어, 자동 HTTPS)
3. **AWS EC2 + Let's Encrypt** (무료 SSL)
4. **PythonAnywhere** (유료, HTTPS 포함)

---

## 7. 테스트

### 로컬 테스트 (HTTPS 시뮬레이션)
```bash
# ngrok 사용
ngrok http 5000
```

### PWA 체크리스트
- [ ] manifest.json 작성
- [ ] Service Worker 등록
- [ ] HTTPS 적용
- [ ] 아이콘 준비 (모든 크기)
- [ ] 설치 프롬프트 테스트
- [ ] 오프라인 동작 확인
- [ ] 푸시 알림 테스트

### Chrome DevTools 확인
1. F12 → Application 탭
2. Manifest 섹션 확인
3. Service Workers 확인
4. Lighthouse 실행 (PWA 점수 확인)

---

## 8. 마이그레이션

```bash
flask db migrate -m "Add push subscription table"
flask db upgrade
```

---

## 참고 자료
- [MDN PWA Guide](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [Web.dev PWA](https://web.dev/progressive-web-apps/)
- [pywebpush Documentation](https://github.com/web-push-libs/pywebpush)
