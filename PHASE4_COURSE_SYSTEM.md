# Phase 4: 수업 관리 시스템 완료 ✅

## 작업 완료 시간: 2026-02-06

---

## 🎯 구현된 기능

### 1. 데이터베이스 모델 (9개 신규/수정)

#### 신규 모델 (7개)
1. **Course** - 수업 정보 관리
2. **CourseEnrollment** - 수강 신청 관리
3. **CourseSession** - 개별 수업 회차
4. **Attendance** - 출석 기록 (수동 체크)
5. **Payment** - 결제 관리 (출석 기반)
6. **ParentStudent** - 학부모-학생 연결
7. **TeacherFeedback** - 강사→학부모 피드백 (학생 비공개)
8. **Announcement** - 전체 공지사항
9. **AnnouncementRead** - 공지 읽음 기록

#### 수정된 모델 (2개)
1. **User** - `role_level` 필드 추가 (권한 계층)
2. **Student** - `tier` 필드 추가 (등급 시스템)

### 2. 유틸리티 함수

#### 권한 관리 (`app/utils/decorators.py`)
- `@requires_role()` - 역할 기반 접근 제어
- `@requires_permission_level()` - 계층적 권한 체크
- `@requires_tier()` - 학생 등급별 접근 제어
- `@admin_or_owner_required()` - 관리자 또는 소유자만
- `@master_admin_only` - 마스터 관리자 전용

#### 수업 관리 (`app/utils/course_utils.py`)
- `generate_course_sessions()` - 자동 세션 생성
- `create_attendance_records_for_enrollment()` - 출석 레코드 자동 생성
- `create_attendance_records_for_session()` - 새 세션 출석 생성
- `update_enrollment_attendance_stats()` - 출석 통계 업데이트
- `calculate_tuition_amount()` - 출석 기반 수업료 계산
- `get_course_statistics()` - 수업 통계 조회
- `enroll_student_to_course()` - 학생 수강 신청 (원스톱)

### 3. 마이그레이션 스크립트

**`create_course_tables.py`** - 데이터베이스 테이블 자동 생성

---

## 📁 파일 구조

```
momoai_web/
├── app/
│   ├── models/
│   │   ├── course.py              ✨ NEW
│   │   ├── attendance.py          ✨ NEW
│   │   ├── payment.py             ✨ NEW
│   │   ├── parent_student.py      ✨ NEW
│   │   ├── teacher_feedback.py    ✨ NEW
│   │   ├── announcement.py        ✨ NEW
│   │   ├── user.py                🔧 MODIFIED
│   │   ├── student.py             🔧 MODIFIED
│   │   └── __init__.py            🔧 MODIFIED
│   └── utils/
│       ├── __init__.py            ✨ NEW
│       ├── decorators.py          ✨ NEW
│       └── course_utils.py        ✨ NEW
├── create_course_tables.py        ✨ NEW
├── COURSE_SYSTEM_IMPLEMENTATION.md ✨ NEW
└── PHASE4_COURSE_SYSTEM.md        ✨ NEW (이 파일)
```

---

## 🚀 다음 실행 단계

### 1단계: 데이터베이스 마이그레이션

```bash
cd C:\Users\aproa\momoai_web
python create_course_tables.py
```

**예상 출력:**
```
✓ All database tables created successfully!

New tables added:
  - courses
  - course_enrollments
  - course_sessions
  - attendance
  - payments
  - parent_student
  - teacher_feedback
  - announcements
  - announcement_reads

Modified tables:
  - users (added role_level column)
  - students (added tier and tier_updated_at columns)
```

### 2단계: 기존 사용자 role_level 설정 (필요시)

```python
# 기존 사용자들에게 role_level 할당
from app import create_app
from app.models import db, User

app = create_app('development')

with app.app_context():
    users = User.query.all()
    for user in users:
        if not user.role_level:
            if user.role == 'admin':
                user.role_level = 1  # master_admin
            elif user.role == 'teacher':
                user.role_level = 3
            elif user.role == 'parent':
                user.role_level = 4
            elif user.role == 'student':
                user.role_level = 5
    db.session.commit()
    print("✓ role_level 설정 완료!")
```

### 3단계: UI 구현 시작

다음 blueprint들을 생성해야 합니다:

1. **`app/admin/`** - 관리자 포털
   - 수업 생성/관리
   - 학생 등록 관리
   - 결제 관리

2. **`app/teacher/`** - 강사 포털
   - 내 수업 목록
   - 출석 체크 (수동)
   - 학생 피드백

3. **`app/student_portal/`** - 학생 포털
   - 과제 제출
   - 수업 자료
   - 학급 게시판

4. **`app/parent_portal/`** - 학부모 포털
   - 자녀 정보 조회
   - 출석/성적 확인
   - 강사 피드백 수신
   - 결제 처리

---

## 💡 주요 특징

### 1. 자동화된 워크플로우

**관리자가 수업 생성 시:**
```python
course = Course(...)
db.session.add(course)
db.session.flush()

# 자동으로 매주 세션 생성
generate_course_sessions(course)
db.session.commit()
```

**학생 등록 시:**
```python
# 모든 세션에 대한 출석 레코드 자동 생성
enrollment = enroll_student_to_course(course_id, student_id)
db.session.commit()
```

