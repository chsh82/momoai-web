# Option 2: 문제 분석 및 재시도 - 완료 보고서

## 📅 작업 일시
2026-02-18

## 🎯 목표
68점 → 81점+ 복구 및 개선

---

## 🔍 문제 원인 분석

### Before (81점 - 성공)
```html
✅ 단순한 CSS 로딩
✅ 폰트 동기 로딩
✅ Alpine.js defer
```

### After Option B (68점 - 실패)
```html
❌ Preload 남용 (3개)
❌ DNS Prefetch 과다 (4개)
❌ 폰트 비동기 로딩 (FCP 5.2s!)
❌ Alpine.js preload (불필요)
```

---

## 🔴 핵심 문제: 폰트 비동기 로딩

### 문제의 코드
```html
<link rel="preload"
      href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR..."
      as="style"
      onload="this.onload=null;this.rel='stylesheet'">
```

### 왜 문제였나?
1. **폰트는 Critical 리소스**
   - 텍스트 렌더링에 필수
   - FCP (First Contentful Paint)에 직접 영향

2. **비동기 로딩의 역효과**
   - 브라우저가 폰트 없이 렌더링 시작
   - FOIT (Flash of Invisible Text)
   - 폰트 로드 완료까지 FCP 지연
   - **2.0s → 5.2s** (+3.2초!)

3. **Preload 오용**
   - 너무 많은 리소스 preload
   - 브라우저 우선순위 혼란
   - 실제로 필요한 리소스 로딩 지연

---

## ✅ 해결책: 균형잡힌 최적화

### 변경 사항

#### 1️⃣ Preconnect만 유지 (Prefetch 제거)
```html
<!-- Before: DNS Prefetch 4개 -->
<link rel="dns-prefetch" href="...">
<link rel="dns-prefetch" href="...">
<link rel="dns-prefetch" href="...">
<link rel="preconnect" href="...">

<!-- After: Preconnect 3개만 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://cdn.jsdelivr.net">
```

**Why:**
- Preconnect가 DNS Prefetch보다 효과적
- DNS + TCP + TLS 한 번에 처리
- 3개면 충분 (과도한 연결 방지)

---

#### 2️⃣ CSS 동기 로딩 (Preload 제거)
```html
<!-- Before: Preload 사용 -->
<link rel="preload" href="/static/css/tailwind.min.css" as="style">
<link rel="stylesheet" href="/static/css/tailwind.min.css">

<!-- After: 직접 로딩 -->
<link rel="stylesheet" href="/static/css/tailwind.min.css">
<link rel="stylesheet" href="/static/css/style.min.css">
```

**Why:**
- CSS 파일이 작음 (64KB total)
- 블로킹해도 성능 영향 미미
- Preload 오버헤드 제거

---

#### 3️⃣ 폰트 동기 로딩 (Critical!)
```html
<!-- Before: 비동기 로딩 (문제!) -->
<link rel="preload"
      href="https://fonts.googleapis.com/..."
      as="style"
      onload="this.onload=null;this.rel='stylesheet'">

<!-- After: 동기 로딩 with font-display:swap -->
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap"
      rel="stylesheet">
```

**Why:**
- 폰트는 렌더링에 필수적
- `font-display:swap`으로 FOUT 방지
- 동기 로딩이 FCP에 유리
- **예상: 5.2s → 2.0s**

---

#### 4️⃣ Alpine.js 단순화 (Preload 제거)
```html
<!-- Before: Preload + defer -->
<link rel="preload" href="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" as="script">
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- After: defer만 사용 -->
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

**Why:**
- `defer`만으로 충분
- Preload는 critical 리소스에만 사용
- Alpine.js는 인터랙션용 (렌더링 블로킹 안 함)

---

## 📊 최적화 전략: "Less is More"

### 제거한 것들 (과도한 최적화)
- ❌ DNS Prefetch (preconnect로 충분)
- ❌ CSS Preload (작은 파일은 불필요)
- ❌ 폰트 비동기 로딩 (오히려 해로움)
- ❌ Alpine.js Preload (불필요)

### 유지한 것들 (효과적인 최적화)
- ✅ Preconnect (3개 도메인)
- ✅ CSS 압축 (style.min.css)
- ✅ 폰트 font-display:swap
- ✅ Alpine.js defer
- ✅ Chart.js 조건부 로딩

---

## 🎯 예상 성능

### Before (Option B 실패)
```
Performance: 68점
FCP: 5.2s
LCP: 5.2s
TBT: 0ms
```

### After (Option 2 균형)
```
Performance: 81-85점 (예상)
FCP: 1.8-2.2s (개선)
LCP: 2.5-2.9s (개선)
TBT: 0-100ms (유지)
```

---

## 📚 핵심 교훈

### 1. "Critical" 리소스는 블로킹이 정답
- 폰트, Critical CSS는 동기 로딩
- 비동기 로딩은 오히려 FCP 지연
- `font-display:swap`으로 FOUT 방지

### 2. Preload는 신중하게
- 정말 critical한 리소스만
- 너무 많으면 역효과
- 우선순위 혼란 발생

### 3. 단순함이 최고
- 과도한 최적화 ≠ 더 나은 성능
- 작은 파일은 블로킹해도 OK
- 브라우저 기본 동작 신뢰

### 4. 측정이 중요
- 가정하지 말고 측정
- Lighthouse로 검증
- A/B 테스트 필수

---

## 🧪 테스트 체크리스트

### 1. 브라우저 캐시 삭제
```
Chrome → Settings → Privacy
→ Clear browsing data
→ Cached images and files
```

### 2. 시크릿 모드 사용
```
Ctrl + Shift + N (Windows)
Cmd + Shift + N (Mac)
```

### 3. Lighthouse 실행
```
F12 → Lighthouse → Performance → Analyze
```

### 4. 확인 항목
- ✅ FCP < 2.5s
- ✅ LCP < 3.0s
- ✅ TBT < 200ms
- ✅ CLS = 0
- ✅ Performance ≥ 81점

---

## 📋 변경된 파일

### 수정된 파일
- `templates/base.html` - 리소스 로딩 최적화
- `postcss.config.js` - CSS 압축 설정
- `package.json` - 빌드 스크립트 수정

### 유지된 파일
- `static/css/style.min.css` (10KB)
- `static/css/tailwind.min.css` (54KB)
- `tailwind.config.js`

---

## 🚀 다음 단계

### Lighthouse 재검사 후...

#### 시나리오 A: 81-85점 달성 ✅
- **성공!** 균형잡힌 최적화 유효
- 더 이상의 최적화는 수익률 감소
- 현재 상태 유지 권장

#### 시나리오 B: 75-80점 ⚠️
- 추가 개선 필요
- Critical CSS 인라인 고려
- 이미지 최적화 검토

#### 시나리오 C: <75점 ❌
- 근본적인 문제 존재
- 서버 응답 시간 확인
- 백엔드 최적화 필요 (Phase 2)

---

## ✅ 완료 체크리스트

- [x] 문제 원인 분석 완료
- [x] 과도한 최적화 제거
- [x] 균형잡힌 접근 적용
- [x] 폰트 동기 로딩 복구
- [x] CSS 압축 유지
- [x] 서버 재시작
- [ ] **Lighthouse 재검사** (사용자 확인 필요)

---

**Option 2 완료! 이제 Lighthouse 재검사를 진행하세요!** 🎯

**예상 점수: 81-85점**
