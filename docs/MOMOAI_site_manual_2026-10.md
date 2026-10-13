# 모모아이(MOMOAI) 사이트 메뉴·기능 안내 매뉴얼 (2026-10-13 기준)

개발자와 함께 개발 범위를 검토하기 위한 체크리스트 용도의 문서다.
`templates/base.html` 사이드바 구조와 `app/__init__.py`에 등록된 블루프린트
28개를 기준으로 정리했다. 각 항목 체크박스는 검토하면서 체크해 쓰면 된다.

## 0. 역할 체계

momoai_web은 **역할을 나타내는 필드가 두 개**이고, 서로 독립적으로 쓰인다 — 이 점이
사이드바 메뉴 노출에 직접 영향을 준다(1-6절 참고).

- `role`(문자열, 자유값): `master_admin` / `admin` / `manager` / `staff` /
  `teacher` / `parent` / `student`
- `role_level`(숫자, 낮을수록 높은 권한): **1=master, 2=manager, 3=staff,
  4=teacher, 5=parent, 6=student** (`app/utils/decorators.py` 기준. `app/models/user.py`
  코드 주석은 이와 다르게 `1=master,2=manager,3=teacher,4=parent,5=student`로
  적혀 있어 staff가 빠진 **오래된 틀린 주석**이니 참고하지 말 것)
- 주요 프로퍼티: `is_master_admin`(role_level==1) · `is_manager`(role_level==2) ·
  `is_staff`(role_level==3) · `is_teacher`(role=='teacher') · `is_admin`(role=='admin') ·
  `is_parent` · `is_student`

## 1. 공통 메뉴 (로그인한 모든 역할)

- [ ] 알림 (`notifications.index`) — 알림 센터
- [ ] 명예의 전당 (`library.hall_of_fame`)
- [ ] 학습 자료실 (`library.index`) — 수업 도서 등 학습 자료(2026-10-12~13 표지 복구 작업 진행한 영역)
- [ ] 모모 소식 (`news.hub`) — 공지성 뉴스 허브
- [ ] 커뮤니티 (`community.index`)

## 2. "관리자" 섹션 — `role_level ≤ 2` (master_admin, manager)

- [ ] 대시보드 (`admin.index`)

**학사 관리**
- [ ] 수업 관리 (`admin.courses`)
- [ ] 수업 현황 (`admin.all_schedule`)
- [ ] 출석 체크 (`teacher.attendance_list`)
- [ ] 전체 출석현황 (`admin.attendance_status`)
- [ ] 학생별 출결 현황 (`admin.student_attendance_report`)
- [ ] 보강수업 관리 (`admin.makeup_requests`)
- [ ] 결석 예고 관리 (`admin.absence_notices`)
- [ ] 입반·전반·보강 (`admin.enrollment_schedules`)
- [ ] 강사 시수 현황 (`admin.teacher_hours`)
- [ ] 🤖 모모 에이전트 (`admin.hermes`) — ⚠️ **`is_master_admin`으로 한 번 더 좁혀져 있어
      manager는 role_level상 이 섹션에 들어와도 이 링크는 못 봄** (백엔드는 teacher까지
      열려 있는데 사이드바 진입점은 master_admin 전용으로 남아있는 불일치, 1-6절 참고)

**회원 관리**
- [ ] 승인 대기 (`admin.pending_users`)
- [ ] 학생 관리 (`students.index`)
- [ ] 강사 관리 (`admin.staff_list`)
- [ ] 학부모 관리 (`admin.parent_list`)
- [ ] 아이디 관리 (`admin.account_management`)
- [ ] 학부모 연결 관리 (`admin.parent_link_requests`)
- [ ] 학생 프로필 (`admin.student_profiles`)
- [ ] 마일리지 관리 (`admin.mileage_dashboard`)
- [ ] 학생 위험도 분석 (`admin.student_risk_analysis`)
- [ ] 푸시 알림 관리 (`admin.push_notification_dashboard`)

**상담 관리**
- [ ] 전체 대화 기록 (`admin.conversation_history`)
- [ ] 피드백 관리 (`admin.feedbacks`)
- [ ] 수업 문자 자동 생성 (`feedback.feedback_index`) — Anthropic API 서버 프록시(클라이언트에 키 노출 방지)
- [ ] 상담 관리 (`admin.consultations`)
- [ ] 상담 신청 접수함 (`consultation_request.admin_list`) — 학부모 접수 → 관리자 처리 → 강사 상담기록 연결
- [ ] 문의 관리 (`inquiry.index`)
- [ ] 처리 대기 업무 (`admin.action_items`)

