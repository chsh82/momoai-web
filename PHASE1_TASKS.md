# 📋 Phase 1: MVP 작업 목록

## 🎯 Phase 1 목표
**강사 1명이 실제로 사용할 수 있는 기본 시스템 구축**

**예상 기간**: 4-6주

---

## ✅ 작업 체크리스트

### 🗄️ 1. 데이터베이스 마이그레이션 (1주)

#### 1.1 SQLAlchemy 설정
- [ ] Flask-SQLAlchemy 설치 및 설정
- [ ] Flask-Migrate 설치 및 초기화
- [ ] config.py에 DB 설정 추가 (SQLite dev, PostgreSQL prod)

#### 1.2 모델 작성
- [ ] `models/user.py` - User 모델
- [ ] `models/student.py` - Student 모델
- [ ] `models/essay.py` - Essay, EssayVersion, EssayResult 모델
- [ ] `models/essay_score.py` - EssayScore, EssayNote 모델
- [ ] relationships 설정

#### 1.3 마이그레이션
- [ ] 초기 마이그레이션 생성 (`flask db init`)
- [ ] 마이그레이션 실행 (`flask db migrate`, `flask db upgrade`)
- [ ] 기존 데이터 이전 스크립트 작성
- [ ] 테스트 데이터 시드 스크립트

---

### 🔐 2. 사용자 인증 시스템 (1주)

#### 2.1 Flask-Login 설정
- [ ] Flask-Login 설치 및 설정
- [ ] LoginManager 초기화
- [ ] User 모델에 UserMixin 적용

#### 2.2 인증 블루프린트 생성
- [ ] `app/auth/__init__.py`
- [ ] `app/auth/routes.py`
- [ ] `app/auth/forms.py` (Flask-WTF)

#### 2.3 회원가입
- [ ] 회원가입 폼 (이메일, 비밀번호, 이름)
- [ ] 비밀번호 해싱 (werkzeug.security)
- [ ] 이메일 중복 체크
- [ ] 회원가입 라우트 (`/signup`)
- [ ] 회원가입 템플릿

#### 2.4 로그인/로그아웃
- [ ] 로그인 폼
- [ ] 로그인 라우트 (`/login`)
- [ ] 로그아웃 라우트 (`/logout`)
- [ ] 로그인 템플릿
- [ ] 세션 관리

#### 2.5 비밀번호 재설정
- [ ] 비밀번호 재설정 요청 폼
- [ ] 비밀번호 재설정 라우트 (`/reset-password`)
- [ ] 이메일 발송 (선택적, 일단 보류 가능)

#### 2.6 권한 데코레이터
- [ ] `@login_required` 적용
- [ ] `@role_required('teacher')` 데코레이터 작성

---

### 👥 3. 학생 관리 CRUD (0.5주)

#### 3.1 학생 블루프린트
- [ ] `app/students/__init__.py`
- [ ] `app/students/routes.py`
- [ ] `app/students/forms.py`

#### 3.2 학생 목록
- [ ] 학생 목록 라우트 (`/students`)
- [ ] 학생 목록 템플릿 (카드/테이블뷰)
- [ ] 검색 기능 (이름)

#### 3.3 학생 추가
- [ ] 학생 추가 폼 (이름, 학년, 이메일, 전화번호)
- [ ] 학생 추가 라우트 (`/students/new`)
- [ ] 학생 추가 템플릿

#### 3.4 학생 상세
- [ ] 학생 상세 라우트 (`/students/:id`)
- [ ] 학생 상세 템플릿 (기본 정보 표시)

#### 3.5 학생 수정/삭제
- [ ] 학생 수정 라우트 (`/students/:id/edit`)
- [ ] 학생 수정 템플릿
- [ ] 학생 삭제 라우트 (POST `/students/:id/delete`)
- [ ] 삭제 확인 모달

---

### ✍️ 4. 첨삭 기능 리팩토링 (1.5주)

#### 4.1 첨삭 블루프린트
- [ ] `app/essays/__init__.py`
- [ ] `app/essays/routes.py`
- [ ] `app/essays/forms.py`

#### 4.2 MOMOAICore 개선
- [ ] `momoai_core.py` 리팩토링
- [ ] SQLAlchemy 모델 연동
- [ ] 버전 관리 로직 추가
- [ ] Essay, EssayVersion 생성

#### 4.3 새 첨삭 시작
- [ ] 새 첨삭 폼 (학생 선택, 논술문 입력, 주의사항, 도서 선택)
- [ ] 학생 드롭다운 (AJAX로 동적 로딩)
- [ ] 새 첨삭 라우트 (`/essays/new`)
- [ ] 새 첨삭 템플릿

#### 4.4 첨삭 진행 중
- [ ] 백그라운드 작업 (threading 유지 또는 Celery 검토)
- [ ] 진행 중 라우트 (`/essays/processing/:id`)
- [ ] 진행 중 템플릿 (로딩 애니메이션)
- [ ] 자동 새로고침 또는 폴링

#### 4.5 첨삭 결과 표시
- [ ] 첨삭 결과 라우트 (`/essays/result/:id`)
- [ ] 첨삭 결과 템플릿 (HTML 리포트 표시)
- [ ] 버전 표시 (v1, v2...)

