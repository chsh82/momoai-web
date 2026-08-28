# momoai.kr 코드베이스 조사 보고서

조사일: 2026-08-28

> 이 문서는 마일리지·뱃지 기능 추가를 위한 **읽기 전용 사전 조사**다. 코드에서 직접 확인한 사실만 적었고, 확인하지 못한 항목은 "확인 불가"로 표시했다. 모든 항목에 근거 파일 경로(`path:line`)를 붙였다. 환경변수는 키 이름만 기재했고 값은 적지 않았다.
>
> **전제 정정**: 원 조사 지시서는 Next.js/Supabase/TypeScript 스택을 가정하고 있었으나, 이 프로젝트는 **Flask + Flask-SQLAlchemy + Jinja2 서버사이드 렌더링** 앱이다(TypeScript, Supabase, RLS, Server Action 개념 자체가 없음). 아래 항목들은 실제 스택에 맞춰 대응 개념으로 조사했다.

---

## 1. 프로젝트 기본 구조

### 프레임워크와 버전
Flask 3.1.2 (`requirements.txt:26`), Flask-SQLAlchemy 3.1.1 (`requirements.txt:29`), SQLAlchemy 2.0.46 (`requirements.txt:103`), Flask-Migrate 4.1.0 (`requirements.txt:28`), alembic 1.18.3 (`requirements.txt:2`), Flask-Login 0.6.3 (`requirements.txt:27`), Werkzeug 3.1.5 (`requirements.txt:120`). 서버사이드 렌더링(Jinja2 3.1.6, `requirements.txt:55`) 기반. `package.json`은 Tailwind/PostCSS 빌드 전용(`package.json:6-11`)이며 프런트엔드 프레임워크가 아니다.

### 정적 타입 체크
없음. mypy 등 관련 패키지·설정 파일 없음.

