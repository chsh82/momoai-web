# 수업 관리 시스템 구현 가이드

## 📋 개요

이 문서는 MOMOAI v4.0의 수업 관리 시스템(Course Management System) 구현 내용을 설명합니다.

### 주요 기능

1. **수업 관리** (Course Management)
   - 관리자가 수업 생성/수정/삭제
   - 강사 배정
   - 학생 등록 관리
   - 자동 세션 생성

2. **출석 관리** (Attendance Management)
   - 수업별 출석 체크 (수동 방식)
   - 출석률 통계
   - 출석 기반 결제 데이터

3. **결제 관리** (Payment Management)
   - 출석 기반 자동 결제 계산
   - 결제 이력 관리
   - 미납 관리

4. **학부모 포털** (Parent Portal)
   - 자녀 정보 조회
   - 출석 및 성적 확인
   - 강사 피드백 수신 (학생 비공개)
   - 결제 관리

5. **학생 포털** (Student Portal)
   - 과제 제출
   - 수업 자료 확인
   - 학급 게시판

6. **공지사항** (Announcements)
   - 전체/대상별 공지
   - 역할별/등급별 필터링

7. **권한 관리** (Permission System)
   - 역할 기반 접근 제어 (RBAC)
   - 계층적 권한 구조
   - 학생 등급별 접근 제한

---

## ✅ 완료된 작업

### 1. 데이터베이스 모델 생성

#### 새로운 모델 파일들:

- **`app/models/course.py`**
  - `Course`: 수업 정보 (수업명, 강사, 일정, 가격 등)
  - `CourseEnrollment`: 수강 신청 (학생-수업 연결)
  - `CourseSession`: 개별 수업 회차

- **`app/models/attendance.py`**
  - `Attendance`: 출석 기록 (수동 체크 방식)

- **`app/models/payment.py`**
  - `Payment`: 결제 기록 (출석 기반 계산)

- **`app/models/parent_student.py`**
  - `ParentStudent`: 학부모-학생 연결 (다대다 관계)

- **`app/models/teacher_feedback.py`**
  - `TeacherFeedback`: 강사→학부모 피드백 (학생 비공개)

- **`app/models/announcement.py`**
  - `Announcement`: 전체 공지사항
  - `AnnouncementRead`: 공지 읽음 기록

#### 수정된 모델 파일들:

- **`app/models/user.py`**
  - `role_level` 필드 추가 (1=master_admin, 2=manager, 3=teacher, 4=parent, 5=student)
  - 권한 체크 메서드 추가:
    - `is_master_admin()`
    - `is_manager()`
    - `has_permission_level(level)`
    - `can_manage_user(target_user)`

- **`app/models/student.py`**
  - `tier` 필드 추가 (A, B, C, VIP 등 등급)
  - `tier_updated_at` 필드 추가
  - 메서드 추가:
    - `update_tier(new_tier)`
    - `has_tier_access(required_tiers)`

- **`app/models/__init__.py`**
  - 모든 새 모델 import 추가

### 2. 유틸리티 함수 생성

#### `app/utils/decorators.py`

권한 체크 데코레이터:
- `@requires_role(*roles)`: 특정 역할만 접근 가능
- `@requires_permission_level(level)`: 특정 권한 레벨 이상만 접근
- `@requires_tier(*tiers)`: 특정 등급 학생만 접근
- `@admin_or_owner_required(get_owner_id)`: 관리자 또는 소유자만 접근
- `@master_admin_only`: 마스터 관리자만 접근

**사용 예시:**
```python
from app.utils.decorators import requires_role, requires_permission_level, requires_tier

@app.route('/admin/users')
@requires_role('admin')  # 관리자만
def manage_users():
    ...

@app.route('/manager/courses')
@requires_permission_level(2)  # 매니저 이상 (level <= 2)
def manage_courses():
    ...

@app.route('/premium/content')
@requires_tier('A', 'VIP')  # A등급 또는 VIP만
def premium_content():
    ...
```

#### `app/utils/course_utils.py`

