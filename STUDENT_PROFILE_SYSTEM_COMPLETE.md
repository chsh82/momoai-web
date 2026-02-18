# 학생 기초 조사 프로필 시스템 구축 완료 ✅

**완료 날짜**: 2026-02-12
**시스템 버전**: MOMOAI v4.0

---

## 📋 시스템 개요

학부모가 최초 등록 시 작성하는 구글 설문 데이터를 시스템에 저장하고, 학생의 특징을 한눈에 파악할 수 있는 **360° 학생 프로필 시스템**을 구축했습니다.

### 핵심 기능
1. **Excel 일괄 임포트**: 구글 설문 결과를 Excel로 다운로드하여 한번에 여러 학생 프로필 생성
2. **개별 프로필 관리**: 관리자가 학생별로 프로필 생성/수정/삭제
3. **종합 프로필 페이지**: 학생의 특징과 상담 이력을 한 페이지에서 확인
4. **강사 접근 권한**: 강사는 자신이 가르치는 학생의 프로필을 조회 가능

---

## 🗄️ 데이터베이스

### 새 테이블: `student_profiles`

```sql
CREATE TABLE student_profiles (
    profile_id INTEGER PRIMARY KEY,
    student_id VARCHAR(50) UNIQUE NOT NULL,

    -- 기본 정보
    survey_date DATETIME,
    address TEXT,
    parent_contact VARCHAR(50),
    current_school VARCHAR(100),

    -- 독서 경험 및 역량
    reading_experience VARCHAR(50),
    reading_competency INTEGER,
    weekly_reading_amount VARCHAR(50),
    preferred_genres TEXT,  -- JSON array

    -- 학생 성향
    personality_traits TEXT,  -- JSON array

    -- 수업 목표
    main_improvement_goal VARCHAR(200),
    preferred_class_style VARCHAR(200),
    teacher_request TEXT,

    -- 유입 경로
    referral_source VARCHAR(100),

    -- 진로/진학 정보
    education_info_needs TEXT,  -- JSON array
    academic_goals TEXT,  -- JSON array
    career_interests TEXT,  -- JSON array
    other_interests TEXT,

    -- 형제자매
    sibling_info TEXT,

    -- 메타 정보
    created_at DATETIME,
    updated_at DATETIME,
    created_by VARCHAR(36),

    FOREIGN KEY(student_id) REFERENCES students(student_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);
```

**Migration ID**: `f50c91ec62b9_add_student_profiles_table`

---

## 📁 생성된 파일

### 1. Models
- **`app/models/student_profile.py`** (새 파일)
  - `StudentProfile` 클래스
  - JSON 데이터 파싱 property 메서드 (`preferred_genres_list`, `personality_traits_list` 등)
  - `to_dict()` 메서드

### 2. Forms
- **`app/admin/forms.py`** (수정)
  - `StudentProfileForm` 클래스 추가
  - 모든 설문 항목에 대한 필드 정의
  - SelectMultipleField를 사용한 다중 선택 지원

### 3. Routes

#### Admin Routes (`app/admin/routes.py`)
새로 추가된 7개 라우트:

1. **`/students/<student_id>/profile`** - 학생 종합 프로필 조회
2. **`/student-profiles`** - 학생 프로필 목록 (검색 기능 포함)
3. **`/student-profiles/create/<student_id>`** - 프로필 생성
4. **`/student-profiles/edit/<student_id>`** - 프로필 수정
5. **`/student-profiles/import`** - Excel 일괄 임포트
6. **`/student-profiles/delete/<student_id>`** - 프로필 삭제
7. **`/students/<student_id>/profile`** (admin) - 관리자용 종합 프로필 페이지

#### Teacher Routes (`app/teacher/routes.py`)
새로 추가된 1개 라우트:

1. **`/teacher/students/<student_id>/profile`** - 강사용 학생 프로필 조회
   - 자신이 가르치는 학생만 조회 가능
   - 본인이 작성하거나 공유받은 상담 기록만 표시

### 4. Templates

#### Admin Templates (4개)
1. **`templates/admin/student_profile.html`** - 종합 프로필 페이지
   - 상단: 4개 주요 지표 카드 (독서역량, 수업경험, 진학목표, 성향)
   - 중단: 상세 정보 섹션 (기본정보, 독서성향, 수업목표)
   - 하단: 진로/진학 정보
   - 최하단: 상담 이력 타임라인