**학습 관리**
- [ ] 첨삭 관리 (`essays.index`) — 논술 자동 채점/피드백
- [ ] 학습 교재 (`admin.teaching_materials`)
- [ ] 학습 동영상 (`admin.videos`)
- [ ] 모모아이 MBTI (`teacher.reading_mbti`)
- [ ] 필사 노트 (`teacher.pilsa_note`)
- [ ] 글쓰기 튜토리얼 (`tutorial.track_select`) — 레슨 열람은 비로그인도 허용

**온라인 강의실**
- [ ] 줌 링크 관리 (`admin.zoom_links`)
- [ ] 접속 로그 (`admin.zoom_access_logs`)

**커뮤니케이션**
- [ ] 공지사항 관리 (`admin.announcements`)
- [ ] SMS 발송 (`admin.messages`)
- [ ] SMS 발송 이력 (`teacher.sms_history`)
- [ ] 알림 현황 (`notifications.index`)
- [ ] 업무 메신저 (`messages.inbox`) — 강사↔관리자 1:1

**게시판 관리**
- [ ] 공지사항 / 클래스 게시판(`admin.board_class_manage`) / 강사 게시판(`admin.board_teacher_manage`) /
      하크니스 게시판(`admin.board_harkness_manage`) / 수업 공지(`admin.messages_manage`) / 문의 관리

**재무 관리**
- [ ] 청구서 생성 (`admin.billing`)
- [ ] 결제 관리 (`admin.payments`)
- [ ] 환불 요청 접수함 (`refund_request.admin_list`) — 2026-10-13 view_only 권한 체크 보완한 영역
- [ ] 이월 및 차감 (`admin.session_adjustments`)
- [ ] 결제 기간 관리 (`admin.payment_periods`)

**콘텐츠 관리**
- [ ] 도서 관리 (`books.index`)
- [ ] 커리큘럼 관리 (`curriculum.index`)
- [ ] 학습 자료실 / 명예의 전당 / 입시정보(`library.admission_info`)

**사이트 관리**
- [ ] API 사용량 (`admin.api_usage_dashboard`)

## 3. "강사" 섹션 — `role in ['teacher','admin']` (문자열 기준!)

> ⚠️ manager/staff는 `role` 문자열이 `'manager'`/`'staff'`라서 이 섹션이 아예 안 보인다(1-6절 참고).

- [ ] 마이 페이지 (`teacher.index`)

**내 수업**: 수업 목록 / 주간 시간표 / 예정 변동 현황 / 출석 체크 /
🤖 모모 에이전트(`is_teacher`일 때만 노출) / 보강 신청 확인 / 상담·개별보강 협의 확인 /
수업 공지 / SMS 발송 / SMS 이력 / 학습 교재 / 교사용 교재 게시판

**학생 관리**: 내 학생 목록 / 피드백 작성 / 피드백 목록 / 수업 문자 자동생성 /
상담 작성 / 문의 관리 / 처리 대기 업무

**과제 관리**: 과제 출제 / 첨삭 관리 / OCR 인식

**평가 관리**: MBTI / 주간 평가 / ACE 평가

**기타**: 학습 자료 / 필사 노트 / 내 시수 확인 / 업무 메신저

**게시판**: 공지사항 / 클래스 게시판 / 강사 게시판 / 하크니스 게시판

## 4. "학부모" 섹션 — `role in ['parent','admin']`

- [ ] 마이 페이지
- [ ] 신규 등록 설문 (`parent.registration_survey`, 미완료 시 강조 표시)

**자녀 관리**: 내 자녀 / 자녀 연결

**학습 현황**: 수업 목록 / 출결 현황 / 과제 및 첨삭 / 글 제출하기 / 학습 교재 /
도서 추천 / 학습 동영상 / 필사 노트 / 상담 기록 / 상담 신청

**평가 정보**: MBTI / 주간 평가 / ACE 분기 평가

**결제/보강**
- [ ] 보강수업 (`parent.makeup_classes_index`)
- [ ] 결제 관리 (`parent.all_payments`) → 환불 요청 내역(`refund_request.index`) —
      2026-10 세션에서 "모모봇이 결제/보강 조회에 답할 수 있는가" 조사 시 다룬 영역

**게시판**: 공지사항 / 선생님 피드백 / 문의 게시판

## 5. "학생" 섹션 — `role in ['student','admin']`

- [ ] 마이 페이지
- [ ] 월간 랭킹 (`student.mileage_ranking`)
- [ ] 강의실 바로가기

**내 수업**: 수업 목록 / 출결 현황 / 과제 보기 / 클래스 게시판 / 하크니스 게시판

**학습 활동**: 글쓰기 제출 / 내 첨삭 / 내가 만든 질문 / 학습 교재 / 도서 추천 /
학습 동영상 / 필사 노트 / 학습 진도

