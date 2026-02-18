# 🗄️ MOMOAI v4.0 데이터베이스 스키마

## 📊 ERD 개요

```
users (사용자)
  ├─→ students (담당 학생들)
  │     └─→ essays (학생의 첨삭들)
  │           ├─→ essay_versions (버전 관리)
  │           ├─→ essay_results (점수/결과)
  │           ├─→ essay_scores (18개 지표)
  │           ├─→ essay_notes (강사 메모)
  │           └─→ essay_books → books
  │
  ├─→ essays (직접 첨삭한 작업들)
  ├─→ posts (작성한 게시글)
  ├─→ comments (작성한 댓글)
  └─→ books (등록한 도서)

books (도서 DB)
  ├─→ book_tags (태그)
  └─→ essay_books (첨삭과 연결)

posts (게시판)
  ├─→ comments (댓글/대댓글)
  └─→ post_likes (좋아요)
```

---

## 📋 테이블 상세 설계

### 1. 사용자 관리

#### `users` (사용자 계정)
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'teacher', 'student', 'parent')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role)
);
```

**설명**:
- `role`: 4가지 역할 (admin, teacher, student, parent)
- `is_active`: 계정 활성화 여부
- Phase 1에서는 teacher/admin만 사용

---

### 2. 학생 관리

#### `students` (학생 정보)
```sql
CREATE TABLE students (
    student_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    grade VARCHAR(20) NOT NULL CHECK (grade IN ('초등', '중등', '고등')),
    email VARCHAR(255),
    phone VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_teacher (teacher_id),
    INDEX idx_name (name)
);
```

**설명**:
- `teacher_id`: 담당 강사
- `user_id`: 향후 학생 계정 연결용 (Phase 4, NULL 허용)
- `notes`: 강사 메모

#### `parent_student_relations` (학부모-자녀 연결)
```sql
CREATE TABLE parent_student_relations (
    id SERIAL PRIMARY KEY,
    parent_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    relationship VARCHAR(20) CHECK (relationship IN ('부', '모', '보호자')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_user_id, student_id)
);
```

**설명**: Phase 4에서 사용

---

### 3. 첨삭 관리

#### `essays` (첨삭 작업)
```sql
CREATE TABLE essays (
    essay_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255),
    original_text TEXT NOT NULL,
    grade VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'processing', 'reviewing', 'completed', 'failed')),
    current_version INTEGER DEFAULT 1,
    is_finalized BOOLEAN DEFAULT FALSE,
    finalized_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_student (student_id),
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at DESC)
);
```

**설명**:
- `status`:
  - draft: 초안
  - processing: 생성 중
  - reviewing: 검토 중 (수정 가능)
  - completed: 완료
  - failed: 실패
- `current_version`: 현재 버전 번호
- `is_finalized`: 완료 버튼을 눌렀는지 여부

#### `essay_versions` (첨삭 버전 관리)
```sql
CREATE TABLE essay_versions (
    version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    html_content TEXT NOT NULL,
    html_path VARCHAR(500),
    revision_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(essay_id, version_number),
    INDEX idx_essay (essay_id)
);
```

**설명**:
- `version_number`: 1, 2, 3...
- `revision_note`: 수정 요청 내용 (v2부터 기록)
- `html_content`: 생성된 HTML 전체 저장

#### `essay_results` (첨삭 결과)
```sql
CREATE TABLE essay_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES essay_versions(version_id) ON DELETE CASCADE,
    html_path VARCHAR(500),
    pdf_path VARCHAR(500),
    total_score DECIMAL(4,1),
    final_grade VARCHAR(10),
    ai_detection_score INTEGER,
    plagiarism_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_essay (essay_id),
    INDEX idx_version (version_id)
);
```

**설명**:
- 각 버전마다 결과 저장
- `pdf_path`: 완료(finalize) 시에만 생성

#### `essay_scores` (18개 지표 점수)
```sql
CREATE TABLE essay_scores (
    score_id SERIAL PRIMARY KEY,
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES essay_versions(version_id) ON DELETE CASCADE,
    category VARCHAR(20) NOT NULL CHECK (category IN ('사고유형', '통합지표')),
    indicator_name VARCHAR(50) NOT NULL,
    score DECIMAL(3,1) NOT NULL CHECK (score >= 0 AND score <= 10),
    INDEX idx_essay (essay_id),
    INDEX idx_version (version_id)
);
```

**설명**:
- `category`: 사고유형(9개) / 통합지표(9개)
- `indicator_name`: 요약, 비교, 적용, 평가, 비판, 문제해결...

#### `essay_notes` (강사 주의사항)
```sql
CREATE TABLE essay_notes (
    note_id SERIAL PRIMARY KEY,
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    note_type VARCHAR(20) CHECK (note_type IN ('주의사항', '참고사항')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_essay (essay_id)
);
```

---

### 4. 도서 데이터베이스

#### `books` (도서 정보)
```sql
CREATE TABLE books (
    book_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    publisher VARCHAR(255),
    isbn VARCHAR(50),
    summary TEXT,
    table_of_contents TEXT,
    publication_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_title (title),
    INDEX idx_author (author),
    INDEX idx_isbn (isbn)
);
```

#### `book_tags` (도서 태그)
```sql
CREATE TABLE book_tags (
    tag_id SERIAL PRIMARY KEY,
    book_id UUID NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    tag_name VARCHAR(50) NOT NULL,
    INDEX idx_book (book_id),
    INDEX idx_tag (tag_name)
);
```

#### `essay_books` (첨삭-도서 연결)
```sql
CREATE TABLE essay_books (
    id SERIAL PRIMARY KEY,
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    book_id UUID NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    relevance INTEGER CHECK (relevance >= 1 AND relevance <= 5),
    INDEX idx_essay (essay_id),
    INDEX idx_book (book_id)
);
```

**설명**:
- `relevance`: 관련도 (1-5)

---

### 5. 커뮤니티 게시판

#### `posts` (게시글)
```sql
CREATE TABLE posts (
    post_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    likes_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_created (created_at DESC),
    INDEX idx_pinned (is_pinned)
);
```

#### `comments` (댓글)
```sql
CREATE TABLE comments (
    comment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    parent_comment_id UUID REFERENCES comments(comment_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_post (post_id),
    INDEX idx_user (user_id),
    INDEX idx_parent (parent_comment_id)
);
```

**설명**:
- `parent_comment_id`: 대댓글용 (NULL이면 최상위 댓글)

#### `post_likes` (좋아요)
```sql
CREATE TABLE post_likes (
    like_id SERIAL PRIMARY KEY,
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id),
    INDEX idx_post (post_id),
    INDEX idx_user (user_id)
);
```

---

### 6. 일괄 첨삭 (기존 유지)

#### `batch_tasks` (일괄 작업)
```sql
CREATE TABLE batch_tasks (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    file_name VARCHAR(255),
    total_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_status (status)
);
```

---

## 📐 인덱스 전략

### 주요 쿼리 패턴별 인덱스

1. **사용자 인증**
   - `users.email` (UNIQUE INDEX)

2. **학생 조회**
   - `students.teacher_id` (강사별 학생 목록)
   - `students.name` (이름 검색)

3. **첨삭 조회**
   - `essays.student_id` (학생별 첨삭 이력)
   - `essays.user_id` (강사별 첨삭 목록)
   - `essays.created_at DESC` (최신순 정렬)
   - `essays.status` (상태별 필터)

4. **게시판 조회**
   - `posts.created_at DESC` (최신순)
   - `posts.is_pinned` (공지사항)

---

## 🔄 마이그레이션 전략

### Phase 1: 기존 → 신규 구조

**기존 테이블**:
- `tasks` → `essays` + `essay_versions` + `essay_results`
- `batch_tasks` → 유지
- `batch_results` → 제거 (essays로 통합)

**마이그레이션 스크립트**:
```python
# migrations/migrate_v3_to_v4.py
# 1. users 테이블 생성
# 2. 기존 tasks → essays + essay_versions + essay_results 변환
# 3. students 테이블 생성 (기존 데이터에서 학생 정보 추출)
```

---

## 📊 예상 데이터 볼륨 (연간)

- users: ~100명 (강사)
- students: ~1,000명
- essays: ~10,000건
- essay_versions: ~15,000건 (평균 1.5 버전)
- essay_scores: ~180,000건 (10,000 × 18)
- books: ~500권
- posts: ~1,000개
- comments: ~5,000개

**예상 DB 크기**: 1-2GB/년

---

**작성일**: 2026-02-06
**최종 수정일**: 2026-02-06