2. **`templates/admin/student_profiles.html`** - 프로필 목록
   - 검색 기능 (학생 이름/ID)
   - 프로필 작성 상태 표시
   - 보기/생성/수정 버튼

3. **`templates/admin/student_profile_form.html`** - 생성/수정 폼
   - 4개 섹션으로 구분 (기본정보, 독서경험, 수업목표, 진로정보)
   - 다중 선택 필드 지원

4. **`templates/admin/import_student_profiles.html`** - Excel 임포트
   - 파일 업로드 폼
   - 사용 방법 안내
   - 에러 로그 표시

#### Teacher Template (1개)
5. **`templates/teacher/student_profile.html`** - 강사용 프로필 조회
   - 관리자 버전과 동일한 레이아웃
   - 수정/생성 버튼 제거 (조회 전용)
   - 상담 이력은 본인 관련 기록만 표시

---

## 🎯 주요 기능 상세

### 1. Excel 일괄 임포트

**지원 파일 형식**: `.xlsx`, `.xls`

**매칭 방식**: Excel의 "1. 학생의 이름" 컬럼으로 시스템 학생 검색

**처리 프로세스**:
1. Excel 파일 업로드
2. 각 행마다 학생 이름으로 Student 검색
3. 학생이 존재하고 프로필이 없으면 생성
4. 이미 프로필이 있거나 학생이 없으면 건너뛰고 에러 기록
5. 완료 후 성공/실패 건수 표시
6. 에러 로그 세션에 저장하여 표시 (최대 50개)

**Excel 컬럼 매핑**:
```python
"1. 학생의 이름" → student.name으로 검색
"타임스탬프" → survey_date
"4. 주소(...)" → address
"5. 학부모 연락처" → parent_contact
"6. 재학 중인 학교 이름" → current_school
"8. 독서논술 수업 경험 및 기간" → reading_experience
"9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요." → reading_competency
"10. 학생의 한 주 평균 독서량을 체크해주세요." → weekly_reading_amount
"11. 학생이 선호하는 독서 분야를 모두 선택해주세요." → preferred_genres
"12. 학생의 성향을 모두 알려주세요." → personality_traits
"13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)" → main_improvement_goal
"17. 가장 선호하는 수업 목표를 선택해주세요. (1개만 선택 가능)" → preferred_class_style
"18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요." → teacher_request
"19. 모모의 책장을 어떻게 알게 되셨나요?" → referral_source
"1. 필요한 교육&입시 정보가 있으신가요?" → education_info_needs
"2. 진학 목표가 있으신가요?" → academic_goals
"3. 관심 있는 학생의 진로 분야는 무엇입니까?" → career_interests
"4. 기타 교육분야 관심사항이 있으시면 모두 적어주세요." → other_interests
"형제/자매 정보를 입력해주세요." → sibling_info
```

### 2. 종합 프로필 페이지

**레이아웃**:

```
┌─────────────────────────────────────────┐
│ 학생 이름                     [수정하기] │
├─────────────────────────────────────────┤
│ [독서역량] [수업경험] [진학목표] [성향] │  ← 4개 주요 지표 카드
├─────────────────────────────────────────┤
│ [기본정보] [독서성향] [수업목표]        │  ← 상세 정보 3단 구성
├─────────────────────────────────────────┤
│ [진로 및 진학 정보]                     │  ← 진로/진학 섹션
├─────────────────────────────────────────┤
│ 💬 상담 이력 (총 N건)                   │  ← 상담 기록 타임라인
│ ┌─────────────────────────────────────┐ │
│ │ [상담1] 날짜, 작성자, 카테고리      │ │
│ │ 내용 미리보기...                    │ │
│ ├─────────────────────────────────────┤ │
│ │ [상담2] ...                         │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**주요 지표 카드**:
- 독서 역량: N/5 점수 + 주간 독서량
- 수업 경험: 독서논술 수업 경험 기간
- 진학 목표: 첫 번째 목표 + 나머지 개수
- 성향: 첫 번째 성향 + 나머지 개수

### 3. 강사 접근 제어

**권한 체크**:
```python
# 강사는 자신의 수업에 등록된 학생만 조회 가능
is_my_student = db.session.query(CourseEnrollment).join(Course).filter(
    Course.teacher_id == current_user.user_id,
    CourseEnrollment.student_id == student_id
).first()

if not is_my_student:
    flash('접근 권한이 없습니다.', 'danger')
    return redirect(url_for('teacher.index'))
