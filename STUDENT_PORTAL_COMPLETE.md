# MOMOAI v4.0 - Student Portal Implementation Guide

**작성일**: 2026-02-06
**구현 완료**: 학생 포털 (Student Portal)

## 📋 개요

학생 포털은 MOMOAI v4.0 시스템의 네 번째 주요 구성 요소로, 학생들이 첨삭 제출, 수업 확인, 출석 조회, 공지사항 확인 등을 할 수 있는 통합 플랫폼입니다.

### 핵심 기능

1. **첨삭 제출 및 관리**
   - 새 첨삭 제출 (담당 강사 자동 연결 + 알림 전송)
   - 제출한 첨삭 목록 조회
   - 첨삭 결과 확인 (완료된 경우)

2. **수업 관리**
   - 수강 중인 수업 목록
   - 수업별 출석 현황
   - 수업 상세 정보

3. **출석 조회**
   - 수업별 출석/지각/결석 통계
   - 출석률 확인
   - 출석 기록 상세

4. **공지사항**
   - 학원 공지사항 조회
   - Tier 기반 필터링 (등급별 전용 공지)
   - 읽음/읽지 않음 구분

5. **수업 자료** (향후 구현 예정)
   - 강의 자료 다운로드
   - 동영상 강의 시청
   - 과제 자료 확인

---

## 🏗️ 구현 내역

### 1. Blueprint 생성

**위치**: `app/student_portal/`

#### `__init__.py`
```python
from flask import Blueprint

student_bp = Blueprint('student', __name__)

from app.student_portal import routes
```

#### `routes.py` - 11개 라우트

| 라우트 | 메서드 | 설명 | 권한 |
|--------|--------|------|------|
| `/` | GET | 학생 대시보드 | student, admin |
| `/courses` | GET | 내 수업 목록 | student, admin |
| `/courses/<course_id>` | GET | 수업 상세 정보 | student, admin |
| `/essays/new` | GET, POST | 새 첨삭 제출 | student, admin |
| `/essays` | GET | 내 첨삭 목록 | student, admin |
| `/essays/<essay_id>` | GET | 첨삭 상세 보기 | student, admin |
| `/attendance` | GET | 출석 현황 | student, admin |
| `/announcements` | GET | 공지사항 목록 | student, admin |
| `/announcements/<announcement_id>` | GET | 공지사항 상세 | student, admin |
| `/materials` | GET | 수업 자료 (향후 구현) | student, admin |

### 2. 템플릿 생성

**위치**: `templates/student/`

#### 생성된 템플릿 (10개)

1. **index.html** - 학생 대시보드
   - 빠른 통계 (수강 수업, 전체 첨삭, 완료 첨삭, 읽지 않은 공지)
   - 빠른 메뉴 (첨삭 제출, 내 첨삭, 내 수업, 공지사항)
   - 이번 주 수업 (출석 상태 포함)
   - 최근 첨삭 기록
   - 수강 중인 수업 목록

2. **submit_essay.html** - 첨삭 제출
   - 제목 입력
   - 본문 입력 (20줄 textarea)
   - 제출 안내 (자동 알림 전송 안내)
   - 제출 시 담당 강사에게 자동 알림

3. **my_essays.html** - 내 첨삭 목록
   - 첨삭 카드 형식 목록
   - 완료/진행 중 상태 표시
   - 총점 표시 (완료된 경우)
   - 종합 평가 미리보기

4. **view_essay.html** - 첨삭 상세
   - 제출한 원문
   - 첨삭 결과 (완료된 경우)
   - HTML/PDF 다운로드
   - 평가 점수 (총점 + 세부 점수)
   - 첨삭 정보 (담당 강사, 제출일, 완료일)

5. **courses.html** - 내 수업 목록
   - 수업 카드 형식
   - 출석률, 출석/결석 통계
   - 수업 시간 정보
   - Tier 뱃지

6. **course_detail.html** - 수업 상세
   - 출석 통계 (출석률, 출석, 지각, 결석)
   - 수업 정보 (시간, 회차, 강사, 설명)
   - 출석 기록 전체 목록

7. **attendance.html** - 출석 현황
   - 수업별 출석 통계
   - 최근 10개 출석 기록
   - 전체 기록 보기 링크

