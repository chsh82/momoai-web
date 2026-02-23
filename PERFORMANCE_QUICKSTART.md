# MOMOAI v4.0 성능 최적화 - 빠른 참조 가이드

## 🎯 최종 성과
- **Performance**: 62점 → **84점** (+22점)
- **Accessibility**: 78점 → **97점** (+19점)
- **파일 크기**: 69% 감소

---

## 🔧 일상적인 작업

### CSS 변경 시
```bash
# 1. CSS 파일 수정
# 2. 빌드
npm run build:css

# 3. 서버 재시작
python run.py
```

### 개발 중 (CSS 자동 빌드)
```bash
# 터미널 1: CSS 자동 빌드
npm run watch:css

# 터미널 2: 서버 실행
python run.py
```

---

## 📊 성능 테스트

### Lighthouse 검사
1. 시크릿 모드로 http://localhost:5000 접속
2. **F12** → **Lighthouse** 탭
3. **Performance** 체크
4. "Analyze page load"

### 브라우저 캐시 삭제
```
Chrome → Settings → Privacy
→ Clear browsing data
→ Cached images and files
```

---

## 🚨 문제 해결

### 디자인이 깨진 경우
```bash
# CSS 재빌드
npm run build:css

# 브라우저 캐시 삭제 후 Ctrl+Shift+R
```

### 성능이 느린 경우
1. Lighthouse 재검사
2. 캐시 삭제 후 재시도
3. 네트워크 throttling 확인

---

## 📁 핵심 파일

### CSS 파일
- `static/css/input.css` - Tailwind 소스
- `static/css/tailwind.min.css` - 빌드된 Tailwind (54KB)
- `static/css/style.css` - 디자인 시스템 소스
- `static/css/style.min.css` - 빌드된 디자인 시스템 (10KB)

### 설정 파일
- `tailwind.config.js` - Tailwind 설정
- `postcss.config.js` - CSS 압축 설정
- `package.json` - npm 빌드 스크립트

### 템플릿
- `templates/base.html` - 리소스 로딩 최적화

---

## 💡 빠른 팁

### Chart.js 사용하는 페이지
```html
{% extends "base.html" %}

{% block chart_js %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
{% endblock %}
```

### 캐시 무효화 (CSS 변경 시)
```html
<link rel="stylesheet" href="/static/css/style.min.css?v=1.1">
```

### 이미지 최적화
```python
from app.utils.performance import optimize_image
optimize_image(file_path, max_width=1920, quality=85)
```

---

## 📚 상세 문서

자세한 내용은 다음 문서 참조:
- `PERFORMANCE_FINAL_SUMMARY.md` - 전체 요약
- `PERFORMANCE_OPTION2_ANALYSIS.md` - 최적화 분석

---

**문의사항이 있으면 위 문서를 참조하세요!**