### 주요 의존성
- 인증: Flask-Login 0.6.3, 세션 기반. `User(UserMixin)` (`app/models/user.py:9`)
- ORM/마이그레이션: SQLAlchemy 2.0.46 + Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.1.0 + alembic 1.18.3
- 배치: APScheduler 3.10.4 (`requirements.txt:1`), `app/utils/scheduler.py`에서 초기화 (`app/__init__.py:510-515`)
- 알림: pywebpush 2.0.0(Web Push), Flask-Mail 0.10.0(이메일), 자체 SMS/카카오톡 발송(`app/models/message.py`, `app/utils/sms.py`)
- 결제: 토스페이먼츠 연동(`app/payment/routes.py:2`), `TOSS_CLIENT_KEY`/`TOSS_SECRET_KEY`(`config.py:38-40`)
- Rate limiting: Flask-Limiter 3.7.0(`app/extensions.py:7-11`, memory:// 스토리지)
- AI: anthropic 0.77.1, google-generativeai 0.8.6 — 첨삭/OCR에 Claude·Gemini 병행 사용(`app/models/api_usage_log.py`)
- UI: Tailwind CSS 3.4.1(devDependency), 상태관리/날짜 라이브러리 없음(서버사이드 렌더링이라 불필요)

### `app/` 폴더 구조 (2단계)
`app/__init__.py`(앱 팩토리), `app/extensions.py`(limiter/mail)

| 폴더 | 역할 |
|---|---|
| `admin/` | 관리자 블루프린트(가장 방대, 8181줄) |
| `auth/` | 로그인/회원가입/이메일 인증 |
| `books/` | 도서 관리, ISBN 조회 |
| `community/` | 커뮤니티 게시판(글/댓글/좋아요) |
| `curriculum/` | "모모의 책장" 커리큘럼(분기·주차) 관리 |
| `dashboard/` | 현재 미사용(블루프린트 등록 주석 처리, `app/__init__.py:170-172`) |
| `essays/` | 첨삭 핵심 모듈(OCR/AI 첨삭 서비스 다수) |
| `harkness/` | 하크니스(토론) 게시판 |
| `inquiry/` | 문의 게시판 |
| `library/` | 명예의 전당, 입시정보 |
| `messages/` | 강사↔관리자 1:1 내부 메시지 |
| `models/` | SQLAlchemy 모델 패키지(2절 참조) |
| `news/` | "모모 소식"(정적 소개 콘텐츠 관리) |
| `notifications/` | 알림센터 |
| `parent_portal/` | 학부모 포털 |
| `payment/` | 토스페이먼츠 결제 |
| `profile/` | 마이페이지 |
| `search/` | 검색 |
| `services/` | 서비스 계층(현재 `payment_calculator.py` 하나뿐) |
| `student_portal/` | 학생 포털(퇴원 7일 경과 시 접근 차단 훅 포함) |
| `students/` | 학생 관리(관리자용) |
| `teacher/` | 강사 포털(5226줄) |
| `utils/` | 권한 데코레이터, 스케줄러, PDF/이미지 처리 등 공용 유틸 |
| `zoom/` | Zoom 연동 |

### 실행·빌드·배포 스크립트
- 실행: `run.py` → `create_app(config_name)`, `FLASK_ENV`로 development/production 전환
- CSS 빌드: `npm run build:css`(Tailwind+PostCSS, `package.json:7-9`)
- 배포: `deploy.sh`(git pull → pip install → `npm run build:css` → DB 백업 → `flask db upgrade` → `systemctl restart momoai`) + `.github/workflows/deploy.yml`(master push 시 SSH로 GCP 서버 배포)
- 인프라: `momoai.service`(systemd, Gunicorn), `nginx_momoai.conf`(HTTPS 리버스 프록시, `client_max_body_size 150M`, `proxy_read_timeout 300s`)
- **문서 간 불일치 발견**: `deploy.sh:59`는 `DATABASE_URL="sqlite:///momoai.db"`를 명시하는 반면 `GCP_DEPLOYMENT_GUIDE.md:177-271`는 PostgreSQL 설치를 전제로 설명함. `config.py:61-64`의 `pool_recycle=280`(Cloud SQL 유휴 연결 대응 주석)은 운영 DB가 Postgres/MySQL 계열임을 시사 — 실제 운영 DB 종류는 코드만으로 확정 불가(10절·C항목 참고).

---

## 2. 데이터베이스

### 사용 DB
`config.py:58-59`: `DATABASE_URL` 환경변수가 있으면 사용, 없으면 `sqlite:///instance/momoai.db` 기본값. 개발환경 기본은 SQLite. `requirements-prod.txt:8-9`에 `psycopg2-binary`(권장 주석)와 `pymysql`(대안 주석) 둘 다 있어 운영 DB 종류는 배포 시점 설정에 좌우됨(값은 `.env`류라 미기재).

### 마이그레이션
- 위치: `migrations/versions/`(47개 파일), `migrations/alembic.ini`, `migrations/env.py` — Flask-Migrate 표준 구조
- 파일명 규칙: alembic 표준 `{revision_hash}_{설명}.py`
- 최근 파일 패턴(`migrations/versions/d391a7c4e8b2_...py`): `upgrade()`에서 `sa.inspect(conn)`로 컬럼 존재를 먼저 확인 후 없을 때만 `add_column` — 재실행 안전 설계
- **중요한 불일치**: `deploy.sh:60`/`GCP_DEPLOYMENT_GUIDE.md:280`는 `flask db upgrade`를 쓰지만, 실제 `.github/workflows/deploy.yml:48-51`이 실행하는 것은 `migrations/`가 아니라 **루트의 애드혹 `migrate_*.py` 스크립트 4개**이며 실패해도 `|| echo "...failed (continuing)"`로 넘어간다. 루트에 `migrate_*.py`가 24개 존재(`migrate_role_levels.py` 등). 즉 **현재 배포 파이프라인이 실제로 쓰는 마이그레이션 방식은 alembic이 아니라 애드혹 스크립트**로 보인다(10절·C항목 참고).
- `app/__init__.py:502-507`에서 `db.create_all()`도 앱 기동 시 병행 실행 — 새 테이블은 이걸로 생성되지만 기존 테이블 컬럼 추가는 마이그레이션(또는 애드혹 스크립트)이 필요.

### 전체 테이블 목록 (`app/models/` 기준, 총 53개 모델 파일 / 약 70개 클래스)

| 파일 | 클래스 | 역할 |
|---|---|---|
| user.py | User | 전 역할 통합 계정(role/role_level) |
| student.py | Student | 학생 정보(학년/등급tier/상태) |
| essay.py | Essay, EssayVersion, EssayResult, CorrectionAttachment | 첨삭 본체/버전/결과/첨부 |
| essay_score.py | EssayScore, EssayNote | 첨삭 세부 점수/주의사항 |
| book.py | Book, BookRating, EssayBook | 도서/평점/첨삭-도서 연결 |
| community.py | Post, Comment, PostLike | 게시글/댓글/좋아요 |
| notification.py | Notification | 알림(웹푸시 발송 헬퍼 포함) |
| tag.py | Tag, PostTag, Bookmark | 태그, 북마크 |
| post_file.py / post_image.py | PostFile, PostImage | 첨부파일/이미지 |
| course.py | Course, CourseEnrollment, CourseSession | 수업/수강신청/회차 |
| attendance.py | Attendance | 출석(참여도/이해도 별점 포함) |
| payment.py | Payment | 결제 |
| parent_student.py | ParentStudent | 학부모-학생 연결 |
| teacher_feedback.py | TeacherFeedback | 강사→학부모 비공개 피드백 |
| announcement.py | Announcement, AnnouncementRead | 공지/읽음기록 |
| message.py | Message, MessageRecipient | SMS/LMS 발송 |
| teaching_material.py | TeachingMaterial, TeachingMaterialDownload, TeachingMaterialFile | 학습자료 |
| video.py | Video, VideoView | 교육 영상/시청기록 |
| makeup_request.py | MakeupClassRequest | 보강 신청 |
| parent_link_request.py | ParentLinkRequest | 학부모-자녀 연결 요청 |
| teacher_board.py | TeacherBoard, TeacherBoardAttachment | 강사 전용 게시판 |
| harkness_board.py | HarknessBoard, HarknessPost, HarknessComment, HarknessPostLike, HarknessQuestionLike | 하크니스 게시판(질문별 좋아요 포함) |
| library.py | HallOfFame, AdmissionInfo | 명예의 전당, 입시정보 |
| class_board.py | ClassBoardPost, ClassBoardAttachment, ClassBoardComment | 수업별 게시판 |
| reading_mbti.py | ReadingMBTITest 등 5종 | 독서MBTI |
| zoom_access.py | ZoomAccessLog | 줌 접속 로그 |
| ocr_history.py | OCRHistory | OCR/AI 분석 이력 |
| consultation.py | ConsultationRecord | 상담 기록 |
| student_profile.py | StudentProfile | 학생 기초조사 |
| login_log.py | LoginAttemptLog | 로그인 시도 기록 |
| inquiry.py | InquiryPost, InquiryReply | 문의/답변 |
| site_content.py | SiteContent | 정적 콘텐츠 key-value |
| ace_evaluation.py | WeeklyEvaluation, AceEvaluation | 주차/분기 역량 평가 |
| notification_reply.py | NotificationReply | 알림 답글 |
| api_usage_log.py | ApiUsageLog | AI API 사용량/비용 |
| reminder_log.py | ReminderLog | 리마인더 발송 이력 |
| push_subscription.py | PushSubscription | 웹푸시 구독 |
| teacher_hours.py | TeacherHoursCorrection | 강사 시수 보정 |
| teacher_prompt.py | TeacherPromptTemplate | 강사 프롬프트 템플릿 |
| conversation.py | Conversation, ConversationMessage | 강사↔관리자 대화 |
| student_caution.py | StudentCaution | 학생 주의사항 |
| payment_period.py | PaymentPeriod, HolidayWeek | 결제기간/휴무 |
| session_adjustment.py | SessionAdjustment | 출결 이월/보강 조정 |
| action_item.py | ActionItem | 처리대기 업무 |
| absence_notice.py | AbsenceNotice | 결석/지각 예고 |
| enrollment_schedule.py | EnrollmentSchedule | 입반/전반 예약 |
| curriculum.py | CurriculumWeek | 분기·주차 커리큘럼 |

`app/models/__init__.py`의 `__all__`에 **등록되지 않아 개별 import가 필요한** 모델 4개: `assignment.py`(Assignment, AssignmentSubmission), `material.py`(Material, MaterialDownload — 구버전 학습자료), `schema_quiz.py`(SchemaQuiz 등 3종), `vocabulary_quiz.py`(VocabularyQuiz 등 3종).

### 새 마이그레이션 관행
공식적으로는 `flask db upgrade`(Flask-Migrate)지만, 실제 CI(`deploy.yml`)는 루트의 애드혹 `migrate_*.py` 스크립트를 실행한다 — **두 관행이 혼재하며 어느 쪽이 "표준"인지 운영자 확인 필요**(C항목 참고).

### RLS(행 단위 접근 제어)
없음 — 애플리케이션 레벨에서 처리. `app/utils/decorators.py`(역할/권한/티어 데코레이터), `app/utils/content_access.py`(학년·수강 여부 기반 콘텐츠 접근 계산), 모델 인스턴스 메서드(`can_view()`, `can_edit()`, `has_tier_access()` 등)로 분산 구현. DB 레벨 정책(PostgreSQL `CREATE POLICY` 등)이나 SQLAlchemy 전역 쿼리 필터는 없음.

---

## 3. 사용자와 권한

### 회원 테이블
`User(UserMixin, db.Model)`, 테이블 `users` (`app/models/user.py:9`). 주요 컬럼: `user_id`(PK, UUID), `email`(unique), `password_hash`, `name`, `phone`, `role`(문자열, default `'teacher'`), `role_level`(Integer, default 4), `is_active`, `is_deleted`, `must_change_password`, `hall_of_fame_last_viewed_at`, 프로필 이미지, Zoom 연동 필드, 보안 필드(`failed_login_attempts`, `locked_until`, `email_verified`), `created_at`, `last_login`.

`get_id()`를 `user_id`로 override(`user.py:67-69`), `is_authenticated`를 항상 `True`로 override(`user.py:106-111`).

### 인증 방식
Flask-Login 세션 기반. `app/__init__.py`에서 `LoginManager` 초기화, `login_view='auth.login'`, `@login_manager.user_loader` 등록. 로그인/가입은 `app/auth/routes.py`+`forms.py`. 이메일 인증은 `itsdangerous.URLSafeTimedSerializer` 토큰 + Flask-Mail(`app/auth/email_utils.py:71-83`).

### 권한 구분
`role` 리터럴 값: `'admin'`, `'teacher'`, `'student'`, `'parent'`, `'master_admin'`(`app/utils/decorators.py:25`). `role_level`은 정수(낮을수록 고권한)이지만 **주석이 두 곳에서 다르다**:
- `app/models/user.py:19` 주석: `1=master, 2=manager, 3=teacher, 4=parent, 5=student`
- `app/utils/decorators.py:42` 주석: `1=master, 2=manager, 3=staff, 4=teacher, 5=parent, 6=student`

두 주석이 단계 수(5단계 vs 6단계)와 teacher 위치(3 vs 4)가 서로 다르다 — **실제 데이터/체크 로직이 어느 쪽을 따르는지 코드 전체 감사 없이는 확정 불가**(C항목 참고, 마일리지 권한 설계 시 영향 있음).

회원가입 폼에서는 `role_level=5 if role=='student' else 4`로 parent/student만 신규가입 가능(`app/auth/routes.py:152`, `app/auth/forms.py:53-56`) — teacher/admin 계정은 가입 폼 밖에서 생성되는 것으로 보이나 생성 지점은 확인 불가.

### 권한 검사 방식
`app/utils/decorators.py`에 데코레이터 5종: `requires_role(*roles)`, `requires_permission_level(level)`, `requires_tier(*tiers)`, `admin_or_owner_required(get_owner_id)`, `master_admin_only`. `master_admin`은 `requires_role` 검사를 항상 통과(`decorators.py:24-26`). 다만 라우트 다수는 데코레이터 대신 함수 내부 `if current_user.role == 'teacher':` 식 인라인 체크와 혼재(`app/admin/routes.py:74,320,342,503` 등).

### 학생-강사, 학생-반 연결
- 학생-강사: `Student.teacher_id`가 `users.user_id`를 직접 FK 참조(`app/models/student.py:12-13`, NOT NULL) — 학생 1명당 전담 강사 1명.
- 학생-반: `Student`에는 반 FK가 없고, `CourseEnrollment`(student_id+course_id 다대다, 수강신청/결제상태 포함)로 연결(`app/models/course.py:103-169`). `Course.teacher_id`로 강좌별 담당강사 별도 지정 가능.
- 입반/전반 예약: `EnrollmentSchedule`(강사 확인 플래그 포함).

### 학생-학부모 연결
`ParentStudent`(`parent_id`+`student_id`, `relation_type`, `permission_level`: full/view_only, `is_active`, unique 제약) — `app/models/parent_student.py:8-47`. 연결 신청 플로우는 `ParentLinkRequest`(내용 상세 미검토, 파일 존재만 확인).

---

## 4. 마일리지 대상 활동 데이터 (가장 중요)

| 활동 | 확인 결과 |
|---|---|
| 리라이팅 제출 | **있음** — `Essay`(제출 본체), `EssayVersion`(버전 이력), `EssayResult`(점수/등급) |
| 퀴즈 | **있음** — 어휘퀴즈/스키마퀴즈 2계열, 각각 문제/결과/세션 3테이블 구조 |
| 질문 등록 | **있음(단, 승인/반려 상태는 없음)** — `InquiryPost`(status: pending/answered만) |
| 댓글 | **있음(소프트 삭제 없음)** — `Comment`(대댓글 지원, `parent_comment_id`) |
| 좋아요 | **있음** — 게시글 좋아요 `PostLike`, 북마크 `Bookmark` 별도 존재. 도서는 좋아요 대신 별점(`BookRating`)만. 댓글엔 좋아요 없음 |
| 출결 | **있음** — `Attendance`(present/absent/late/excused, 수업회차 FK), 보강/이월은 별도 `SessionAdjustment` |
| 분기·주차 | **있음** — `CurriculumWeek`(year/quarter/grade/week_number), 평가 쪽엔 `WeeklyEvaluation`/`AceEvaluation`에도 분기·주차 필드 |
| 모의고사 | **없음** — "모의고사"는 `Course.course_type`의 선택지 값 하나일 뿐, 점수/순위 저장 테이블 없음. 마일리지 대상에 넣으려면 **신규 테이블 설계 필요** |
| 게시글 | **있음(리라이팅과 별개)** — `Post`(category: notice/question/free/resource). `app/news`는 학생 작성 게시판이 아니라 관리자 편집용 정적 콘텐츠 |

### 상세

**리라이팅(첨삭) 제출** (`app/models/essay.py`)
`Essay`: `essay_id`, `student_id`, `user_id`(실제 업로드자 = **강사 계정**, 학생 자기제출 아님 — `app/essays/routes.py:266`), `status`(draft/processing/reviewing/completed/failed), `is_finalized`, `finalized_at` → **교사 확인/승인 상태 명확히 존재**. finalize 액션: `app/essays/routes.py:974-977`에서 `status='completed'`, `is_finalized=True`, `finalized_at=datetime.utcnow()`.

**퀴즈** (`app/models/vocabulary_quiz.py`, `schema_quiz.py`)
`*QuizResult`: `student_id`, `quiz_id`, `is_correct`, `attempted_at`. `*QuizSession`: `total_questions`, `correct_count`, `score`(%), `started_at`/`completed_at` → **만점/정답률 판별 가능**. **회차 구분은 전용 컬럼이 아니라 `session_id`+타임스탬프 순서로 유추해야 함**.

**질문 등록** (`app/models/inquiry.py`)
`InquiryPost.status`는 `'pending'`/`'answered'` 2가지뿐 — **승인/반려 개념 없음**.

**댓글** (`app/models/community.py`)
`Comment`: `post_id` FK(CASCADE), `parent_comment_id`(대댓글). **소프트 삭제 컬럼 없음** — 실삭제 구조.

**좋아요** (`app/models/community.py`, `tag.py`, `book.py`)
`PostLike`(user_id+post_id 복합PK), `Bookmark`(user_id+post_id 복합PK, 좋아요와 별개), `BookRating`(fun_score/usefulness_score, 좋아요 아닌 별점).

**출결** (`app/models/attendance.py`, `course.py`, `session_adjustment.py`)
`Attendance`: `session_id`(수업회차 FK), `status`(present/absent/late/excused), `checked_at`, `participation_score`/`comprehension_score`(1-5). 수업회차는 `CourseSession.session_number`+`session_date`. 보강/이월은 `SessionAdjustment`(adjustment_type: rollover/free_session, status: pending_review/pending/applied/cancelled)로 별도 관리.

**분기·주차** (`app/models/curriculum.py`)
`CurriculumWeek`: (year, quarter, grade, week_number) unique. 학생 평가 쪽 `WeeklyEvaluation.week_number`, `AceEvaluation.year/quarter`.

**모의고사** — 없음
"모의고사" 문자열은 (1) `Course.course_type` 선택지, (2) 강사 시급계산 로직의 수업유형 분류, (3) `HallOfFame.category`의 `'mock_exam_award'`(수상작 게시)로만 등장. 순위/백분위 계산 가능한 전용 성적 테이블 없음 — grep 결과 `rank`/`순위`/`백분위` 매치 없음(무관한 도서랭킹 API 제외).

**게시글** (`app/models/community.py`, `app/news/routes.py`)
`Post`: `category`(notice/question/free/resource), 로그인 사용자면 role 제한 없이 작성 가능해 보임(글쓰기 자체엔 역할 제한 코드 없음, 특정 액션만 admin 제한). `app/news`는 `SiteContent`(정적 소개 페이지) 편집 라우트일 뿐 학생 게시판 아님.

### 설계 시 주의점
- 모의고사만 실데이터 없음 → 신규 테이블 필요
- 질문 등록에 승인/반려가 없어 "질문 승인 시 지급" 조건은 현재 데이터로 구현 불가
- 댓글 소프트 삭제가 없어, 삭제된 댓글에 지급한 마일리지 회수 로직을 두려면 소프트 삭제부터 도입해야 함
- 퀴즈 "회차"는 컬럼이 아니라 타임스탬프 순서로 유추

---

## 5. 기존 유사 기능 (포인트/뱃지/랭킹)

**마일리지/뱃지(게이미피케이션) 전용 기능: 없음** — `mileage`/`badge`/`뱃지`/`마일리지` 키워드 전체 검색 결과 없음.

- `templates/macros/badges.html`의 `tier_badge()` 매크로는 **UI 표시용 등급 배지**(부트스트랩 스타일)일 뿐 적립/획득 로직 없음. `Student.tier`/`Course.tier`(A/B/C/VIP)를 시각화하는 용도.
- **명예의 전당**(`HallOfFame`, `app/models/library.py:8-61`)은 "우수 답안/수상작 게시판"이며, `category`(excellent_answer/mock_exam_award/essay_award/other), `student_id`, `award_name`, `award_date`, `week_number`, `view_count` 등을 가진 **정적 게시글 모델**. 적립/차감 로직 없음, 강사/관리자가 수동 등록. `User.hall_of_fame_last_viewed_at`은 "NEW" 안읽음 표시용일 뿐 포인트와 무관.
- 점수화된 기존 지표: `WeeklyEvaluation`(주간 점수+등급), `AceEvaluation`(분기별 5축×3항목 역량 평가) — 강사가 학생 역량을 평가하는 성적 시스템이며 "포인트 적립" 구조 아님. **마일리지 산정 근거로 재사용할 여지는 있으나(예: ACE 점수 연동) 그대로 가져다 쓸 순 없음.**
- `Post.likes_count`/`views`는 단순 카운터일 뿐 사용자 귀속 누적 포인트 아님.
- 랭킹(순위): grep 결과 없음.

**결론**: 마일리지/뱃지는 전면 신규 구현 필요. `HallOfFame`은 이름만 유사할 뿐 로직 무관 — 굳이 연계한다면 "명예의 전당 등재 시 마일리지 지급" 정도가 통합 후보.

---

## 6. 서버 로직 구조

### 라우트 작성 방식
Flask Blueprint 기반. `app/<도메인>/routes.py`에 `@<bp>.route(...)` 데코레이터로 뷰 함수 정의, `app/__init__.py`에서 `url_prefix`와 함께 일괄 등록. 인증은 `@login_required`(Flask-Login) 표준 적용(23개 파일에서 사용).

### 서비스 계층
`app/services/`에는 파일이 2개뿐(`__init__.py`, `payment_calculator.py`) — 서비스 계층 분리는 **결제 계산 로직 한 곳에만** 명시적으로 적용됨(`PaymentCalculator.calculate()`, 순수 계산 후 DTO 반환, DB 쓰기는 호출부 라우트가 수행). 그 외 대부분 도메인은 라우트 함수 안에 쿼리·비즈니스 로직·트랜잭션이 그대로 섞여 있음. `app/utils/`의 `course_utils.py`, `enrollment_utils.py` 등은 헬퍼 함수 모듈에 가까움.

### 에러 처리/유효성 검증
전역 `@app.errorhandler`는 `app/__init__.py:53-56`의 429(rate limit) 하나뿐, 404/500 전역 핸들러 없음. try/except는 라우트별 개별 판단(위험한 다중삭제는 rollback 포함 방어적으로, 단순 생성/수정은 try/except 없이 commit만 — 일관된 전역 규칙 없음). 유효성 검증은 Flask-WTF 폼(`app/*/forms.py`, 9개 도메인에 존재)을 쓰는 곳과, forms.py 없이 `request.form.get()`을 직접 수동 검증하는 곳이 혼재.

### 트랜잭션 처리
`app/admin/routes.py:1538-1619`의 청구서 일괄 생성이 대표 사례: `Payment` 생성 후 `flush()`로 PK 확보 → 관련 `SessionAdjustment` 상태 변경 → 루프 종료 후 **한 번만** `commit()`(try/except 없어 예외 시 전체가 그대로 예외 전파, 전역 핸들러도 없어 500으로 이어짐). 반면 `app/students/routes.py:446-469`의 삭제 로직은 여러 테이블을 raw SQL로 순차 삭제 후 try/except+rollback으로 방어적으로 처리 — **두 스타일이 혼재하며 통일된 규칙 없음**.

---

## 7. 배치 작업

### 현재 존재하는 배치
`app/utils/scheduler.py`에 `BackgroundScheduler(timezone='Asia/Seoul')`로 초기화(`app/__init__.py:510-515`에서 `create_app()` 마지막에 호출), 등록된 job 3개:
1. `class_reminder` — 30분 간격, 1시간 후 시작 수업 리마인더 발송
2. `enrollment_schedule` — 매일 00:05, 예약된 입반/전반/보강 적용
3. `weekly_session_gen` — 매주 일요일 00:01, 다음 7일치 수업 세션 생성

멀티워커(gunicorn) 환경에서 중복 실행 방지를 위해 `fcntl.flock`으로 `/tmp/momoai_scheduler.lock` 파일 락 사용(`scheduler.py:222-230`) — **POSIX 전용이라 Linux 운영서버에서만 정상 동작**, Windows 로컬 개발환경에선 락 동작이 다를 수 있음.

각 job은 `with app.app_context(): try/except`로 예외를 로깅만 하고 삼키며, 마지막에 `commit()` 한 번.

### 다른 정기 실행 수단
`.github/workflows/deploy.yml`은 스케줄이 아니라 push 트리거 CI/CD. systemd timer 유닛 없음(`momoai.service`만 존재). `GCP_DEPLOYMENT_GUIDE.md:400-407`에 crontab 기반 DB 백업 예시가 있으나 **문서상 안내일 뿐 코드로 구현된 배치는 아님**.

**월간/분기 자동 집계 배치는 현재 코드에 없음** — 결제 청구서 생성도 스케줄러가 아니라 관리자가 화면에서 수동 트리거.

### 신규 배치 추가 방법 (판단)
기존 인프라(멀티워커 gunicorn + fcntl 락 걸린 APScheduler)를 그대로 재사용해 `app/utils/scheduler.py`에 job을 추가하는 것이 배포 파이프라인·systemd 유닛을 새로 건드리지 않아 가장 현실적. 대안(별도 systemd timer)은 웹 프로세스와 완전히 분리되는 장점이 있으나 이 프로젝트에 선례가 없고 배포 자동화(`deploy.yml`)가 지원하지 않아 수동 설치가 필요함. 무거운 전체 스캔(월간 집계 등)은 스케줄러 스레드를 오래 점유할 수 있어 배치 크기 제한 등 신규 설계가 필요함(선례 없음).

---

## 8. 알림

`app/notifications/`(블루프린트+라우트), 모델은 `app/models/notification.py`의 `Notification`(테이블 `notifications`): `user_id`, `notification_type`(자유 문자열), `title`, `message`, `link_url`, `is_read`/`read_at`, `attachment_url`, `related_user_id`/`related_entity_type`/`related_entity_id`, `created_at`. 답글은 `NotificationReply`.

**발송 방식**: 인앱(DB 저장+목록/폴링 API) + Web Push(`pywebpush`, `PushSubscription`에 구독정보 저장, VAPID 키는 config에서 이름만 확인). 이메일(Flask-Mail)은 **회원가입 이메일 인증 전용**이며 일반 알림에는 연동되어 있지 않음.

**트리거 연결**: `Notification.create_notification()`(정적 메서드)이 (1) DB row insert, (2) try/except로 `send_push_to_user()` 자동 호출(실패해도 무시) — **인앱 알림 생성 시 웹푸시가 자동 동반**됨. 실제 호출 지점: 첨삭 완료 시 학생 본인+`ParentStudent`로 연결된 학부모 전원(`app/essays/routes.py:822-845`), 커뮤니티 댓글/멘션(`app/community/routes.py`), 관리자 액션 다수, 수강/입반 자동 알림(`app/utils/course_utils.py`), 스케줄러 리마인더(`app/utils/scheduler.py:196`) 등.

→ **뱃지 획득/등급 승급/우수답안 선정 알림은 `Notification.create_notification()`을 그대로 호출하면 인앱+웹푸시가 동시에 나가는 기존 패턴을 재사용할 수 있음.**

---

## 9. 화면 구조

### 학생 화면 (`app/student_portal/`, url_prefix `/student`)
`before_request` 훅으로 퇴원 7일 경과 학생은 `static` 외 접근 차단(`app/student_portal/__init__.py:9-35`). 60개 라우트(3227줄) 중 마일리지 연관 후보: `/essays`(첨삭), `/attendance`(출결), `/assignments`(과제), `/class-board`(게시판), `/vocabulary-quiz`·`/schema-quiz`(퀴즈), `/progress`(진도). 전 라우트에 `@login_required`+`@requires_role('student','admin')` 조합.

### 관리자 화면 (`app/admin/`, url_prefix `/admin`)
190개 라우트(8181줄). `requires_permission_level(level)` 위주 권한 검사(예: 대시보드는 레벨 2 이상). 데코레이터 주석상 레벨 체계가 3절에서 언급한 것과 또 다르게 적혀 있음(`1=master,2=manager,3=staff,4=teacher,5=parent,6=student`) — 3절의 불일치 참고.

### 강사 화면 (`app/teacher/`, url_prefix `/teacher`)
110개 라우트(5226줄). `@requires_role('teacher','admin')` 기본, 일부는 `'master_admin'`까지 포함. 담당 수업 여부(`course.teacher_id != current_user.user_id`) 추가 검증이 흔함.

### 마이페이지 (`app/profile/`, url_prefix `/profile`)
라우트 4개뿐: `/`(개인 통계·최근활동), `/edit`, `/change-password`, `/image/<user_id>`. **역할 제한 없이 `@login_required`만** — 마일리지/뱃지 표시를 추가하기 가장 자연스러운 위치.

### UI 컴포넌트/스타일
Tailwind(`tailwind.config.js`, `content`가 `templates/**/*.html`+`app/**/*.py` 스캔). 재사용 Jinja2 매크로는 `templates/macros/`에 3개뿐: `badges.html`(`tier_badge` 매크로 — 뱃지 UI 설계 시 이 패턴 참고 권장), `rich_editor.html`, `image_upload.html`.

### 정적 파일/업로드
`config.py:9`에서 `BASE_DIR/uploads` 기준으로 `POST_FILES_FOLDER` 등 하위 폴더 파생, 앱 시작 시 자동 생성. 업로드 파일명은 `uuid4().hex+확장자`로 저장, 원본명은 별도 보존. Nginx가 `/uploads/`를 직접 서빙(30일 캐시).

---

## 10. 개발 환경 관행

### 시간대
모델 계층은 거의 전부 `datetime.utcnow()` default(12개 이상 모델 파일, 19건 확인) — **DB 저장은 UTC로 일관**. 화면 표시는 Jinja 커스텀 필터 `kst`(`app/__init__.py:92-102`, UTC+9 변환)로 처리. 단, 라우트 레벨에서 `datetime.now()`(서버 로컬시간)도 12개 파일·34건 섞여 쓰임 — **"저장=UTC, 표시=KST" 원칙은 있으나 완전히 통일되어 있지 않음.** 신규 기능은 모델은 `utcnow()`, 화면은 `kst` 필터를 따르는 게 안전. 배치 스케줄러는 `timezone='Asia/Seoul'`을 명시적으로 사용.

### 코드 컨벤션
린트 설정 파일(`.flake8`, `pyproject.toml` 등) 없음. snake_case(함수/변수), PascalCase(모델), `xxx_bp`(블루프린트 변수명) 일관. 라우트 함수에 한글 docstring 관행적으로 부착.

### 테스트 코드
루트의 `test_*.py`(17개)는 **pytest 기반이 아님** — `import pytest` 0건, `create_app()`으로 앱 컨텍스트를 만들어 쿼리 후 `print()`로 확인하는 수동 점검 스크립트. `python test_xxx.py` 직접 실행. CI(`deploy.yml`)는 문법 검사(`py_compile`)만 하고 이 테스트들을 호출하지 않음.

### 배포 방식과 브랜치 전략
`master` 단일 브랜치 운영. CI(`deploy.yml`): push 트리거 → 문법 검사 → SSH로 `git reset --hard origin/master` → **애드혹 `migrate_*.py` 스크립트 실행(실패해도 계속 진행)** → `systemctl restart momoai`. 유닛테스트 없음.

### 문서상 주의사항
**루트의 `README.md`/`DEPLOYMENT.md`/`PRODUCTION_DEPLOYMENT_GUIDE.md`는 현재 아키텍처를 반영하지 않는 구버전 문서다** — 이전 단계였던 "AI 논술 배치 첨삭 도구"(SQLite `tasks.db`, `/api/review` 등) 기준으로 작성되어 있고, 현재의 학생/수업/출결/결제 중심 학원 운영 플랫폼과 다르다. 실제 배포 절차는 `GCP_DEPLOYMENT_GUIDE.md`+`momoai.service`+`nginx_momoai.conf`+`deploy.yml`을 기준으로 봐야 한다. `SECURITY_CHECKLIST.md`에 `.env`/`*.bak` 업로드 금지 경고 명시.

---

## 종합 요약

### A. 그대로 재사용할 수 있는 것
- 권한 데코레이터 체계 — `app/utils/decorators.py`(`requires_role`, `requires_permission_level`)
- 알림 발송 인프라 — `Notification.create_notification()`이 인앱+웹푸시를 자동으로 함께 처리(`app/models/notification.py:53-83`), 뱃지 획득/등급 승급 알림에 그대로 재사용 가능
- 배치 실행 인프라 — `app/utils/scheduler.py`의 APScheduler(fcntl 락 포함), 신규 job만 추가하면 됨
- 마일리지 대상 활동의 원천 데이터 테이블 — `Essay`, `Comment`, `PostLike`/`Bookmark`, `Attendance`, `CurriculumWeek`, `VocabularyQuiz*`/`SchemaQuiz*`, `InquiryPost`, `Post` (4절 참고, 모의고사만 예외)
- 뱃지 UI 매크로 패턴 — `templates/macros/badges.html`의 `tier_badge()`(색상맵+size 매개변수 구조)
- 학생-학부모 알림 전파 패턴 — `ParentStudent` 연결을 이용해 자녀 마일리지 변동을 학부모에게도 알리는 기존 관행(`app/essays/routes.py:822-845`) 재사용 가능
- 마이페이지(`app/profile/`) — 역할 제한 없는 개인 화면이라 마일리지/뱃지 표시 추가에 적합

### B. 새로 만들어야 하는 것
- 마일리지/뱃지 테이블 자체(적립 로그, 뱃지 정의, 사용자별 획득 이력) — 전무
- 모의고사 성적 테이블 — 전용 테이블 없음, 점수/레벨/순위 산출 구조부터 설계 필요
- 랭킹/순위 계산 로직 — 전무
- 마일리지 지급 트리거 — 각 활동 이벤트 지점(첨삭 finalize, 퀴즈 세션 완료, 출석 체크, 댓글/좋아요 생성 등)에 훅 삽입
- 신규 배치 함수 3종(월간 명예의 전당 집계, 주간 출석 정산, 분기 완주 판정) — `app/utils/scheduler.py`에 추가
- 질문 등록 승인/반려 상태(현재 pending/answered뿐이라 "승인 시 지급" 조건은 컬럼 확장 필요 시에만)
- 댓글 소프트 삭제(마일리지 회수 로직을 두려면)

### C. 판단이 필요한 사항

1. **운영 DB 종류**: `deploy.sh`는 SQLite를 명시하는데 `GCP_DEPLOYMENT_GUIDE.md`와 `config.py`의 Cloud SQL 대응 설정은 PostgreSQL/MySQL을 전제로 함. 실제 운영 DB가 무엇인지에 따라 마일리지 적립의 동시성 제어(중복 지급 방지 락 전략)가 달라진다. → 운영자 확인 필요.
2. **마이그레이션 방식**: 공식 문서는 `flask db upgrade`(alembic)를 말하지만 실제 CI가 실행하는 건 루트의 애드혹 `migrate_*.py` 스크립트다. 마일리지 테이블을 추가할 때
   - (a) alembic 정식 마이그레이션 파일을 새로 작성 — 표준적이지만 현재 CI가 이걸 실행하지 않아 별도로 서버에서 수동 실행해야 할 수 있음
   - (b) 기존 관행대로 `migrate_mileage.py` 애드혹 스크립트를 작성해 `deploy.yml`에 추가 — 현재 파이프라인과 일치하지만 alembic 이력과 어긋나 스키마 추적이 더 어려워짐
   중 어느 쪽을 따를지 결정 필요.
3. **role_level 체계 불일치**: `app/models/user.py:19` 주석(5단계, teacher=3)과 `app/utils/decorators.py:42` 주석(6단계, teacher=4)이 서로 다르다. 마일리지 권한(예: "매니저 이상만 뱃지 수동 지급 가능")을 설계하기 전에 실제 운영 데이터의 `role_level` 값이 어느 체계를 따르는지 확인이 필요하다(기존 버그일 가능성도 있어 별도 보고 가치 있음).
4. **모의고사 마일리지 반영 여부**: 데이터가 아예 없다. 마일리지 대상에 포함할지, 포함한다면 점수를 강사가 수동 입력하게 할지 외부 시스템과 연동할지 결정 필요.
5. **질문 등록 지급 기준**: "등록"만으로 지급할지, "답변 완료(answered)"를 기준으로 지급할지 — 현재 승인/반려 개념이 없어 전자·후자 중 선택.
6. **댓글 마일리지 회수 여부**: 댓글에 소프트 삭제가 없어, 삭제된 댓글에 지급했던 마일리지를 회수할지, 회수한다면 소프트 삭제부터 새로 도입할지.
7. **퀴즈 회차별 지급 규칙**: "회차" 컬럼이 없어 세션 타임스탬프로 유추해야 한다. 같은 날 여러 번 응시 시 매번 지급할지, 하루 1회로 제한할지 등 정책 결정 필요.
8. **배치 실행 위치**: 기존 인프로세스 APScheduler(gunicorn 멀티워커+fcntl 락)에 신규 job을 추가할지, 아니면 웹 프로세스와 분리된 별도 systemd timer로 새로 만들지.
   - 기존 방식: 배포 파이프라인 변경 불필요, 다만 무거운 월간 집계 시 스레드 점유 이슈 가능
   - 신규 timer: 웹 요청 처리와 완전 분리되지만 서버에 수동 설치 필요, 이 프로젝트에 선례 없음
9. **학부모 노출 범위**: 자녀의 마일리지/뱃지를 학부모 화면에도 노출할지(`ParentStudent.permission_level`의 full/view_only 구분을 재사용할 수 있음) 여부.
10. **명예의 전당과의 통합 여부**: 기존 `HallOfFame`(수동 등록 우수작 게시판)과 신규 마일리지/뱃지를 완전히 별개로 둘지, "명예의 전당 등재 시 마일리지 자동 지급" 같은 연동 지점을 만들지.