수업 관리 자동화 함수:

- **`generate_course_sessions(course)`**
  - 수업 생성 시 자동으로 세션들을 생성
  - weekly 스케줄: 매주 같은 요일에 자동 생성
  - custom 스케줄: 수동으로 세션 추가

- **`create_attendance_records_for_enrollment(enrollment)`**
  - 학생 수강 신청 시 모든 세션에 대한 출석 레코드 자동 생성

- **`create_attendance_records_for_session(session)`**
  - 새 세션 생성 시 모든 수강생의 출석 레코드 자동 생성

- **`update_enrollment_attendance_stats(enrollment_id)`**
  - 수강 신청의 출석 통계 업데이트

- **`calculate_tuition_amount(enrollment)`**
  - 출석 기반 수업료 계산
  - 반환: total_amount, paid_amount, remaining_amount, attended_unpaid

- **`get_course_statistics(course_id)`**
  - 수업 통계 정보 조회 (학생 수, 출석률, 수익 등)

- **`enroll_student_to_course(course_id, student_id)`**
  - 학생을 수업에 등록 (편의 함수)
  - 정원 확인 및 출석 레코드 자동 생성

**사용 예시:**
```python
from app.utils.course_utils import generate_course_sessions, enroll_student_to_course

# 수업 생성 시
course = Course(...)
db.session.add(course)
db.session.flush()
generate_course_sessions(course)  # 자동으로 세션 생성
db.session.commit()

# 학생 등록 시
enrollment = enroll_student_to_course(course_id, student_id)
if enrollment:
    db.session.commit()
    flash('수강 신청이 완료되었습니다.', 'success')
```

---

## 🔧 데이터베이스 마이그레이션

### 방법 1: 자동 마이그레이션 스크립트 실행 (권장)

```bash
cd C:\Users\aproa\momoai_web
python create_course_tables.py
```

이 스크립트는:
- 모든 새 테이블 생성
- 기존 테이블에 새 컬럼 추가
- 결과 출력

### 방법 2: Flask-Migrate 사용

```bash
# 마이그레이션 파일 생성
flask db migrate -m "Add course management system"

# 마이그레이션 적용
flask db upgrade
```

### 방법 3: 수동 SQL (SQLite)

```sql
-- users 테이블에 role_level 컬럼 추가
ALTER TABLE users ADD COLUMN role_level INTEGER DEFAULT 3;

-- students 테이블에 tier 관련 컬럼 추가
ALTER TABLE students ADD COLUMN tier VARCHAR(20);
ALTER TABLE students ADD COLUMN tier_updated_at DATETIME;

-- 나머지는 create_course_tables.py가 자동으로 처리
```

---

## 📁 다음 단계: 라우트 및 UI 구현

### 1. 관리자 포털 (Admin Portal)

**Blueprint 생성: `app/admin/`**

필요한 라우트:
```python
# app/admin/routes.py

@admin_bp.route('/courses')
@requires_permission_level(2)  # 매니저 이상
def list_courses():
    """수업 목록"""
    ...

@admin_bp.route('/courses/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_course():
    """수업 생성"""
    # 1. 수업 정보 입력
    # 2. 강사 배정
    # 3. generate_course_sessions() 호출
    ...

@admin_bp.route('/courses/<course_id>/students')
@requires_permission_level(2)
def manage_students(course_id):
    """학생 관리"""
    # 1. 수강생 목록
    # 2. 학생 추가/제거
    # 3. enroll_student_to_course() 호출
    ...

@admin_bp.route('/courses/<course_id>/payments')
@requires_permission_level(2)
def manage_payments(course_id):
    """결제 관리"""
    # 1. 결제 이력
    # 2. 미납 관리
    # 3. calculate_tuition_amount() 활용
    ...
```

**필요한 템플릿:**
- `templates/admin/courses_list.html`
- `templates/admin/course_form.html`
- `templates/admin/students_management.html`
- `templates/admin/payments_management.html`

### 2. 강사 포털 (Teacher Portal)

**Blueprint 생성: `app/teacher/`**