---

### 🔄 5. 첨삭 수정/완료 프로세스 (1주)

#### 5.1 수정 요청
- [ ] 수정 요청 폼 (텍스트 에리어)
- [ ] 수정 요청 API (`POST /api/essays/:id/regenerate`)
- [ ] 수정 이력 표시

#### 5.2 재생성
- [ ] 재생성 로직 (Claude API 재호출)
- [ ] 새 버전 생성 (version_number++)
- [ ] EssayVersion 저장
- [ ] 재생성 중 페이지 (`/essays/regenerating/:id`)

#### 5.3 버전 전환
- [ ] 버전 목록 표시
- [ ] 특정 버전 보기 (`/essays/:id/versions/:version`)
- [ ] 초안으로 되돌리기 버튼

#### 5.4 완료 프로세스
- [ ] 완료 버튼 추가
- [ ] 완료 API (`POST /api/essays/:id/finalize`)
- [ ] is_finalized = true 업데이트
- [ ] PDF 자동 생성 (기존 pdf_generator.py 사용)
- [ ] 완료 페이지 (`/essays/completed/:id`)

#### 5.5 PDF 다운로드
- [ ] PDF 다운로드 라우트 (`/api/download/:filename`)
- [ ] HTML 다운로드 라우트

---

### 📊 6. 기본 대시보드 (0.5주)

#### 6.1 대시보드 라우트
- [ ] 대시보드 블루프린트 생성
- [ ] 대시보드 라우트 (`/dashboard`)

#### 6.2 통계 카드
- [ ] 총 첨삭 수
- [ ] 진행 중인 첨삭
- [ ] 이번 달 첨삭 수
- [ ] 학생 수

#### 6.3 진행 중 첨삭 목록
- [ ] 진행 중인 첨삭 목록 표시
- [ ] 각 첨삭으로 이동 링크

#### 6.4 빠른 시작
- [ ] 빠른 첨삭 시작 버튼
- [ ] 새 첨삭 페이지로 이동

#### 6.5 사이드바 네비게이션
- [ ] 사이드바 컴포넌트
- [ ] 메뉴 항목 (대시보드, 첨삭, 학생, 설정)
- [ ] 현재 페이지 하이라이트

---

### 🎨 7. UI/UX 개선 (0.5주)

#### 7.1 기본 레이아웃
- [ ] `templates/base.html` 개선
- [ ] 로그인 전/후 헤더 분기
- [ ] 푸터

#### 7.2 랜딩 페이지
- [ ] 랜딩 페이지 디자인 (`/`)
- [ ] 로그인/회원가입 버튼

#### 7.3 알림/플래시 메시지
- [ ] 성공/에러 메시지 표시
- [ ] Toast 알림 (선택적)

#### 7.4 로딩 상태
- [ ] 버튼 로딩 스피너
- [ ] 페이지 로딩 인디케이터

---

### 🧪 8. 테스트 & 버그 수정 (1주)

#### 8.1 단위 테스트
- [ ] 모델 테스트 (User, Student, Essay)
- [ ] 인증 테스트 (회원가입, 로그인)

#### 8.2 통합 테스트
- [ ] 첨삭 전체 플로우 테스트
- [ ] 학생 CRUD 테스트

#### 8.3 수동 테스트
- [ ] 회원가입부터 첨삭 완료까지 E2E 테스트
- [ ] 다양한 시나리오 테스트

#### 8.4 버그 수정
- [ ] 발견된 버그 수정
- [ ] 에러 핸들링 개선

---

## 📦 의존성 추가

```
# requirements.txt에 추가할 패키지들
Flask-SQLAlchemy>=3.0.0
Flask-Migrate>=4.0.0
Flask-Login>=0.6.0
Flask-WTF>=1.1.0
WTForms>=3.0.0
psycopg2-binary>=2.9.0  # PostgreSQL
email-validator>=2.0.0   # 이메일 검증
```

---

## 🚀 시작 순서

### Week 1: DB + 인증
1. SQLAlchemy 모델 작성
2. 마이그레이션
3. 회원가입/로그인 구현

### Week 2: 학생 + 첨삭 기본
4. 학생 CRUD
5. 첨삭 기능 리팩토링

### Week 3: 첨삭 고급
6. 첨삭 수정/완료 프로세스
7. 버전 관리

### Week 4: 대시보드 + UI
8. 대시보드 구현
9. UI/UX 개선

### Week 5-6: 테스트 & 정리
10. 테스트 작성
11. 버그 수정
12. 문서 정리

---

## 📝 추가 고려사항

### 선택적 기능 (Phase 1.5)
- [ ] 프로필 설정 페이지
- [ ] 비밀번호 변경
- [ ] 첨삭 검색 기능
- [ ] 페이지네이션

### 기술적 개선
- [ ] API 응답 표준화 (JSON 형식)
- [ ] 에러 핸들링 미들웨어
- [ ] 로깅 시스템
- [ ] 환경 변수 관리 (.env)

---

**작성일**: 2026-02-06
**최종 수정일**: 2026-02-06

**다음 단계**: Week 1 작업 시작
