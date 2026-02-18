# 📋 Phase 3: 커뮤니티 & 도서 작업 목록

**목표**: 협업 및 참고 자료 관리 시스템 구축

**예상 기간**: 3-4주

**시작일**: 2026-02-06

---

## 🎯 Phase 3 핵심 목표

1. 도서 관리 시스템 구축
2. 커뮤니티 게시판 구축
3. 첨삭과 도서 연결 기능
4. 협업 및 공유 기능

---

## ✅ 작업 체크리스트

### 📚 1. 도서 관리 시스템 (우선순위: 높음)

#### 1.1 데이터베이스 모델
- [ ] `Book` 모델 생성
  - book_id (PK)
  - title (도서 제목)
  - author (저자)
  - publisher (출판사)
  - isbn (ISBN)
  - publication_year (출판년도)
  - category (카테고리)
  - description (설명)
  - cover_image_url (표지 이미지)
  - created_at, updated_at
  - user_id (등록자)

- [ ] `EssayBook` 관계 테이블
  - essay_id (FK)
  - book_id (FK)
  - relation_type (참고/인용/기타)

#### 1.2 도서 CRUD
- [ ] 도서 목록 페이지 (`/books`)
  - 그리드 카드 레이아웃
  - 표지 이미지 표시
  - 기본 정보 표시

- [ ] 도서 상세 페이지 (`/books/<book_id>`)
  - 도서 상세 정보
  - 이 도서를 참고한 첨삭 목록
  - 수정/삭제 버튼

- [ ] 도서 추가 페이지 (`/books/new`)
  - 폼 (제목, 저자, ISBN 등)
  - 표지 이미지 업로드 (선택)
  - ISBN 자동 검색 (선택)

- [ ] 도서 수정 페이지 (`/books/<book_id>/edit`)
  - 기존 정보 수정
  - 표지 이미지 변경

#### 1.3 검색 및 필터링
- [ ] 제목 검색
- [ ] 저자 검색
- [ ] ISBN 검색
- [ ] 카테고리 필터
- [ ] 출판년도 범위 필터

#### 1.4 첨삭-도서 연결
- [ ] 첨삭 작성 시 도서 선택
- [ ] 첨삭 결과 페이지에 참고 도서 표시
- [ ] 도서 상세 페이지에 관련 첨삭 표시

---

### 💬 2. 커뮤니티 게시판 (우선순위: 높음)

#### 2.1 데이터베이스 모델
- [ ] `Post` 모델 생성
  - post_id (PK)
  - user_id (FK)
  - title (제목)
  - content (내용)
  - category (카테고리: 공지/질문/자유/자료)
  - views (조회수)
  - likes_count (좋아요 수)
  - is_pinned (상단 고정)
  - created_at, updated_at

- [ ] `Comment` 모델 생성
  - comment_id (PK)
  - post_id (FK)
  - user_id (FK)
  - parent_comment_id (FK, nullable) - 대댓글용
  - content (내용)
  - created_at, updated_at

- [ ] `PostLike` 모델 생성
  - user_id (FK)
  - post_id (FK)
  - created_at

#### 2.2 게시판 기본 기능
- [ ] 게시판 목록 페이지 (`/community`)
  - 카테고리별 탭
  - 게시글 목록 (제목, 작성자, 날짜, 조회수, 좋아요)
  - 페이지네이션
  - 검색 기능

- [ ] 게시글 상세 페이지 (`/community/<post_id>`)
  - 게시글 내용
  - 작성자 정보
  - 조회수, 좋아요 수
  - 수정/삭제 버튼 (본인만)

- [ ] 게시글 작성 페이지 (`/community/new`)
  - 제목, 내용, 카테고리 선택
  - 마크다운 에디터 (선택)

- [ ] 게시글 수정 페이지 (`/community/<post_id>/edit`)
  - 기존 내용 수정

#### 2.3 댓글 기능
- [ ] 댓글 작성
  - AJAX 방식으로 실시간 추가
  - 댓글 목록 자동 갱신

- [ ] 대댓글 작성
  - 댓글에 대한 답글
  - 중첩 표시

- [ ] 댓글 수정/삭제
  - 본인만 가능
  - AJAX 방식

#### 2.4 좋아요 기능
- [ ] 게시글 좋아요
  - 하트 아이콘 클릭
  - AJAX 방식
  - 중복 방지

- [ ] 좋아요 취소
  - 다시 클릭하면 취소

#### 2.5 검색 및 필터링
- [ ] 제목 검색
- [ ] 내용 검색
- [ ] 작성자 검색
- [ ] 카테고리 필터
- [ ] 정렬 (최신순, 인기순, 조회순)

---

### 🔗 3. 통합 기능 (우선순위: 중간)

#### 3.1 첨삭-도서 연결
- [ ] 첨삭 작성 시 도서 선택 UI
- [ ] 첨삭 결과 페이지에 참고 도서 섹션
- [ ] 도서 상세 페이지에 관련 첨삭 목록

#### 3.2 게시판-첨삭 연결
- [ ] 게시글에서 첨삭 결과 공유 (선택)
- [ ] 첨삭 결과에서 게시글 작성 바로가기

#### 3.3 알림 시스템 (기초)
- [ ] 댓글 알림 (간단한 카운트)
- [ ] 좋아요 알림 (선택)

---

### 📱 4. UI/UX 개선 (우선순위: 중간)

#### 4.1 도서 카드
- [ ] 표지 이미지 표시
- [ ] 호버 효과
- [ ] 북마크 기능 (선택)