8. **announcements.html** - 공지사항 목록
   - 공지사항 카드
   - NEW 뱃지 (읽지 않은 경우)
   - 📌 고정 표시
   - Tier 필터링 (등급별 전용)

9. **view_announcement.html** - 공지사항 상세
   - 공지 본문
   - 첨부파일 다운로드
   - 읽음 자동 표시
   - Tier 정보

10. **materials.html** - 수업 자료 (향후 구현)
    - 수업별 자료 목록 (향후)
    - 기능 안내 UI

### 3. 사이드바 메뉴 추가

**파일**: `templates/base.html`

```html
{% if current_user.role in ['student', 'admin'] %}
<div class="mt-6 pt-6 border-t border-gray-200">
    <div class="text-xs font-medium text-gray-500 px-4 mb-2">학생</div>
    <a href="{{ url_for('student.index') }}">🏠 학생 대시보드</a>
    <a href="{{ url_for('student.submit_essay') }}">✍️ 첨삭 제출</a>
    <a href="{{ url_for('student.my_essays') }}">📝 내 첨삭</a>
    <a href="{{ url_for('student.courses') }}">📚 내 수업</a>
    <a href="{{ url_for('student.announcements') }}">📢 공지사항</a>
</div>
{% endif %}
```

### 4. Blueprint 등록

**파일**: `app/__init__.py`

```python
from app.student_portal import student_bp
app.register_blueprint(student_bp, url_prefix='/student')
```

---

## 🔑 핵심 기능 상세

### 1. 첨삭 제출 (submit_essay)

**흐름**:
1. 학생이 제목과 본문 입력
2. 제출 시 `Essay` 생성 (student_id, teacher_id 자동 연결)
3. 담당 강사에게 `Notification` 생성
4. 알림 내용: "김철수 학생이 '논술문 제목' 첨삭을 제출했습니다."
5. 관련 URL 자동 생성 (강사가 클릭하면 첨삭 페이지로 이동)

**코드**:
```python
essay = Essay(
    student_id=student.student_id,
    teacher_id=student.teacher_id,  # 학생 담당 강사
    title=title,
    essay_content=content
)
db.session.add(essay)

notification = Notification(
    user_id=student.teacher_id,
    notification_type='essay_submitted',
    title='새 첨삭 제출',
    message=f'{student.name} 학생이 "{title}" 첨삭을 제출했습니다.',
    related_url=url_for('essays.edit', essay_id=essay.essay_id)
)
db.session.add(notification)
db.session.commit()
```

### 2. 공지사항 Tier 필터링 (announcements)

**로직**:
```python
all_announcements = Announcement.query.filter(
    and_(
        Announcement.is_active == True,
        Announcement.published_at <= datetime.utcnow()
    )
).order_by(desc(Announcement.published_at)).all()

# Tier 필터링
for announcement in all_announcements:
    if announcement.target_tier and student.tier not in announcement.target_tier.split(','):
        continue  # 접근 권한 없음
```

**예시**:
- Student A (tier='A'): A등급 전용 + 전체 공지 볼 수 있음
- Student B (tier='B'): B등급 전용 + 전체 공지 볼 수 있음 (A등급 전용은 못 봄)

### 3. 읽음 자동 표시 (view_announcement)

**로직**:
```python
existing_read = AnnouncementRead.query.filter_by(
    announcement_id=announcement_id,
    user_id=current_user.user_id
).first()

if not existing_read:
    announcement_read = AnnouncementRead(
        announcement_id=announcement_id,
        user_id=current_user.user_id
    )
    db.session.add(announcement_read)
    db.session.commit()
```

학생이 공지사항을 클릭하면 자동으로 `AnnouncementRead` 레코드 생성.

### 4. 출석 현황 조회 (attendance)

**통계 자동 계산**:
- `enrollment.attendance_rate`: 출석률 (%)
- `enrollment.attended_sessions`: 출석 횟수
- `enrollment.late_sessions`: 지각 횟수
- `enrollment.absent_sessions`: 결석 횟수

이 통계는 강사가 출석을 체크할 때마다 `update_enrollment_attendance_stats()` 함수로 자동 업데이트됩니다.

---

## 🎯 사용 시나리오

### 시나리오 1: 학생이 첨삭 제출