**테스트**: MBTI / 글쓰기 튜토리얼
+ (`is_admin`만 노출, "관리자 검토용" 라벨) 이야기 탐험단 · 중등 공부력 테스트 ·
초등 공부력 테스트(구버전) · 중등 전공 나침반
+ ⚠️ 어휘퀴즈/스키마퀴즈는 라우트는 있지만 **메뉴에서 주석 처리되어 비활성화 상태**
  (아프로랩스 쪽 어휘 퀴즈 모듈과는 별개 — 이식 여부는 미결정)

**평가 정보**: MBTI / 주간 평가

**보강수업**: 신청하기 / 신청 내역

**게시판**: 공지사항 / 하크니스

## 6. "빠른 작업" — `role in ['admin','teacher']`

- [ ] 새 첨삭 시작
- [ ] (`is_admin`만) 학생 추가

## 7. 사이드바에 메뉴가 없는 기능 (블루프린트는 등록돼 있음)

- [ ] `chat_widget` — 학부모 대화 위젯(모모봇). 사이드바 메뉴 없음, 플로팅 버튼 전용
- [ ] `payment` (`/payment`) — 토스페이먼츠 결제 콜백 API로 추정, 사이드바 메뉴 없음
- [ ] `auth` — 로그인/로그아웃만
- [ ] `search` — 헤더 검색창에서 호출(사이드바 아님)

## 8. 역할별 진단 테스트 계열 (admin 전용 노출)

`interest_quest`, `study_mid`, `study_elem`(구버전 표시), `interest_mid` —
학년대상 진단/적성 테스트. **admin 메뉴에서만 "관리자 검토용"으로 노출**되고
학생들에게는 아직 정식 공개 안 된 상태로 보인다. `interest_mid`는 결과를
세션에도 DB에도 저장하지 않는 것으로 확인됨 — 정식 공개 전 데이터 저장 여부
결정 필요.

---

## 발견된 구조적 이슈 (개발 범위 논의 시 참고)

1. **role 문자열 vs role_level 숫자 불일치로 manager/staff 메뉴 공백 가능성**
   사이드바의 강사/학부모/학생 섹션은 전부 `role` **문자열**로 분기하는데,
   manager/staff 계정의 `role` 값은 `'manager'`/`'staff'`이지 `'admin'`이
   아니다. 즉 manager/staff는 "관리자" 섹션(role_level 기준)엔 들어가지만,
   그 외 섹션은 전부 role 문자열 불일치로 제외되어 **"관리자" 섹션 외에는
   거의 아무 메뉴도 안 보일 가능성이 높다.** 실제로 그런지 manager/staff
   계정으로 직접 로그인해 확인이 필요하다 — 모모 에이전트 권한 확장(2026-10-13)
   때 manager/staff를 "master_admin과 동일한 전체 범위"로 설계했던 것과
   같은 맥락의 문제라, 사이트 전체에 이 패턴이 더 있을 수 있다.

2. **🤖모모 에이전트 사이드바 링크가 백엔드 권한 확장을 못 따라감**
   백엔드는 teacher(role_level 4)까지 열려 있는데, "관리자" 섹션의 진입
   링크는 여전히 `is_master_admin` 조건이라 manager는 거길 통해 못 들어간다
   (강사 섹션엔 `is_teacher` 조건으로 별도 링크가 있어 teacher는 진입 가능).
   staff는 두 섹션 어디에도 안 걸려 진입 경로 자체가 없다(2026-10-13 세션에서
   이미 한 번 언급됨, 미반영).

3. **사용자 역할 주석 오류** — `app/models/user.py`의 role_level 설명 주석이
   실제 코드(`app/utils/decorators.py`)와 다르게 staff를 빼먹고 번호가
   밀려 있다. 사소하지만 다음에 역할 관련 작업할 때 혼동 소지가 있어 정정
   필요.

4. **"사이트 사용 설명서"(관리자용)가 최근 기능을 못 따라감** — 모모
   에이전트, 마일리지 관리, 학생 위험도 분석, 푸시 알림 관리 등 비교적
   최근 추가된 기능이 admin 설명서 목차에 전혀 없다. 신규 관리자 온보딩에
   영향 줄 수 있음.

5. **비활성 상태인 기능들** — 어휘퀴즈/스키마퀴즈(학생 메뉴에서 주석 처리),
   진단 테스트 계열(`interest_quest` 등, admin 검토용으로만 노출) — 정식
   오픈 여부와 일정을 개발 범위 논의에서 결정 필요.

---

*이 문서는 2026-10-13 기준 코드(`templates/base.html`, `app/__init__.py`,
`app/models/user.py`, `app/utils/decorators.py`)를 읽어 작성했다. 실제
화면에서 역할별로 직접 로그인해 확인하는 과정이 아직 빠져 있으니, 특히
위 "발견된 구조적 이슈" 1·2번은 실사용 확인을 권장한다.*