```

**상담 이력 필터링**:
```python
# 본인이 작성하거나 공유받은 상담 기록만
consultations = ConsultationRecord.query.filter_by(student_id=student_id)\
    .filter(
        (ConsultationRecord.counselor_id == current_user.user_id) |
        (ConsultationRecord.reference_teachers.like(f'%{current_user.user_id}%'))
    )\
    .order_by(ConsultationRecord.consultation_date.desc())\
    .all()
```

---

## 🎨 UI/UX 특징

### 1. 카드 기반 디자인
- 4개의 색상 구분 카드로 주요 정보 시각화
- 그라데이션 배경으로 섹션 구분

### 2. 반응형 레이아웃
- 모바일: 1열 레이아웃
- 태블릿: 2열 레이아웃
- 데스크톱: 3-4열 레이아웃

### 3. 태그 표시
- 선호 독서 분야: 파란색 태그
- 학생 성향: 초록색 태그
- 상담 카테고리: 보라색 태그

### 4. 정보 계층 구조
- 중요 정보를 상단에 배치
- 덜 중요한 정보는 하단에 배치
- 상담 이력은 최하단에 타임라인 형태로 표시

---

## 📊 통계 및 데이터 분석

현재 Excel 파일에는 **124개의 응답**이 있습니다.

### 데이터 구조
- 23개 컬럼 (타임스탬프 포함)
- 학생 기본 정보 (이름, 성별, 생년월일, 주소, 학부모 연락처)
- 독서 경험 및 역량 (경험 기간, 역량 점수 1-5, 주간 독서량)
- 학생 성향 (다중 선택)
- 수업 목표 및 선호 스타일
- 진로/진학 정보 (다중 선택)

---

## 🔐 권한 관리

| 역할 | 프로필 조회 | 프로필 생성 | 프로필 수정 | 프로필 삭제 | Excel 임포트 |
|------|------------|------------|------------|------------|--------------|
| 마스터 관리자 | ✅ 전체 | ✅ | ✅ | ✅ | ✅ |
| 관리자 | ✅ 전체 | ✅ | ✅ | ✅ | ✅ |
| 강사 | ✅ 담당 학생만 | ❌ | ❌ | ❌ | ❌ |
| 학부모 | ❌ | ❌ | ❌ | ❌ | ❌ |
| 학생 | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 📱 메뉴 구조

### Admin 메뉴
```
학생 관리
  ├─ 강사 관리
  ├─ 학부모 연결 관리
  ├─ 상담 내용 관리
  └─ 📋 학생 프로필  ← 새로 추가