1. 학생 로그인 → 대시보드
2. "첨삭 제출" 버튼 클릭
3. 제목: "자유 주제 논술", 본문 입력
4. "제출하기" 클릭
5. 시스템 동작:
   - Essay 생성 (student_id=김철수, teacher_id=이선생)
   - Notification 생성 (user_id=이선생, "김철수 학생이 '자유 주제 논술' 첨삭을 제출했습니다.")
6. 학생: "첨삭이 성공적으로 제출되었습니다. 담당 강사에게 알림이 전송되었습니다." 메시지 표시
7. 강사: 알림 수신 → 클릭 → 첨삭 페이지로 이동

### 시나리오 2: 학생이 출석 확인

1. 학생 로그인 → "내 수업" 또는 "출석 현황"
2. 수업별 출석률 확인:
   - 국어 논술: 출석률 95%, 출석 19회, 지각 1회, 결석 0회
3. "상세 보기" 클릭
4. 전체 출석 기록 확인:
   - 1회차: 2026-01-05 - 출석
   - 2회차: 2026-01-12 - 지각
   - 3회차: 2026-01-19 - 출석

### 시나리오 3: VIP 학생이 전용 공지 확인

1. VIP 학생 로그인 → "공지사항"
2. 공지사항 목록:
   - [전체] "2026년 1학기 개강 안내" (모든 학생 표시)
   - [VIP등급] "VIP 학생 전용 특강 안내" (VIP만 표시)
   - [A등급] "A반 특별 과제" (VIP는 못 봄)
3. "VIP 학생 전용 특강 안내" 클릭
4. 읽음 자동 표시 (AnnouncementRead 생성)
5. 다시 목록으로 돌아오면 NEW 뱃지 사라짐

---

## 🔐 보안 및 권한

### 1. 학생 식별

```python
if current_user.role == 'student':
    student = Student.query.filter_by(email=current_user.email).first()
else:  # admin
    student = Student.query.first()  # 테스트용
```

**중요**: 학생 계정은 `User.email`과 `Student.email`이 일치해야 함.

### 2. 권한 체크

모든 라우트에 `@requires_role('student', 'admin')` 데코레이터 적용.

### 3. 데이터 접근 제한

- 첨삭: 본인 첨삭만 조회 가능
  ```python
  if essay.student_id != student.student_id and current_user.role != 'admin':
      flash('접근 권한이 없습니다.', 'error')
      return redirect(url_for('student.my_essays'))
  ```

- 수업: 수강 중인 수업만 조회 가능
  ```python
  enrollment = CourseEnrollment.query.filter_by(
      course_id=course_id,
      student_id=student.student_id,
      status='active'
  ).first()

  if not enrollment and current_user.role != 'admin':
      flash('수강하지 않는 수업입니다.', 'error')
      return redirect(url_for('student.courses'))
  ```

- 공지사항: Tier 기반 필터링
  ```python
  if announcement.target_tier and student.tier not in announcement.target_tier.split(','):
      flash('접근 권한이 없습니다.', 'error')
      return redirect(url_for('student.announcements'))
  ```

---

## 📊 데이터 흐름

### 첨삭 제출 흐름

```
학생 (submit_essay.html)
  ↓ POST /student/essays/new
routes.py (submit_essay)
  ↓ Essay 생성
  ↓ Notification 생성
DB (essays, notifications)
  ↓ 알림 전송
강사 알림 수신
  ↓ 클릭
첨삭 페이지 (essays.edit)
```

### 출석 조회 흐름

```
학생 (index.html 또는 attendance.html)
  ↓ GET /student/attendance
routes.py (attendance)
  ↓ CourseEnrollment 조회
  ↓ Attendance 조회
DB (course_enrollments, attendances)
  ↓ 통계 계산 (enrollment.attendance_rate 등)
attendance.html (수업별 출석 현황 표시)
```

### 공지사항 흐름

```
관리자/강사 (admin 또는 teacher portal)
  ↓ Announcement 생성 (target_tier 설정)
DB (announcements)
  ↓
학생 (announcements.html)
  ↓ GET /student/announcements
routes.py (announcements)
  ↓ Tier 필터링
  ↓ 읽음 여부 확인
announcements.html (공지 목록 + NEW 뱃지)
  ↓ 클릭
routes.py (view_announcement)
  ↓ AnnouncementRead 생성
DB (announcement_reads)
```

---

## 🧪 테스트 시나리오

### 1. 학생 계정 생성

