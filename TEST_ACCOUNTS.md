# MOMOAI v4.0 - 테스트 계정 정보

**생성일**: 2026-02-08
**프로젝트**: MOMOAI v4.0 Essay Correction System

---

## 📊 전체 계정 요약

| 역할 | 계정 수 | 설명 |
|------|---------|------|
| 관리자 (Admin) | 3개 | Master, Manager, Staff 3단계 |
| 강사 (Teacher) | 2개 | 테스트 강사, 실제 강사 |
| 학부모 (Parent) | 1개 | 테스트 학부모 |
| 학생 (Student) | 1개 | 테스트 학생 |
| **총계** | **7개** | - |

---

## 🔐 테스트 계정 상세 정보

### 1. 관리자 계정 (Admin Accounts)

#### 1-1. Master Admin (최고 관리자)
```
이메일: admin@momoai.com
비밀번호: admin123
권한 레벨: 1 (Master)
권한 범위: 모든 기능 접근 및 수정 가능
```

**접근 가능 기능:**
- ✅ 수업 생성 및 관리
- ✅ 학생 등록 및 관리
- ✅ 결제 관리
- ✅ 공지사항 작성
- ✅ 전체 시스템 설정
- ✅ 다른 관리자 계정 관리
- ✅ 통계 및 리포트

**접속 URL:** `http://localhost:5000/admin`

---

#### 1-2. Manager Admin (중간 관리자)
```
이메일: manager@momoai.com
비밀번호: manager123
권한 레벨: 2 (Manager)
권한 범위: 대부분의 관리 기능 접근 가능
```

**접근 가능 기능:**
- ✅ 수업 관리
- ✅ 학생 등록
- ✅ 결제 조회 (수정 제한)
- ✅ 공지사항 작성
- ❌ 다른 관리자 삭제 불가

**접속 URL:** `http://localhost:5000/admin`

---

#### 1-3. Staff Admin (일반 관리자)
```
이메일: staff@momoai.com
비밀번호: staff123
권한 레벨: 3 (Staff)
권한 범위: 기본 관리 기능만 접근 가능
```

**접근 가능 기능:**
- ✅ 수업 조회
- ✅ 학생 조회
- ✅ 결제 조회
- ✅ 공지사항 조회
- ❌ 수업 생성/삭제 제한
- ❌ 결제 관리 제한

**접속 URL:** `http://localhost:5000/admin`

---

### 2. 강사 계정 (Teacher Accounts)

#### 2-1. 테스트 강사
```
이메일: test@momoai.com
비밀번호: testpassword123
권한 레벨: 4 (Teacher)
이름: 테스트 강사
```

**접근 가능 기능:**
- ✅ 내 수업 관리
- ✅ 학생 첨삭 관리 (채점, 피드백)
- ✅ 출석 체크 (수동 체크)
- ✅ 학부모 피드백 작성
- ✅ 내 학생 목록 조회
- ✅ 수업 자료 업로드
- ✅ 과제 관리

**접속 URL:** `http://localhost:5000/teacher`

**테스트 시나리오:**
1. 출석 체크: `/teacher` → 오늘 수업 → 출석 체크
2. 첨삭 처리: 대시보드 → Essays → 첨삭 진행
3. 피드백 작성: `/teacher/feedback/new`

---

#### 2-2. 실제 강사 (추승호)
```
이메일: chsh82@gmail.com
비밀번호: (실제 비밀번호 - 보안상 비공개)
권한 레벨: 4 (Teacher)
이름: 추승호
```

---

### 3. 학부모 계정 (Parent Account)

```
이메일: parent@momoai.com
비밀번호: testpassword123
권한 레벨: 5 (Parent)
이름: Parent User
```

**접근 가능 기능:**
- ✅ 자녀 정보 조회
- ✅ 자녀 출석 현황 조회
- ✅ 강사 피드백 수신 및 확인
- ✅ 결제 내역 조회
- ✅ 미납 금액 확인
- ✅ 자녀 첨삭 결과 조회
- ❌ 첨삭 제출 불가 (학생만 가능)

**접속 URL:** `http://localhost:5000/parent`

**테스트 시나리오:**
1. 자녀 목록: `/parent/children`
2. 출석 현황: `/parent/children/<student_id>/attendance`
3. 피드백 확인: `/parent/feedback` (NEW 배지 확인)
4. 결제 관리: `/parent/children/<student_id>/payments`

**주요 특징:**
- 다자녀 지원 (ParentStudent 다대다 관계)
- 강사 피드백은 학생에게 숨김 (hidden_from_student=True)
- 출석 기반 자동 수업료 계산

---

### 4. 학생 계정 (Student Account)

```
이메일: student@momoai.com
비밀번호: testpassword123
권한 레벨: 6 (Student)
이름: Student User
```

