const CACHE_NAME = 'momoai-v4.1.0-optimized';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/css/tailwind.min.css',  // ✅ 최적화된 Tailwind
  '/static/css/style.min.css',     // ✅ 최적화된 디자인 시스템
  '/static/icons/icon-72x72.png',
  '/static/icons/icon-96x96.png',
  '/static/icons/icon-128x128.png',
  '/static/icons/icon-144x144.png',
  '/static/icons/icon-152x152.png',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-384x384.png',
  '/static/icons/icon-512x512.png'
];

// 캐시할 CDN 리소스 (최적화 반영)
const CDN_URLS = [
  // TailwindCSS CDN 제거됨! (빌드 파일 사용)
  // Chart.js는 조건부 로딩 (필요한 페이지만)
  'https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
  'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap'
];

// 오프라인 폴백 HTML
const OFFLINE_HTML = `
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>오프라인 - MOMOAI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 60px 40px;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .icon {
            width: 120px;
            height: 120px;
            margin: 0 auto 30px;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            border-radius: 26px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 72px;
            font-weight: 900;
            color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 15px;
        }
        p {
            color: #666;
            line-height: 1.8;
            margin-bottom: 30px;
            font-size: 16px;
        }
        .btn {
            display: inline-block;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            padding: 15px 40px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            transition: transform 0.2s;
            cursor: pointer;
            border: none;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3);
        }
        .status {
            margin-top: 30px;
            padding: 15px;
            background: #f0f4ff;
            border-radius: 10px;
            color: #6366f1;
            font-size: 14px;
        }
        .version {
            margin-top: 20px;
            font-size: 12px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">📚</div>
        <h1>오프라인 상태입니다</h1>
        <p>
            인터넷 연결이 필요합니다.<br>
            네트워크 연결을 확인한 후<br>
            아래 버튼을 눌러 다시 시도해주세요.
        </p>
        <button class="btn" onclick="location.reload()">
            🔄 다시 시도
        </button>
        <div class="status">
            💡 일부 캐시된 페이지는 오프라인에서도 이용 가능합니다
        </div>
        <div class="version">MOMOAI v4.1.0 (Optimized)</div>
    </div>
</body>
</html>
`;

const OFFLINE_URL = '/offline.html';

// 설치 이벤트
self.addEventListener('install', event => {
  console.log('[SW v4.1.0] Installing... (Performance Optimized)');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Caching optimized resources');
        // 오프라인 페이지를 Response 객체로 캐시
        cache.put(OFFLINE_URL, new Response(OFFLINE_HTML, {
          headers: { 'Content-Type': 'text/html' }
        }));

        // 기본 리소스 캐시
        const cachePromises = [
          cache.addAll(urlsToCache).catch(err => {
            console.error('[SW] Failed to cache app shell:', err);
          }),
          // CDN 리소스 캐시 (실패해도 계속 진행)
          ...CDN_URLS.map(url =>
            fetch(url, { mode: 'cors', cache: 'no-cache' })
              .then(response => {
                if (response.ok) {
                  return cache.put(url, response);
                }
              })
              .catch(err => {
                console.warn('[SW] Failed to cache CDN:', url);
              })
          )
        ];

        return Promise.all(cachePromises);
      })
      .catch(err => {
        console.error('[SW] Install failed:', err);
      })
  );
  self.skipWaiting();
});

// 활성화 이벤트 - 오래된 캐시 삭제
self.addEventListener('activate', event => {
  console.log('[SW v4.1.0] Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Fetch 이벤트 - Stale-While-Revalidate 전략
self.addEventListener('fetch', event => {
  // POST 요청은 캐시하지 않음
  if (event.request.method !== 'GET') {
    return;
  }

  // Chrome extension 요청 무시
  if (event.request.url.startsWith('chrome-extension://')) {
    return;
  }

  // HTML 페이지 요청 (navigation)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // 성공하면 캐시에 저장하고 반환
          if (response.status === 200) {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // 네트워크 실패 시 캐시 확인
          return caches.match(event.request)
            .then(cachedResponse => {
              if (cachedResponse) {
                return cachedResponse;
              }
              // 캐시에도 없으면 오프라인 페이지 표시
              return caches.match(OFFLINE_URL);
            });
        })
    );
    return;
  }

  // 정적 리소스 (CSS, JS, 이미지, 폰트): Stale-While-Revalidate
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        const fetchPromise = fetch(event.request)
          .then(response => {
            // 유효한 응답이면 캐시 업데이트
            if (response && response.status === 200) {
              const responseToCache = response.clone();
              caches.open(CACHE_NAME).then(cache => {
                cache.put(event.request, responseToCache);
              });
            }
            return response;
          })
          .catch(() => {
            // 네트워크 실패는 조용히 무시 (캐시 사용)
            return null;
          });

        // 캐시가 있으면 즉시 반환하고 백그라운드 업데이트
        if (cachedResponse) {
          return cachedResponse;
        }

        // 캐시 없으면 네트워크 응답 기다림
        return fetchPromise.then(response => {
          if (response) {
            return response;
          }
          // 완전히 실패하면 503 반환
          return new Response('Service Unavailable', {
            status: 503,
            statusText: 'Service Unavailable'
          });
        });
      })
  );
});

// 푸시 알림 수신
self.addEventListener('push', event => {
  console.log('[SW] Push notification received');

  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = {
        title: 'MOMOAI 알림',
        body: event.data.text()
      };
    }
  }

  const title = data.title || 'MOMOAI 알림';
  const options = {
    body: data.body || '새로운 알림이 있습니다.',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-96x96.png',
    vibrate: [200, 100, 200],
    tag: data.tag || 'momoai-notification',
    requireInteraction: data.requireInteraction || false,
    data: {
      url: data.url || '/',
      dateOfArrival: Date.now()
    },
    actions: [
      {
        action: 'open',
        title: '확인'
      },
      {
        action: 'close',
        title: '닫기'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// 알림 클릭 이벤트
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked:', event.action);
  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // 알림 클릭 시 해당 URL 열기
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(windowClients => {
        const url = event.notification.data.url || '/';
        const absoluteUrl = new URL(url, self.location.origin).href;

        // 이미 열린 창이 있으면 포커스
        for (let client of windowClients) {
          if (client.url === absoluteUrl && 'focus' in client) {
            return client.focus();
          }
        }

        // 없으면 새 창 열기
        if (clients.openWindow) {
          return clients.openWindow(absoluteUrl);
        }
      })
  );
});

// 백그라운드 동기화 (향후 확장 가능)
self.addEventListener('sync', event => {
  console.log('[SW] Background sync:', event.tag);

  if (event.tag === 'sync-notifications') {
    event.waitUntil(
      // 여기에 동기화 로직 추가
      Promise.resolve()
    );
  }
});

// 주기적 백그라운드 동기화 (Chrome 80+)
self.addEventListener('periodicsync', event => {
  console.log('[SW] Periodic sync:', event.tag);

  if (event.tag === 'content-sync') {
    event.waitUntil(
      // 여기에 주기적 동기화 로직 추가
      Promise.resolve()
    );
  }
});

console.log('[SW v4.1.0] Service Worker loaded (Performance Optimized)');
