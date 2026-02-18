# Phase 1 Week 1 진행 상황

**작업 날짜**: 2026-02-06

## 완료된 작업

### 1. ✅ 프로젝트 구조 생성
- [x] app/ 디렉토리 구조 생성
- [x] blueprints 디렉토리 (auth, essays, students, dashboard)
- [x] models/ 디렉토리

### 2. ✅ 의존성 설치
**requirements.txt에 추가된 패키지:**
```
Flask-SQLAlchemy>=3.0.0
Flask-Migrate>=4.0.0
Flask-Login>=0.6.0
Flask-WTF>=1.1.0
WTForms>=3.0.0
email-validator>=2.0.0
psycopg2-binary>=2.9.0
```

모든 패키지 설치 완료.

### 3. ✅ SQLAlchemy 모델 작성

**생성된 모델 파일:**
- `app/models/user.py` - User 모델
  - user_id, email, password_hash, name, role, is_active
  - 비밀번호 해싱 및 검증 메서드
  - Flask-Login UserMixin 적용

- `app/models/student.py` - Student 모델
  - student_id, teacher_id, name, grade, email, phone, notes
  - teacher relationship

- `app/models/essay.py` - Essay, EssayVersion, EssayResult 모델
  - Essay: 첨삭 작업 메인 모델
  - EssayVersion: 버전 관리 (v1, v2, v3...)
  - EssayResult: 첨삭 결과 (HTML/PDF 경로, 점수)

- `app/models/essay_score.py` - EssayScore, EssayNote 모델
  - EssayScore: 18개 지표 점수
  - EssayNote: 강사 주의사항

**Relationships 설정 완료:**
- User → Students (1:N)
- User → Essays (1:N)
- Student → Essays (1:N)
- Essay → EssayVersions (1:N)
- Essay → EssayResult (1:1)
- Essay → EssayScores (1:N)
- Essay → EssayNotes (1:N)

### 4. ✅ Config 설정

**config.py 업데이트:**
- Config 클래스 생성
- DevelopmentConfig (SQLite, Debug mode)
- ProductionConfig (PostgreSQL)
- SECRET_KEY 설정
- SQLALCHEMY_DATABASE_URI 설정

### 5. ✅ Flask App Factory 생성

**app/__init__.py:**
- `create_app()` 팩토리 함수
- SQLAlchemy 초기화
- Flask-Migrate 초기화
- Flask-Login 초기화
- user_loader 설정
- Blueprint 등록 준비

**run.py:**
- 새로운 진입점 파일
- app factory 사용
- 환경 변수 기반 config 선택

### 6. ✅ 데이터베이스 마이그레이션

**실행 명령어:**
```bash
flask db init
flask db migrate -m "Initial migration: User, Student, Essay models"
flask db upgrade
```

**생성된 테이블:**
- users
- students
- essays
- essay_versions
- essay_results
- essay_scores
- essay_notes

모든 테이블이 성공적으로 생성되었으며, 인덱스와 외래 키 제약 조건이 올바르게 적용됨.

**데이터베이스 파일:**
- `momoai.db` (SQLite, development용)

### 7. ✅ 인증 시스템 구현

**app/auth/forms.py:**
- LoginForm - 로그인 폼 (이메일, 비밀번호, Remember Me)
- SignupForm - 회원가입 폼 (이름, 이메일, 비밀번호, 확인)
- ChangePasswordForm - 비밀번호 변경 폼
- 폼 검증 (이메일 중복 체크, 비밀번호 일치 확인)

**app/auth/routes.py:**
- `/auth/login` - 로그인 (GET, POST)
- `/auth/signup` - 회원가입 (GET, POST)
- `/auth/logout` - 로그아웃
- `/auth/change-password` - 비밀번호 변경
- Flask-Login 통합 (login_user, logout_user)
- Flash 메시지 처리

**app/auth/__init__.py:**
- auth_bp 블루프린트 생성