```python
# app/teacher/routes.py

@teacher_bp.route('/courses')
@requires_role('teacher', 'admin')
def my_courses():
    """내 수업 목록"""
    ...

@teacher_bp.route('/courses/<course_id>/sessions/<session_id>/attendance')
@requires_role('teacher', 'admin')
def check_attendance(course_id, session_id):
    """출석 체크"""
    # 수동 출석부 체크 UI
    ...

@teacher_bp.route('/api/attendance/<attendance_id>', methods=['PATCH'])
@requires_role('teacher', 'admin')
def update_attendance(attendance_id):
    """출석 상태 업데이트 API"""
    ...
```

**필요한 템플릿:**
- `templates/teacher/courses_list.html`
- `templates/teacher/attendance_check.html`

### 3. 학생 포털 (Student Portal)

**Blueprint 생성: `app/student_portal/`**

```python
# app/student_portal/routes.py

@student_bp.route('/')
@requires_role('student')
def dashboard():
    """학생 대시보드"""
    ...

@student_bp.route('/submit-essay', methods=['GET', 'POST'])
@requires_role('student')
def submit_essay():
    """과제 제출"""
    # 담당 강사에게 자동 연결 + 알림
    ...

@student_bp.route('/class-board')
@requires_role('student')
def class_board():
    """학급 게시판"""
    ...

@student_bp.route('/premium-content')
@requires_tier('A', 'VIP')
def premium_content():
    """프리미엄 콘텐츠 (A등급, VIP만)"""
    ...
```

**필요한 템플릿:**
- `templates/student_portal/dashboard.html`
- `templates/student_portal/submit_essay.html`
- `templates/student_portal/class_board.html`

### 4. 학부모 포털 (Parent Portal)

**Blueprint 생성: `app/parent_portal/`**

```python
# app/parent_portal/routes.py

@parent_bp.route('/')
@requires_role('parent')
def dashboard():
    """학부모 대시보드"""
    # 연결된 자녀 목록
    ...

@parent_bp.route('/student/<student_id>')
@requires_role('parent')
def student_info(student_id):
    """자녀 정보"""
    # 1. 출석 현황
    # 2. 성적 정보
    # 3. 첨삭 기록
    ...

@parent_bp.route('/student/<student_id>/feedback')
@requires_role('parent')
def teacher_feedback(student_id):
    """강사 피드백 (학생 비공개)"""
    ...

@parent_bp.route('/student/<student_id>/payments')
@requires_role('parent')
def payments(student_id):
    """결제 관리"""
    ...
```

**필요한 템플릿:**
- `templates/parent_portal/dashboard.html`
- `templates/parent_portal/student_info.html`
- `templates/parent_portal/feedback.html`
- `templates/parent_portal/payments.html`

### 5. 공지사항 시스템 (Announcements)

**기존 community blueprint에 추가하거나 별도 blueprint 생성**

```python
@app.route('/announcements')
@login_required
def list_announcements():
    """공지사항 목록"""
    # 현재 사용자에게 보이는 공지만 필터링
    announcements = Announcement.query.filter(
        Announcement.is_published == True
    ).all()

    visible_announcements = [
        a for a in announcements
        if a.is_visible_to_user(current_user)
    ]
    ...

@app.route('/announcements/<announcement_id>')
@login_required
def view_announcement(announcement_id):
    """공지사항 상세"""
    announcement = Announcement.query.get_or_404(announcement_id)
    announcement.mark_as_read_by(current_user.user_id)
    db.session.commit()
    ...

@app.route('/admin/announcements/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_announcement():
    """공지사항 작성"""
    ...
```

---

## 🎨 UI/UX 가이드라인

### 출석 체크 UI (강사용)

