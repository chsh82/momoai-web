# 🤖 MOMOAI v4.0 업그레이드 프로젝트 계획

## 📋 프로젝트 개요

**목표**: MOMOAI v3.3.0을 다중 사용자 지원, 고급 분석, 커뮤니티 기능을 갖춘 종합 논술 첨삭 플랫폼으로 업그레이드

**버전**: v3.3.0 → v4.0

**시작일**: 2026-02-06

---

## 🎯 핵심 신규 기능

### 1. 사용자 인증 & 역할 관리
- 이메일 회원가입/로그인
- 4가지 역할: 관리자, 강사, 학생, 학부모
- 역할별 맞춤 마이페이지

### 2. 고급 첨삭 관리
- 첨삭 수정 및 재생성 (버전 관리)
- 완료 프로세스 (자동 PDF 생성)
- 첨삭 히스토리 및 검색

### 3. 학생 성장 추적
- 학생별 첨삭 이력
- 점수 변화 그래프
- 18개 지표 레이더 차트 비교

### 4. 도서 데이터베이스
- 도서 등록 및 관리
- 제목/저자/ISBN 검색
- 첨삭과 도서 연결

### 5. 커뮤니티 게시판
- 게시글/댓글/대댓글
- 좋아요 기능
- 구성원 간 소통

---

## 📅 개발 로드맵

### Phase 1: MVP (4-6주) ⭐ 최우선
**목표**: 강사가 실제 사용 가능한 기본 시스템

- ✅ 사용자 인증 (회원가입/로그인)
- ✅ 기본 첨삭 기능 (Claude API 연동)
- ✅ 첨삭 수정/완료 프로세스 (버전 관리)
- ✅ 학생 관리 CRUD
- ✅ 간단한 대시보드
- ✅ 데이터베이스 마이그레이션

**기술 스택**:
- Backend: Flask 3.0+, SQLAlchemy, Flask-Login
- Frontend: Jinja2, Tailwind CSS, Vanilla JS
- Database: PostgreSQL (프로덕션), SQLite (개발)

### Phase 2: 고급 분석 & 히스토리 (3-4주)
**목표**: 학생별 성장 추이 분석

- ✅ 첨삭 히스토리 (검색/필터링)
- ✅ 학생 상세 페이지 (성장 그래프)
- ✅ 대시보드 고도화 (통계 차트)
- ✅ 버전 비교 기능
- ✅ Chart.js 연동

### Phase 3: 커뮤니티 & 도서 (3-4주)
**목표**: 협업 및 참고 자료 관리

- ✅ 도서 관리 시스템
- ✅ 게시판 (게시글/댓글/좋아요)
- ✅ 첨삭-도서 연결

### Phase 4: 학생/학부모 계정 (4-5주) - 향후
**목표**: 다중 역할 시스템

- ✅ 학생 계정 및 마이페이지
- ✅ 학부모 계정 및 자녀 관리
- ✅ 권한 관리 시스템 (RBAC)
- ✅ 알림 시스템

**총 예상 기간**: 14-19주 (약 3.5-5개월)

---

## 🗄️ 데이터베이스 설계 개요

### 핵심 테이블
1. **users** - 사용자 계정 (강사/관리자/학생/학부모)
2. **students** - 학생 정보 (강사가 관리)
3. **essays** - 첨삭 작업
4. **essay_versions** - 첨삭 버전 관리
5. **essay_results** - 첨삭 결과 (HTML/PDF)
6. **essay_scores** - 18개 지표 점수
7. **books** - 도서 정보
8. **posts** - 게시판
9. **comments** - 댓글

상세 설계: [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

---

## 🎨 페이지 구조

### 공통 영역
- `/` - 랜딩 페이지
- `/signup` - 회원가입
- `/login` - 로그인

### 강사 전용 영역 (Phase 1-3)
- `/dashboard` - 대시보드
- `/essays/new` - 새 첨삭 시작
- `/essays/result/:id` - 첨삭 결과 (수정/완료)
- `/essays/history` - 첨삭 히스토리
- `/students` - 학생 관리
- `/students/:id` - 학생 상세 (성장 추이)
- `/books` - 도서 관리
- `/community` - 게시판

### 관리자 영역
- `/admin` - 관리자 대시보드

### 학생/학부모 영역 (Phase 4)
- `/my` - 학생/학부모 마이페이지

---

## 🛠️ 기술 스택

### Backend
```
- Python 3.11+
- Flask 3.0+
- SQLAlchemy (ORM)
- Flask-Login (인증)
- Flask-WTF (폼 관리)
- Flask-Migrate (DB 마이그레이션)
- Anthropic Claude API
```

### Frontend
```
- Jinja2 템플릿
- Tailwind CSS 3.0+
- Vanilla JavaScript / Alpine.js
- Chart.js (차트)
```

### Database
```
- PostgreSQL (프로덕션)
- SQLite (개발/테스트)
```

### DevOps (배포 시)
```
- Docker
- Nginx
- Gunicorn
```

---

## 📂 프로젝트 구조 (예상)

```
momoai_web/
├── app/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy 모델
│   ├── auth/              # 인증 관련
│   ├── essays/            # 첨삭 관련
│   ├── students/          # 학생 관리
│   ├── books/             # 도서 관리
│   ├── community/         # 게시판
│   └── dashboard/         # 대시보드
├── migrations/            # DB 마이그레이션
├── templates/
├── static/
├── config.py
├── requirements.txt
├── DATABASE_SCHEMA.md
├── PROJECT_PLAN.md
└── PHASE1_TASKS.md
```

---

## 🎯 Phase 1 시작

Phase 1 작업 상세: [PHASE1_TASKS.md](./PHASE1_TASKS.md)

---

## 📊 진행 상황 추적

### Phase 1 (MVP)
- [ ] 데이터베이스 마이그레이션
- [ ] 사용자 인증 시스템
- [ ] 학생 관리 CRUD
- [ ] 첨삭 기능 리팩토링
- [ ] 첨삭 수정/완료 프로세스
- [ ] 기본 대시보드
- [ ] 테스트 & 버그 수정

### Phase 2-4
- 추후 업데이트

---

**작성일**: 2026-02-06
**최종 수정일**: 2026-02-06