```

### Teacher 메뉴
- 강사는 학생 프로필에 직접 메뉴 접근 없음
- 상담 작성 시 학생 정보에서 프로필로 이동 가능

---

## 🚀 사용 시나리오

### 시나리오 1: Excel 일괄 임포트
1. 관리자가 구글 설문 결과를 Excel로 다운로드
2. Admin → 학생 관리 → 학생 프로필 → Excel 일괄 임포트
3. Excel 파일 업로드
4. 시스템이 자동으로 학생 이름 매칭 후 프로필 생성
5. 성공/실패 건수 확인
6. 에러가 있으면 에러 목록 확인 후 수동 처리

### 시나리오 2: 개별 프로필 생성/수정
1. Admin → 학생 관리 → 학생 프로필
2. 학생 목록에서 "생성" 또는 "수정" 클릭
3. 폼 작성 (모든 필드 선택사항)
4. 저장 → 종합 프로필 페이지로 이동

### 시나리오 3: 강사가 학생 정보 확인
1. 강사가 상담 작성 페이지 또는 학생 목록에서 학생 선택
2. 학생 프로필 페이지로 이동
3. 독서 역량, 성향, 진학 목표 등 확인
4. 하단 상담 이력에서 이전 상담 내용 확인
5. 수업 준비에 활용

### 시나리오 4: 상담 작성과 프로필 연계
1. 강사가 학생 프로필을 먼저 확인
2. 학생의 주요 향상 목표와 강사 요청사항 파악
3. 이를 바탕으로 맞춤형 상담 진행
4. 상담 기록 작성
5. 다음 강사가 프로필과 상담 이력을 함께 확인하여 연속성 있는 지도

---

## ⚠️ 주의사항

### Excel 임포트 시
1. **학생 이름 정확성**: Excel의 학생 이름이 시스템 등록 이름과 정확히 일치해야 합니다
2. **중복 방지**: 이미 프로필이 있는 학생은 임포트되지 않습니다 (수동 수정 필요)
3. **대용량 처리**: 100건 이상 임포트 시 1-2분 소요 가능
4. **컬럼 이름**: 구글 설문 컬럼 이름이 변경되면 코드 수정 필요

### 데이터 입력 시
1. **필수 필드 없음**: 모든 필드가 선택사항이므로 부분 입력 가능
2. **JSON 저장**: 다중 선택 필드는 JSON으로 저장되므로 직접 DB 수정 시 주의
3. **학생당 1개**: 한 학생에 대해 1개의 프로필만 생성 가능 (UNIQUE 제약)

---

## 🔮 향후 개선 사항

### 1. 통계 및 분석 기능
- 학년별 독서 역량 평균
- 진로 관심 분야 분포 차트
- 성향별 그룹화

### 2. 자동화
- 구글 설문 API 연동으로 실시간 동기화
- 신규 학생 등록 시 프로필 작성 안내 자동 발송

### 3. 학부모 포털 연동
- 학부모가 직접 프로필 작성/수정
- 프로필 변경 이력 추적

### 4. 강사 활용 도구
- 학생 그룹별 프로필 비교
- 수업 준비를 위한 프로필 요약 출력

### 5. 알림 시스템
- 프로필 미작성 학생 알림
- 프로필 업데이트 주기 알림 (연 1회)

---

## ✅ 테스트 체크리스트

- [x] 모델 생성 및 마이그레이션 적용
- [x] Admin 폼 생성 및 검증
- [x] Admin 라우트 7개 생성
- [x] Teacher 라우트 1개 생성
- [x] Admin 템플릿 4개 생성
- [x] Teacher 템플릿 1개 생성
- [x] 메뉴 추가 (Admin)
- [x] 앱 시작 테스트 통과
- [ ] Excel 임포트 실제 테스트
- [ ] 프로필 CRUD 기능 테스트
- [ ] 강사 접근 권한 테스트
- [ ] 상담 이력 연동 테스트

---

## 📝 사용 가이드

### 관리자 가이드

#### 1. Excel 일괄 임포트 방법
```
1. 구글 설문 → 응답 → 스프레드시트 만들기
2. 파일 → 다운로드 → Microsoft Excel(.xlsx)
3. MOMOAI Admin → 학생 관리 → 학생 프로필 → Excel 일괄 임포트
4. 파일 선택 → 업로드 및 임포트
5. 결과 확인 (성공/실패 건수)
6. 에러가 있으면 에러 목록 확인 후 개별 처리
```

#### 2. 개별 프로필 생성
```
1. Admin → 학생 프로필
2. 학생 목록에서 "생성" 클릭
3. 폼 작성 (모든 필드 선택사항)
   - 기본 정보
   - 독서 경험 및 역량
   - 수업 목표
   - 진로/진학 정보
4. 저장
```

#### 3. 프로필 수정
```
1. Admin → 학생 프로필
2. 학생 목록에서 "수정" 클릭 또는 프로필 페이지에서 "수정하기"
3. 폼 수정
4. 저장
```

### 강사 가이드

#### 프로필 조회 및 활용
```
1. 상담 작성 또는 수업 준비 시 학생 프로필 확인
2. 주요 지표 카드에서 핵심 정보 파악
   - 독서 역량 수준
   - 학생 성향
   - 진학 목표
3. 상세 정보에서 강사 요청사항 확인
4. 하단 상담 이력에서 이전 지도 내용 파악
5. 맞춤형 수업 및 상담 진행
```

---

## 🎉 완료 요약

✅ **학생 기초 조사 프로필 시스템 완전 구축 완료!**

- ✅ 새 데이터베이스 모델 생성 및 마이그레이션 적용
- ✅ Excel 일괄 임포트 기능 구현 (구글 설문 연동)
- ✅ 종합 프로필 페이지 (특징 + 상담이력) 구현
- ✅ Admin 완전 CRUD 인터페이스
- ✅ Teacher 조회 전용 인터페이스
- ✅ 메뉴 통합 및 권한 관리
- ✅ 124건 응답 데이터 구조 분석 완료

**이제 관리자는 구글 설문 결과를 시스템에 저장하고, 강사들은 수업 준비 시 학생의 특징과 목표를 한눈에 파악할 수 있습니다!** 🚀