**templates/auth/:**
- `login.html` - 로그인 페이지
- `signup.html` - 회원가입 페이지
- Tailwind CSS 스타일링
- Flash 메시지 표시
- 폼 에러 표시

### 8. ✅ 앱 실행 확인

서버가 정상적으로 실행됨:
```
MOMOAI v4.0 Web Application
Environment: development
Database: sqlite:///C:\Users\aproa\momoai_web\momoai.db
Debug Mode: True
Server starting...
URL: http://localhost:5000
```

---

## 테스트 가능한 기능

### 1. 회원가입
- URL: http://localhost:5000/auth/signup
- 이름, 이메일, 비밀번호 입력
- 자동으로 'teacher' 역할 부여

### 2. 로그인
- URL: http://localhost:5000/auth/login
- 이메일, 비밀번호 입력
- Remember Me 옵션

### 3. 로그아웃
- URL: http://localhost:5000/auth/logout
- 로그인 상태에서 접근 가능

---

## 다음 단계 (Week 1 나머지 작업)

### Phase 1.1.4 - 학생 관리 CRUD (0.5주)
- [ ] Students blueprint 생성
- [ ] 학생 목록 페이지
- [ ] 학생 추가/수정/삭제
- [ ] 학생 상세 페이지

### Phase 1.1.5 - 첨삭 기능 리팩토리ng (1.5주)
- [ ] Essays blueprint 생성
- [ ] MOMOAICore를 SQLAlchemy와 연동
- [ ] 새 첨삭 시작 페이지
- [ ] 첨삭 진행 중 페이지
- [ ] 첨삭 결과 페이지

### Phase 1.1.6 - 첨삭 수정/완료 프로세스 (1주)
- [ ] 수정 요청 기능
- [ ] 재생성 로직 (버전 관리)
- [ ] 완료 버튼 및 PDF 생성
- [ ] 버전 전환 기능

### Phase 1.1.7 - 기본 대시보드 (0.5주)
- [ ] Dashboard blueprint 생성
- [ ] 통계 카드 (총 첨삭 수, 진행 중, 학생 수)
- [ ] 진행 중인 첨삭 목록
- [ ] 사이드바 네비게이션

---

## 기술 스택 확인

- ✅ Flask 3.0+
- ✅ SQLAlchemy 2.0+
- ✅ Flask-Migrate 4.0+
- ✅ Flask-Login 0.6+
- ✅ Flask-WTF 1.2+
- ✅ WTForms 3.2+
- ✅ Jinja2 템플릿
- ✅ Tailwind CSS (CDN)
- ✅ SQLite (개발 환경)

---

## 변경 사항

### 기존 파일
- `app.py` - 향후 제거 예정 (run.py로 대체)
- `database.py` - 향후 제거 예정 (SQLAlchemy 모델로 대체)
- `tasks.db` - 기존 DB (마이그레이션 후 제거 예정)

### 새 파일
- `run.py` - 새 진입점
- `momoai.db` - 새 SQLite 데이터베이스
- `app/` - 새 애플리케이션 구조

---

## 진행률

### Week 1 (DB + 인증)
- [x] 1.1 SQLAlchemy 설정 (100%)
- [x] 1.2 모델 작성 (100%)
- [x] 1.3 마이그레이션 (100%)
- [x] 2.1 Flask-Login 설정 (100%)
- [x] 2.2 인증 블루프린트 생성 (100%)
- [x] 2.3 회원가입 (100%)
- [x] 2.4 로그인/로그아웃 (100%)
- [ ] 2.5 비밀번호 재설정 (보류)
- [ ] 2.6 권한 데코레이터 (예정)

**전체 진행률: ~60% (Week 1 기준)**

---

**다음 작업 시작**: 학생 관리 CRUD 구현
**예상 소요 시간**: 0.5주

---

**작성일**: 2026-02-06
**최종 수정일**: 2026-02-06
