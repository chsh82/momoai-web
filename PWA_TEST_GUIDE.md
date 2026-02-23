# MOMOAI v4.0 PWA 테스트 가이드

## 테스트 환경
- URL: http://localhost:5000
- 계정: admin@momoai.com / admin123
- 브라우저: Chrome, Edge, Firefox, Safari 모두 가능

---

## 1. Service Worker 등록 확인

### Chrome/Edge에서:
1. 개발자 도구 열기 (F12)
2. **Application** 탭 클릭
3. 왼쪽 메뉴에서 **Service Workers** 클릭
4. 확인 사항:
   - ✅ Status: **activated and is running**
   - ✅ Source: **/static/sw.js**
   - ✅ Update on reload 체크

### Firefox에서:
1. 개발자 도구 열기 (F12)
2. **Application** 탭 클릭 (또는 about:debugging#/runtime/this-firefox)
3. Service Workers 섹션 확인

### Console에서 확인:
```javascript
// Console 탭에서 실행
navigator.serviceWorker.getRegistrations().then(registrations => {
    console.log('Service Worker 등록 개수:', registrations.length);
    registrations.forEach(reg => console.log('SW Scope:', reg.scope));
});
```

**예상 결과:**
- Service Worker가 1개 등록되어 있어야 함
- Scope: http://localhost:5000/

---

## 2. Manifest 파일 확인

### Chrome/Edge에서:
1. 개발자 도구 > **Application** 탭
2. 왼쪽 메뉴에서 **Manifest** 클릭
3. 확인 사항:
   - ✅ Name: "MOMOAI v4.0 - 교육 관리 시스템"
   - ✅ Short name: "MOMOAI"
   - ✅ Start URL: "/"
   - ✅ Display: "standalone"
   - ✅ Theme color: "#6366f1" (보라색)
   - ✅ Icons: 8개 (72x72 ~ 512x512)

### Icons 미리보기:
- 각 아이콘이 보라색 원형 배경에 "M" 글자가 있어야 함

---

## 3. PWA 설치 가능 여부 확인

### Chrome/Edge에서:
1. 주소창 오른쪽에 **설치 아이콘** (⊕ 또는 컴퓨터 모양) 확인
2. 아이콘이 보이면 클릭하여 설치 가능!

### 수동 설치:
1. 개발자 도구 > Application > Manifest
2. 아래쪽에 "Add to home screen" 또는 "Install" 버튼 클릭

### 설치 후 확인:
- Windows: 시작 메뉴에 "MOMOAI" 앱 추가됨
- Mac: Launchpad에 추가됨
- Linux: 애플리케이션 메뉴에 추가됨

---

## 4. 오프라인 캐싱 테스트

### 방법 1: Network 탭에서 시뮬레이션
1. 개발자 도구 > **Network** 탭
2. 상단에 **Offline** 체크박스 체크
3. 페이지 새로고침 (F5)
4. **예상 결과:** 페이지가 정상적으로 로드되어야 함 (캐시에서)

### 방법 2: Service Worker에서 확인
1. Application > Service Workers
2. **Offline** 체크박스 체크
3. 페이지 새로고침

### 캐시된 리소스 확인:
1. Application > Cache Storage
2. **momoai-v4.0.0** 캐시 확인
3. 캐시된 파일들:
   - / (메인 페이지)
   - /static/css/style.css
   - 아이콘 파일들

---

## 5. 푸시 알림 권한 요청 (선택사항)

### Console에서 테스트:
```javascript
// 알림 권한 요청
Notification.requestPermission().then(permission => {
    console.log('알림 권한:', permission);
});

// 테스트 알림 보내기
if (Notification.permission === 'granted') {
    new Notification('MOMOAI 테스트', {
        body: '푸시 알림이 정상적으로 작동합니다!',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png'
    });
}
```

---

## 6. 반응형 디자인 확인

### 모바일 시뮬레이션:
1. 개발자 도구에서 **Toggle device toolbar** (Ctrl+Shift+M)
2. 다양한 기기에서 테스트:
   - iPhone 12 Pro
   - iPad
   - Samsung Galaxy S20
   - 사용자 정의 크기

### 확인 사항:
- ✅ 레이아웃이 화면에 맞게 조정됨
- ✅ 메뉴와 버튼이 터치하기 적절한 크기
- ✅ 텍스트가 읽기 좋은 크기
- ✅ 스크롤이 자연스러움

---

## 7. 성능 측정 (Lighthouse)

### Chrome에서:
1. 개발자 도구 > **Lighthouse** 탭
2. Categories에서 모두 선택:
   - ✅ Performance
   - ✅ Accessibility
   - ✅ Best Practices
   - ✅ SEO
   - ✅ **Progressive Web App**
3. **Generate report** 클릭

### PWA 체크리스트 확인:
- ✅ Installable
- ✅ PWA optimized
- ✅ Has a service worker
- ✅ Has a web app manifest
- ✅ Configured for a custom splash screen
- ✅ Sets a theme color

---

## 8. iOS/Safari 테스트 (있는 경우)

### iPhone/iPad에서:
1. Safari로 http://[your-ip]:5000 접속
2. 공유 버튼 (↑) 클릭
3. "홈 화면에 추가" 선택
4. 추가 후 홈 화면에서 앱 아이콘 확인

### 확인 사항:
- ✅ 앱 아이콘이 표시됨
- ✅ 앱 이름: "MOMOAI"
- ✅ 전체 화면 모드로 실행 (주소창 없음)
- ✅ 상태 바 색상이 적용됨

---

## 9. 실제 모바일 기기에서 테스트

### 네트워크 설정:
1. 서버가 실행 중인 PC의 IP 주소 확인:
   ```bash
   ipconfig  # Windows
   ifconfig  # Mac/Linux
   ```
2. 모바일 기기를 같은 Wi-Fi에 연결
3. 모바일 브라우저에서 접속: http://[PC-IP]:5000

### Android에서:
1. Chrome으로 접속
2. 메뉴 > "홈 화면에 추가" 또는 "앱 설치"
3. 설치 후 앱 서랍에서 확인

---

## 트러블슈팅

### Service Worker가 등록되지 않을 때:
1. 브라우저 캐시 완전 삭제 (Ctrl+Shift+Delete)
2. 하드 새로고침 (Ctrl+Shift+R)
3. Service Worker Unregister 후 재등록:
   ```javascript
   navigator.serviceWorker.getRegistrations().then(registrations => {
       registrations.forEach(reg => reg.unregister());
   });
   ```
4. 페이지 새로고침

### PWA 설치 아이콘이 안 보일 때:
- HTTPS가 아닌 localhost에서는 정상 작동
- manifest.json이 올바른지 확인
- Console에서 에러 메시지 확인

### 오프라인 모드가 작동하지 않을 때:
- Service Worker가 활성화되어 있는지 확인
- Cache Storage에 파일들이 있는지 확인
- sw.js에 문법 에러가 없는지 확인

---

## 테스트 체크리스트

- [ ] Service Worker 등록 확인
- [ ] Manifest 파일 로드 확인
- [ ] 아이콘 8개 모두 표시됨
- [ ] PWA 설치 가능 (설치 버튼 표시)
- [ ] 오프라인 모드에서 페이지 로드 성공
- [ ] Cache Storage에 파일 저장됨
- [ ] 푸시 알림 권한 요청 작동
- [ ] 테스트 알림 전송 성공
- [ ] Lighthouse PWA 점수 확인
- [ ] 모바일 반응형 디자인 확인
- [ ] (선택) iOS Safari에서 홈 화면 추가
- [ ] (선택) Android Chrome에서 앱 설치

---

## 완료!

모든 테스트가 통과하면 MOMOAI v4.0은 완전한 PWA로 작동합니다! 🎉

문제가 발생하면 Console 탭의 에러 메시지를 확인하세요.