**접근 가능 기능:**
- ✅ 과제 제출 (자동 알림 전송)
- ✅ 내 첨삭 목록 조회
- ✅ 첨삭 결과 확인
- ✅ 수강 중인 수업 조회
- ✅ 출석 현황 조회
- ✅ 공지사항 확인 (Tier 필터링)
- ✅ 수업 자료 다운로드
- ❌ 강사 피드백 조회 불가 (학부모만 가능)

**접속 URL:** `http://localhost:5000/student`

**테스트 시나리오:**
1. 과제 제출: `/student/essays/new` → 제출 → 강사에게 자동 알림
2. 내 첨삭: `/student/essays` → 완료된 첨삭 확인
3. 내 수업: `/student/courses` → 출석률 확인
4. 공지사항: `/student/announcements` (Tier 기반 필터링)

**주요 특징:**
- 과제 제출 시 파일 첨부 가능 (이미지, PDF, 워드, 한글)
- 담당 강사에게 자동 알림 전송
- Tier 등급별 콘텐츠 접근 제어 (A, B, C, VIP)
- 메인 메뉴 숨김 (학생 포털 메뉴만 표시)

---

## 🎯 권한 레벨 시스템

| Level | 역할 | 설명 |
|-------|------|------|
| 1 | Master Admin | 최고 관리자 (모든 권한) |
| 2 | Manager Admin | 중간 관리자 (제한적 관리 권한) |
| 3 | Staff Admin | 일반 관리자 (기본 관리 권한) |
| 4 | Teacher | 강사 (담당 수업/학생 관리) |
| 5 | Parent | 학부모 (자녀 정보 조회) |
| 6 | Student | 학생 (과제 제출 및 조회) |

**권한 검증:**
- `@requires_permission_level(N)`: N 이하 레벨만 접근 가능
- `@requires_role('admin', 'teacher')`: 특정 역할만 접근 가능
- `@requires_tier('A', 'VIP')`: 학생 Tier 등급 검증

---

## 🚀 빠른 접속 가이드

### 로그인 페이지
```
http://localhost:5000/auth/login
```

### 역할별 대시보드
```
관리자: http://localhost:5000/admin
강사:   http://localhost:5000/teacher
학부모: http://localhost:5000/parent
학생:   http://localhost:5000/student
```

---

## 🛠️ 계정 생성 스크립트

### 관리자 계정 생성
```bash
python create_admin_accounts.py
```

### 테스트 강사 계정 생성
```bash
python test_auth.py
```

### 테스트 학생 데이터 생성
```bash
python test_students.py
```

### 데모 첨삭 데이터 생성
```bash
python create_demo_data.py
```

---

## 📝 테스트 워크플로우

### 전체 시스템 테스트
```
1. [Admin] 관리자 로그인 (admin@momoai.com)
   → 수업 생성 (/admin/courses/new)
   → 학생 등록 (/admin/students/enroll)

2. [Student] 학생 로그인 (student@momoai.com)
   → 과제 제출 (/student/essays/new)
   → 파일 첨부 테스트

3. [Teacher] 강사 로그인 (test@momoai.com)
   → 알림 확인 (학생 과제 제출 알림)
   → 출석 체크 (/teacher/sessions/<id>/attendance)
   → 첨삭 진행 및 완료

4. [Teacher] 학부모 피드백 작성
   → /teacher/feedback/new
   → 학생 선택 → 학부모 선택 → 피드백 전송

5. [Parent] 학부모 로그인 (parent@momoai.com)
   → 자녀 출석 확인 (/parent/children)
   → 피드백 확인 (NEW 배지)
   → 결제 내역 조회

6. [Student] 학생 로그인 (student@momoai.com)
   → 첨삭 결과 확인 (/student/essays)
   → 강사 피드백 보이지 않음 확인
```

---

## ⚠️ 주의사항

### 보안
- 프로덕션 환경에서는 반드시 비밀번호 변경 필요
- `testpassword123`, `admin123` 등은 테스트 전용

### 데이터베이스
- 테스트 계정은 SQLite 개발 DB에 저장됨
- 초기화: `flask db upgrade`
- 재생성: `python create_admin_accounts.py`

### 자동 알림
- 학생 과제 제출 → 담당 강사 알림 (자동)
- 강사 피드백 작성 → 학부모 알림 (자동)
- 첨삭 완료 → 학생 알림 (자동)

### Tier 시스템
- Student.tier: 'A', 'B', 'C', 'VIP'
- Course.tier: 등급별 수업 구분
- Announcement.tier: 등급별 공지사항 필터링

---

## 📞 문의

계정 관련 문제가 발생하면:
1. 데이터베이스 확인: `python -c "from app import create_app; app = create_app(); ..."`
2. 계정 재생성: `python create_admin_accounts.py`
3. 비밀번호 재설정: 관리자 계정으로 로그인 후 수정

---

**마지막 업데이트**: 2026-02-08
**버전**: MOMOAI v4.0