### 2. 출석 기반 결제 계산

```python
# 출석 현황에 따라 자동 계산
calc = calculate_tuition_amount(enrollment)
print(f"총 수업료: {calc['total_amount']:,}원")
print(f"납부 완료: {calc['paid_amount']:,}원")
print(f"미납금: {calc['remaining_amount']:,}원")
print(f"출석 미납 회차: {calc['attended_unpaid']}")
```

### 3. 계층적 권한 구조

```
Level 1 (Master Admin) → 모든 권한
Level 2 (Manager) → 관리 권한
Level 3 (Teacher) → 강사 권한
Level 4 (Parent) → 학부모 권한
Level 5 (Student) → 학생 권한
```

### 4. 학생 등급별 접근 제어

```python
@app.route('/premium-board')
@requires_tier('A', 'VIP')
def premium_board():
    """A등급, VIP만 접근 가능한 게시판"""
    ...
```

---

## 📊 데이터 흐름

### 수업 생성 → 세션 자동 생성
```
관리자 수업 생성
  ↓
Course 레코드 생성
  ↓
generate_course_sessions() 호출
  ↓
CourseSession 레코드 자동 생성 (매주 월요일 14:00-16:00 등)
```

### 학생 등록 → 출석 레코드 자동 생성
```
학생 수강 신청
  ↓
CourseEnrollment 생성
  ↓
create_attendance_records_for_enrollment() 호출
  ↓
모든 세션에 대한 Attendance 레코드 생성 (기본값: absent)
```

### 출석 체크 → 결제 데이터 업데이트
```
강사 출석 체크
  ↓
Attendance.status = 'present'
  ↓
update_enrollment_attendance_stats() 호출
  ↓
CourseEnrollment.attended_sessions 증가
  ↓
calculate_tuition_amount()로 납부할 금액 자동 계산
```

---

## 🔐 보안 기능

### 1. 역할 기반 접근 제어
- 각 기능에 필요한 역할/권한 레벨 지정
- 데코레이터로 간편하게 보호

### 2. 학생 비공개 피드백
- `TeacherFeedback.hidden_from_student = True` (강제)
- 학부모만 조회 가능

### 3. 소유자 확인
- `@admin_or_owner_required` 데코레이터
- 본인 또는 관리자만 수정 가능

---

## 📈 성능 최적화

### 인덱스 설정
- `user_id`, `course_id`, `student_id` 등 자주 조회되는 컬럼에 인덱스
- `role`, `role_level`, `tier`, `status` 등 필터링에 사용되는 컬럼 인덱스

### 관계 최적화
- `back_populates` 사용으로 양방향 관계 설정
- `cascade='all, delete-orphan'`로 자동 정리

---

## ✅ 체크리스트

### 완료된 작업
- [x] Course 모델 생성
- [x] CourseEnrollment 모델 생성
- [x] CourseSession 모델 생성
- [x] Attendance 모델 생성 (수동 체크)
- [x] Payment 모델 생성
- [x] ParentStudent 모델 생성
- [x] TeacherFeedback 모델 생성
- [x] Announcement 모델 생성
- [x] User 모델 role_level 추가
- [x] Student 모델 tier 추가
- [x] 권한 체크 데코레이터 구현
- [x] 수업 관리 유틸리티 함수 구현
- [x] 마이그레이션 스크립트 생성
- [x] 구현 가이드 문서 작성

### 다음 단계
- [ ] 관리자 포털 Blueprint 생성
- [ ] 강사 포털 Blueprint 생성
- [ ] 학생 포털 Blueprint 생성
- [ ] 학부모 포털 Blueprint 생성
- [ ] 출석 체크 UI 구현
- [ ] 결제 관리 UI 구현
- [ ] 공지사항 시스템 구현
- [ ] 통계 대시보드 구현
- [ ] 알림 시스템 통합
- [ ] 테스트 데이터 생성
- [ ] 단위 테스트 작성

---

## 📚 참고 문서

1. **`COURSE_SYSTEM_IMPLEMENTATION.md`** - 전체 구현 가이드
   - 데이터베이스 구조 상세 설명
   - UI/UX 가이드라인
   - API 설계 예시
   - 문제 해결 가이드

2. **모델 파일들** (`app/models/*.py`)
   - 각 모델의 필드 및 관계 정의
   - 프로퍼티 및 메서드 구현

3. **유틸리티 파일들** (`app/utils/*.py`)
   - 데코레이터 사용법
   - 자동화 함수 사용 예시

---

## 🎉 요약

### 구현된 내용
✅ 9개의 새로운 데이터베이스 모델
✅ 계층적 권한 시스템
✅ 학생 등급 시스템
✅ 자동화된 세션/출석 생성
✅ 출석 기반 결제 계산
✅ 강사→학부모 피드백 (학생 비공개)
✅ 전체 공지사항 시스템

### 다음 작업
🔜 관리자/강사/학생/학부모 포털 UI 구현
🔜 출석 체크 인터페이스
🔜 결제 관리 시스템
🔜 통계 대시보드

---

*Phase 4 완료 - 2026-02-06*
*다음: Phase 5 - UI 구현*
