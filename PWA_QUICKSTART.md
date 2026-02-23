# MOMOAI PWA - 빠른 참조 가이드

## 🎯 PWA 최적화 완료!
- Service Worker: v4.1.0-optimized
- 커스텀 설치 프롬프트 구현
- 완전한 오프라인 지원

---

## 🧪 빠른 테스트

### 1. 설치 배너 테스트
```bash
# 1. 시크릿 모드로 실행
chrome.exe --incognito http://localhost:5000

# 2. 로그인 후 하단 배너 확인
# 3. "설치" 버튼 클릭
# 4. 설치 다이얼로그 확인
```

### 2. Lighthouse PWA 검사
```
1. F12 → Lighthouse
2. "Progressive Web App" 체크
3. "Analyze page load"
4. 점수 확인 (예상: 90점+)
```

### 3. 오프라인 테스트
```
1. F12 → Network → Offline 체크
2. 페이지 새로고침
3. 오프라인 페이지 표시 확인
```

---

## 🔧 문제 해결

### 배너가 안 보이는 경우
```javascript
// Console에서 실행
localStorage.removeItem('pwa-dismissed');
location.reload();
```

### Service Worker 초기화
```javascript
// Console에서 실행
navigator.serviceWorker.getRegistrations()
  .then(registrations => {
    registrations.forEach(reg => reg.unregister());
  });
location.reload();
```

### 캐시 삭제
```
F12 → Application → Cache Storage
→ 우클릭 → Delete
→ 페이지 새로고침
```

---

## 📁 핵심 파일

### PWA 파일
- `static/sw.js` - Service Worker (v4.1.0-optimized)
- `static/manifest.json` - 앱 매니페스트
- `static/icons/*.png` - 앱 아이콘들

### 템플릿
- `templates/base.html` - PWA 설치 배너 + 스크립트

### 문서
- `PWA_OPTIMIZATION_COMPLETE.md` - 전체 문서
- `PWA_QUICKSTART.md` - 이 파일

---

## 💡 빠른 팁

### Service Worker 버전 업데이트
```javascript
// static/sw.js
const CACHE_NAME = 'momoai-v4.1.1';  // 버전 증가
```

### 배너 다시 표시
```javascript
localStorage.removeItem('pwa-dismissed');
```

### 설치 여부 확인
```javascript
// Console에서 실행
window.matchMedia('(display-mode: standalone)').matches
// true = 설치됨, false = 브라우저
```

---

## 🚀 프로덕션 배포

### 필수 체크리스트
- [ ] HTTPS 활성화 (필수!)
- [ ] manifest.json 경로 확인
- [ ] 아이콘 파일 확인 (72x72 ~ 512x512)
- [ ] sw.js 등록 확인
- [ ] Lighthouse PWA 검사 (90점+)

### 테스트 기기
- [ ] Desktop Chrome
- [ ] Android Chrome
- [ ] iOS Safari (수동 설치)

---

## 📊 지원 브라우저

### 완전 지원 ✅
- Chrome 67+
- Edge 79+
- Opera 64+
- Chrome for Android
- Samsung Internet

### 제한적 지원 ⚠️
- iOS Safari (수동 "홈 화면에 추가")
- Firefox (제한적 PWA 지원)

---

## 🔗 관련 문서

자세한 내용은 다음 문서 참조:
- `PWA_OPTIMIZATION_COMPLETE.md` - 전체 구현 문서
- `PERFORMANCE_FINAL_SUMMARY.md` - 성능 최적화

---

**문의사항이 있으면 위 문서를 참조하세요!**