```
┌─────────────────────────────────────────────────────┐
│ 수업: Python 기초반 A                                │
│ 일시: 2026-02-10 (월) 14:00-16:00                   │
│ 강사: 김강사                                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  출석 체크                                          │
│                                                     │
│  [ ] 김학생  [ 출석 ] [ 결석 ] [ 지각 ] [ 인정결석 ] │
│  [ ] 이학생  [ 출석 ] [ 결석 ] [ 지각 ] [ 인정결석 ] │
│  [ ] 박학생  [ 출석 ] [ 결석 ] [ 지각 ] [ 인정결석 ] │
│                                                     │
│              [저장하기]                             │
└─────────────────────────────────────────────────────┘
```

### 학부모 대시보드

```
┌───────────────────────────────────────────────┐
│ 내 자녀 목록                                   │
├───────────────────────────────────────────────┤
│                                               │
│  김철수 (중등 2학년)                           │
│  ├─ 출석률: 95% (19/20)                       │
│  ├─ 미납금: 150,000원                         │
│  ├─ 읽지 않은 피드백: 2건                     │
│  └─ [상세보기]                                │
│                                               │
│  김영희 (초등 5학년)                           │
│  ├─ 출석률: 100% (12/12)                      │
│  ├─ 미납금: 0원                               │
│  ├─ 읽지 않은 피드백: 0건                     │
│  └─ [상세보기]                                │
│                                               │
└───────────────────────────────────────────────┘
```

### 수업 통계 대시보드 (관리자용)

```python
# 활용 예시
stats = get_course_statistics(course_id)

print(f"수업명: {stats['course_name']}")
print(f"수강생: {stats['total_students']}/{stats['max_students']}")
print(f"완료/예정 세션: {stats['completed_sessions']}/{stats['total_sessions']}")
print(f"전체 출석률: {stats['attendance_rate']}%")
print(f"총 수익: {stats['total_revenue']:,}원")
print(f"미납금: {stats['total_pending']:,}원")
```

---

## 🔐 권한 레벨 구조

```
Level 1: Master Admin (마스터 관리자)
  ├─ 모든 데이터 접근/수정
  ├─ 사용자 역할 변경
  └─ 시스템 설정 변경

Level 2: Manager (매니저)
  ├─ 수업 관리
  ├─ 학생/강사 관리
  ├─ 결제 관리
  └─ 레벨 3 이하 사용자 관리

Level 3: Teacher (강사)
  ├─ 담당 수업 관리
  ├─ 출석 체크
  ├─ 학생 피드백
  └─ 담당 학생 조회

Level 4: Parent (학부모)
  ├─ 자녀 정보 조회
  ├─ 출석/성적 확인
  ├─ 결제 처리
  └─ 강사 피드백 수신

Level 5: Student (학생)
  ├─ 본인 정보 조회
  ├─ 과제 제출
  ├─ 수업 자료 열람
  └─ 등급별 콘텐츠 접근
```

---

## 📝 구현 체크리스트

### 완료 ✅
- [x] 데이터베이스 모델 생성
- [x] 권한 체크 데코레이터
- [x] 수업 관리 유틸리티 함수
- [x] User 모델에 role_level 추가
- [x] Student 모델에 tier 추가
- [x] 마이그레이션 스크립트

### 진행 중 🔄
- [ ] 관리자 포털 (admin blueprint)
- [ ] 강사 포털 (teacher blueprint)
- [ ] 학생 포털 (student_portal blueprint)
- [ ] 학부모 포털 (parent_portal blueprint)
- [ ] 공지사항 시스템

### 예정 📅
- [ ] 출석 체크 UI
- [ ] 결제 관리 UI
- [ ] 통계 대시보드
- [ ] 모바일 반응형 디자인
- [ ] 알림 시스템 통합
- [ ] 테스트 코드 작성

---

## 🚀 빠른 시작

### 1. 데이터베이스 마이그레이션

```bash
python create_course_tables.py
```

### 2. 테스트 데이터 생성 (선택사항)