```sql
-- User 생성 (student 역할)
INSERT INTO users (user_id, name, email, role, role_level)
VALUES ('student-001', '김철수', 'student1@example.com', 'student', 5);

-- Student 생성
INSERT INTO students (student_id, name, email, grade, tier, teacher_id)
VALUES ('student-001', '김철수', 'student1@example.com', '중학교 2학년', 'A', 'teacher-001');
```

**중요**: `User.email`과 `Student.email`이 일치해야 학생 포털에서 정상 작동.

### 2. 첨삭 제출 테스트

1. 브라우저: http://localhost:5000/student
2. 로그인: student1@example.com
3. "첨삭 제출" 클릭
4. 제목: "테스트 첨삭", 본문: "내용..."
5. 제출
6. 강사 계정으로 로그인하여 알림 확인

### 3. 공지사항 Tier 필터링 테스트

**시나리오**:
- A등급 학생: "A등급 전용 공지" 표시됨
- B등급 학생: "A등급 전용 공지" 표시 안 됨

```sql
-- A등급 전용 공지 생성
INSERT INTO announcements (announcement_id, title, content, target_tier, author_id, is_active, published_at)
VALUES ('ann-001', 'A등급 전용 특강', '내용...', 'A', 'admin-001', 1, NOW());

-- 전체 공지 생성
INSERT INTO announcements (announcement_id, title, content, target_tier, author_id, is_active, published_at)
VALUES ('ann-002', '전체 공지', '내용...', NULL, 'admin-001', 1, NOW());
```

1. A등급 학생으로 로그인 → 공지사항 → 2개 공지 표시
2. B등급 학생으로 로그인 → 공지사항 → 1개 공지 표시 (전체 공지만)

---

## 🚀 다음 단계 (향후 구현)

### 1. 수업 자료 (materials)

**기능**:
- 강사가 업로드한 강의 자료 다운로드
- 동영상 강의 시청
- 과제 파일 다운로드

**필요한 모델**:
```python
class CourseMaterial(db.Model):
    material_id = db.Column(db.String(36), primary_key=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id'))
    title = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    material_type = db.Column(db.String(20))  # document, video, assignment
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 2. 수업 게시판 (Class Board)

**기능**:
- 수업별 질문/답변 게시판
- 학생-강사 소통
- 파일 첨부

### 3. 학습 진도 추적

**기능**:
- 수업별 진도율
- 과제 완료 여부
- 학습 목표 설정 및 달성률

### 4. 모바일 반응형 개선

**현재**: Tailwind CSS로 기본 반응형 지원
**향후**: 모바일 전용 UI/UX 개선

---

## 📝 체크리스트

### 구현 완료 항목 ✅

- [x] Student Blueprint 생성 (11개 라우트)
- [x] 템플릿 10개 생성
- [x] 첨삭 제출 기능 (자동 알림)
- [x] 내 첨삭 목록 조회
- [x] 첨삭 상세 보기
- [x] 수업 목록/상세 조회
- [x] 출석 현황 조회
- [x] 공지사항 목록/상세 (Tier 필터링)
- [x] 읽음 자동 표시
- [x] 사이드바 메뉴 추가
- [x] Blueprint 등록

### 향후 구현 항목 ⏳

- [ ] 수업 자료 업로드/다운로드
- [ ] 동영상 강의 시청
- [ ] 수업 게시판
- [ ] 과제 제출
- [ ] 학습 진도 추적
- [ ] 모바일 최적화

---

## 🎉 완료

**학생 포털 (Student Portal) 구현 완료!**

이제 학생들은:
1. ✅ 첨삭을 제출하고 담당 강사에게 자동 알림 전송
2. ✅ 제출한 첨삭 목록 및 결과 확인
3. ✅ 수강 중인 수업 및 출석 현황 조회
4. ✅ 등급별 공지사항 확인

**다음 단계**: 공지사항 시스템 완성 또는 알림 시스템 통합

---

## 📞 문의

구현 관련 문의사항은 개발 문서를 참조하거나 관리자에게 문의하세요.

**관련 문서**:
- ADMIN_PORTAL_COMPLETE.md
- TEACHER_PORTAL_COMPLETE.md
- PARENT_PORTAL_COMPLETE.md
- COURSE_SYSTEM_IMPLEMENTATION.md