#### 4.2 게시판 카드
- [ ] 카테고리 배지
- [ ] 작성자 아바타
- [ ] 좋아요/댓글 수 아이콘

#### 4.3 반응형 디자인
- [ ] 모바일 최적화
- [ ] 태블릿 최적화

---

### 🔐 5. 권한 관리 (우선순위: 중간)

#### 5.1 도서 관리 권한
- [ ] 모든 강사: 도서 추가 가능
- [ ] 본인: 자신이 추가한 도서 수정/삭제
- [ ] 관리자: 모든 도서 수정/삭제

#### 5.2 게시판 권한
- [ ] 모든 강사: 게시글 작성 가능
- [ ] 본인: 자신의 게시글 수정/삭제
- [ ] 본인: 자신의 댓글 수정/삭제
- [ ] 관리자: 모든 게시글/댓글 관리

---

## 🗄️ 데이터베이스 스키마

### Book 테이블
```sql
CREATE TABLE books (
    book_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(200),
    publisher VARCHAR(200),
    isbn VARCHAR(20),
    publication_year INTEGER,
    category VARCHAR(100),
    description TEXT,
    cover_image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_isbn ON books(isbn);
```

### EssayBook 관계 테이블
```sql
CREATE TABLE essay_books (
    essay_id VARCHAR(36) NOT NULL,
    book_id VARCHAR(36) NOT NULL,
    relation_type VARCHAR(50) DEFAULT 'reference',
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (essay_id, book_id),
    FOREIGN KEY (essay_id) REFERENCES essays(essay_id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
);
```

### Post 테이블
```sql
CREATE TABLE posts (
    post_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    views INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_category ON posts(category);
CREATE INDEX idx_posts_created_at ON posts(created_at);
```

### Comment 테이블
```sql
CREATE TABLE comments (
    comment_id VARCHAR(36) PRIMARY KEY,
    post_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    parent_comment_id VARCHAR(36),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_comment_id) REFERENCES comments(comment_id) ON DELETE CASCADE
);

CREATE INDEX idx_comments_post_id ON comments(post_id);
```

### PostLike 테이블
```sql
CREATE TABLE post_likes (
    user_id VARCHAR(36) NOT NULL,
    post_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);
```

---

## 📂 파일 구조

### 새로 추가될 파일
```
app/
├── books/
│   ├── __init__.py
│   ├── routes.py
│   ├── forms.py
│   └── utils.py (선택: ISBN 검색)
├── community/
│   ├── __init__.py
│   ├── routes.py
│   ├── forms.py
│   └── utils.py
└── models/
    ├── book.py
    └── community.py

templates/
├── books/
│   ├── index.html
│   ├── detail.html
│   ├── new.html
│   └── edit.html
└── community/
    ├── index.html
    ├── detail.html
    ├── new.html
    └── edit.html
```

---

## 🚀 시작 순서 (우선순위 기반)

### Week 1: 도서 관리 시스템
1. 데이터베이스 모델 생성 (Book, EssayBook)
2. 도서 CRUD 구현
3. 도서 목록/상세 페이지
4. 검색 및 필터링

### Week 2: 게시판 기본 기능
5. 데이터베이스 모델 생성 (Post, Comment, PostLike)
6. 게시판 목록/상세 페이지
7. 게시글 작성/수정/삭제
8. 검색 및 필터링

### Week 3: 댓글 & 좋아요
9. 댓글 작성/수정/삭제
10. 대댓글 기능
11. 좋아요 기능 (AJAX)

### Week 4: 통합 & 최적화
12. 첨삭-도서 연결
13. UI/UX 개선
14. 권한 관리
15. 테스트 및 버그 수정

---

## 🎨 UI 컴포넌트

### 도서 카드
```
┌─────────────────┐
│   [표지 이미지]  │
│                 │
│  도서 제목       │
│  저자: OOO      │
│  출판사: XXX    │
│  출판년도: 2024 │
│                 │
│  [상세보기]     │
└─────────────────┘
```

### 게시글 카드
```
┌──────────────────────────────┐
│ [카테고리] 게시글 제목        │
│                              │
│ 👤 작성자   📅 2024-01-01    │
│ 👁 123    ❤️ 45    💬 12    │
└──────────────────────────────┘
```

### 댓글 구조
```
┌──────────────────────────┐
│ 👤 작성자  2024-01-01    │
│ 댓글 내용...             │
│ [답글]  [수정]  [삭제]   │
│                          │
│   └─ 👤 작성자2          │
│      대댓글 내용...       │
└──────────────────────────┘
```

---

## 📝 API 엔드포인트 (AJAX용)

### 좋아요
- `POST /api/posts/<post_id>/like` - 좋아요 추가
- `DELETE /api/posts/<post_id>/like` - 좋아요 취소

### 댓글
- `POST /api/posts/<post_id>/comments` - 댓글 작성
- `PUT /api/comments/<comment_id>` - 댓글 수정
- `DELETE /api/comments/<comment_id>` - 댓글 삭제

### 조회수
- `POST /api/posts/<post_id>/view` - 조회수 증가

---

## 🔜 다음 단계

**가장 먼저 시작할 작업:**
1. Book, EssayBook 모델 생성
2. Post, Comment, PostLike 모델 생성
3. 데이터베이스 마이그레이션
4. books, community 블루프린트 생성
5. 기본 라우트 및 템플릿 작성

---

**작성일**: 2026-02-06
**최종 수정일**: 2026-02-06
**상태**: 📝 준비 중