```python
# create_test_course_data.py 예시
from app import create_app
from app.models import db, User, Student, Course
from app.utils.course_utils import generate_course_sessions, enroll_student_to_course
from datetime import date, time

app = create_app('development')

with app.app_context():
    # 1. 강사 생성
    teacher = User(
        email='teacher@test.com',
        name='김강사',
        role='teacher',
        role_level=3
    )
    teacher.set_password('password')
    db.session.add(teacher)
    db.session.flush()

    # 2. 수업 생성
    course = Course(
        course_name='Python 기초반 A',
        course_code='PY-101-A',
        tier='A',
        teacher_id=teacher.user_id,
        max_students=15,
        schedule_type='weekly',
        weekday=0,  # 월요일
        start_time=time(14, 0),
        end_time=time(16, 0),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        price_per_session=50000,
        created_by=teacher.user_id
    )
    db.session.add(course)
    db.session.flush()

    # 3. 세션 자동 생성
    generate_course_sessions(course)

    # 4. 학생 생성 및 수강 신청
    student = Student(
        teacher_id=teacher.user_id,
        name='김학생',
        grade='중등',
        tier='A'
    )
    db.session.add(student)
    db.session.flush()

    enroll_student_to_course(course.course_id, student.student_id)

    db.session.commit()
    print("✓ 테스트 데이터 생성 완료!")
```

### 3. 서버 실행

```bash
python run.py
```

---

## 📚 참고 자료

### 데이터베이스 ERD 주요 관계

```
User (사용자)
  ├─ 1:N → Course (teaching_courses)
  ├─ 1:N → TeacherFeedback (sent_feedbacks)
  ├─ 1:N → TeacherFeedback (received_feedbacks)
  └─ N:M → Student (via ParentStudent)

Course (수업)
  ├─ 1:N → CourseSession (sessions)
  ├─ 1:N → CourseEnrollment (enrollments)
  └─ 1:N → Payment (payments)

CourseSession (수업 회차)
  └─ 1:N → Attendance (attendance_records)

Student (학생)
  ├─ 1:N → CourseEnrollment (course_enrollments)
  ├─ 1:N → Attendance (attendance_records)
  ├─ 1:N → Payment (payments)
  ├─ 1:N → TeacherFeedback (teacher_feedbacks)
  └─ N:M → User (via ParentStudent)

CourseEnrollment (수강신청)
  ├─ 1:N → Attendance (attendance_records)
  └─ 1:N → Payment (payments)
```

### API 설계 예시

```python
# 출석 체크 API
POST /api/attendance/<attendance_id>/check
{
  "status": "present",  # present, absent, late, excused
  "notes": "수업 참여 적극적"
}

# 결제 등록 API
POST /api/payments
{
  "enrollment_id": "...",
  "amount": 200000,
  "payment_method": "card",
  "sessions_covered": 4
}

# 강사 피드백 작성 API
POST /api/teacher-feedback
{
  "student_id": "...",
  "parent_id": "...",
  "title": "이번 주 수업 피드백",
  "content": "수업 참여도가 높았습니다...",
  "feedback_type": "progress",
  "priority": "normal"
}
```

---

## 🐛 문제 해결

### 문제: 마이그레이션 실패

**해결:**
```bash
# Flask-Migrate 재초기화
flask db init
flask db migrate
flask db upgrade
```

### 문제: role_level이 null

**해결:**
```python
# 기존 사용자들에게 기본 role_level 설정
from app.models import User, db

with app.app_context():
    users = User.query.filter_by(role_level=None).all()
    for user in users:
        if user.role == 'admin':
            user.role_level = 1  # master_admin
        elif user.role == 'teacher':
            user.role_level = 3
        elif user.role == 'parent':
            user.role_level = 4
        elif user.role == 'student':
            user.role_level = 5
    db.session.commit()
```

---

## 📞 다음 단계

1. **관리자 포털 구현** - 수업 생성 및 관리 UI
2. **강사 포털 구현** - 출석 체크 UI
3. **학생/학부모 포털 구현** - 대시보드 및 정보 조회
4. **알림 시스템 통합** - 출석, 결제, 피드백 알림
5. **통계 대시보드** - 수업 통계 시각화
6. **모바일 최적화** - 반응형 디자인 적용

---

*마지막 업데이트: 2026-02-06*
*버전: 1.0.0*
