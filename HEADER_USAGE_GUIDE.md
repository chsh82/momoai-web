# 동적 페이지 헤더 사용 가이드

## 개요
각 페이지의 헤더에 동적 제목과 서브타이틀을 표시할 수 있습니다.

## 기본 사용법

### 1. 페이지 제목만 설정
```jinja
{% extends "base.html" %}

{% block page_title %}📊 대시보드{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
{% endblock %}
```

### 2. 제목 + 서브타이틀 설정
```jinja
{% extends "base.html" %}

{% block page_title %}👤 학생 관리{% endblock %}

{% block page_subtitle %}
<span class="text-sm text-white text-opacity-70 ml-3">전체 학생 목록</span>
{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
{% endblock %}
```

### 3. 동적 데이터 활용
```jinja
{% extends "base.html" %}

{% block page_title %}👤 {{ student.name }} 학생 프로필{% endblock %}

{% block page_subtitle %}
<span class="text-sm text-white text-opacity-70 ml-3">{{ student.grade }} · {{ student.student_id[:8] }}</span>
{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
{% endblock %}
```

## 이모지 추천

| 페이지 유형 | 이모지 | 예시 |
|------------|--------|------|
| 대시보드 | 📊 | 📊 대시보드 |
| 학생 관리 | 👤 | 👤 학생 관리 |
| 수업 관리 | 📚 | 📚 수업 관리 |
| 과제/첨삭 | ✍️ | ✍️ 과제 첨삭 |
| 성적/평가 | 📈 | 📈 성적 관리 |
| 결제 | 💰 | 💰 결제 관리 |
| 알림 | 🔔 | 🔔 알림 센터 |
| 설정 | ⚙️ | ⚙️ 설정 |
| 통계/분석 | 📉 | 📉 통계 분석 |
| 커뮤니티 | 💬 | 💬 커뮤니티 |
| 자료실 | 📁 | 📁 학습 자료실 |
| AI 기능 | 🤖 | 🤖 AI 분석 |
| 상담 | 🗣️ | 🗣️ 상담 기록 |

## 커스텀 헤더 액션 추가

헤더 우측에 커스텀 버튼이나 액션을 추가할 수 있습니다:

```jinja
{% extends "base.html" %}

{% block page_title %}👤 학생 목록{% endblock %}

{% block header_actions %}
<a href="{{ url_for('students.new') }}"
   class="flex items-center gap-2 px-4 py-2 bg-white bg-opacity-20 hover:bg-opacity-30 text-white rounded-button transition">
    <span>➕</span>
    <span class="text-sm font-medium">학생 추가</span>
</a>
<a href="{{ url_for('search.index') }}"
   class="flex items-center gap-2 px-4 py-2 text-white text-opacity-80 hover:text-white rounded-button hover:bg-white hover:bg-opacity-10 transition">
    <span class="text-xl">🔍</span>
    <span class="text-sm font-medium">검색</span>
</a>
{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
{% endblock %}
```

## 스타일 가이드

### 제목 스타일
- **클래스**: 자동 적용 (`text-header text-white`)
- **폰트**: Noto Sans KR, 20px, weight 800
- **색상**: 흰색

### 서브타이틀 스타일
- **권장 클래스**: `text-sm text-white text-opacity-70 ml-3`
- **폰트**: Noto Sans KR, 14px
- **색상**: 흰색 70% 투명도
- **간격**: 왼쪽 여백 12px

### 액션 버튼 스타일
- **기본**: `text-white text-opacity-80 hover:text-white rounded-button hover:bg-white hover:bg-opacity-10`
- **강조**: `bg-white bg-opacity-20 hover:bg-opacity-30 text-white rounded-button`

## 기본값

`page_title` 블록을 설정하지 않으면 기본값으로 "대시보드"가 표시됩니다.

## 적용 예시

### ✅ 이미 적용된 페이지
1. `templates/admin/student_risk_analysis.html` - 🤖 학생 위험도 분석
2. `templates/admin/student_profile.html` - 👤 학생 프로필
3. `templates/teacher/student_detail.html` - 👤 학생 정보

### 📝 적용 권장 페이지
- 모든 대시보드 페이지
- 목록 페이지 (학생 목록, 수업 목록 등)
- 상세 페이지 (학생 상세, 수업 상세 등)
- 설정 페이지
- 통계/리포트 페이지

## 마이그레이션 팁

기존 페이지를 업데이트할 때:
1. 페이지 내부의 중복 헤더 제거
2. `page_title` 블록 추가
3. 필요시 `page_subtitle` 블록 추가
4. 버튼들이 있다면 `header_actions` 블록으로 이동 고려

---

**모모의 책장 디자인 시스템**
마지막 업데이트: 2026-02-18
