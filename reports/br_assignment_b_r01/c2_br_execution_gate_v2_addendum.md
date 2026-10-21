# C2B-R 실행 승인안 보완 v2 — 독립 리뷰 차단7건 대응

상태: PROPOSED / RE_REVIEW_REQUIRED / EXECUTION_NOT_APPROVED. 원본 승인안은 이력으로 보존한다. 충돌 시 이 보완이 우선하며 파일 범위(repo 신규3/수정2, 외부실행5)와 실제19+신규4=23테이블은 확대하지 않는다. 검토 deleg_75c9cc3d는 passed=false였다. 아래는 그 지적에 대한 설계 수정이며 실행 결과가 아니다.

## F1. flag 분기 진리표
- 설정 키 부재 또는 정확 bool False, store 부재: OFF, 기존 본문 실행.
- 정확 bool False 또는 키 부재, store 존재: 구성 충돌503, GET/POST legacy 실행0.
- 정확 bool True, 현재 factory 소유의 유효 bound store: ON.
- 정확 bool True, store 없음/타 owner/폐쇄/유효성 실패:503, legacy 실행0.
- bool이 아닌 모든 값(NULL/0/1/문자열 포함):503, legacy 실행0.
- ON 업무·CSRF·권한 검사 실패 후 OFF로 fallback 금지.
- legacy before_request가 먼저 redirect할 수 있다. 이 경우 handler 진입 전 종료로 기록하되 legacy 업무 DML0을 확인한다. 구성 오류503 시험은 hook 통과 fixture에서 실시한다.

## F2. exact source 및 import 경계
`c2_br_executable_source_slices.json`에 원문 경로/hash/심볼/decorator 포함 slice를 고정했다. 신규 create3와 수정 route/detail은 승인 구현 이후 source manifest에 별도 final hash를 동결하며 baseline을 덮어쓰지 않는다. 모델10 원문 hash는 c2_br_exact_gate_manifest.json이 기준이다.

### 실행 slice와 주입 globals
모든 slice는 AST 원문에서 함수 전체+원래 decorator만 compile한다. 함수 본문/정의/decorator를 다시 쓰거나 제거하지 않는다. nested 함수의 app 참조는 정상 create_app closure를 실행해 얻지 않고 아래 명시 globals로 해석한다. 이 환경 치환은 보고한다.
- requires_role: functools.wraps, Flask flash/redirect/url_for/abort, Flask-Login current_user.
- check_student_status: fresh student_bp, Flask request/flash/redirect/url_for, current_user. 내부 `from app.models import Student`는 실제 로드된 Student로만 해석한다.
- assignment_detail/submit_assignment: fresh student_bp, 실제 login_required/requires_role/current_user, 실제 db/Student/CourseEnrollment/Assignment/AssignmentSubmission/Notification, Flask request/flash/redirect/url_for/render_template, 실제 safe_original_filename. 이외 사용하지 않는 원본 route import 영역 실행 금지. ON 신규3 import는 각 exact source로 로드한 실제 module symbol만 resolver가 제공한다.
- safe_original_filename: app/utils/file_utils.py:5–22 원문, globals os/re. 해당 파일의 나머지 top-level 실행 없음. OFF 파일 양성 시험에 이 실제 helper를 사용한다.
- to_kst_filter: app/__init__.py:140–151 원문, fresh app. 내부 stdlib datetime/timedelta만 허용.
- static_versioned: app/__init__.py:161–169 원문, globals fresh app/실제 Flask url_for. 내부 os만 허용. fresh app.static_folder는 실제 repo/static, CSS2 stat만 허용. create_app나 config import 없음.
- now는 datetime.now 직접 binding. generate_csrf/validate_csrf는 실제 Flask-WTF. template은 원문 base/detail만 허용, 미등록 include는 fail-closed.

### 제한 resolver
- 모델10의 `from app.models import db` → fresh 실제 Flask-SQLAlchemy db만.
- hook의 `from app.models import Student` → 같은 registry 실제 Student만. db resolver와 별도 fromlist exact match.
- ON route lazy import → app.student_portal.assignment_p3_adapter의 승인된 entry symbol만. adapter/store/schema 사이 import도 승인 신규3만, normal package initializer fallback 없음.
- OFF route 내부: flask.current_app, werkzeug.utils.secure_filename, stdlib os/uuid만. file helper는 주입된 원문 slice다.
- 모델 전체의 최상위는 docstring/import/class 및 essay.py 상수2만 허용. top-level global call/event 등록/추가 assignment/클래스 발견 시 fail-closed.
- 허용 앱 심볼·globals·fromlist 밖이면 ImportError 및 audit 실패로 종료. 정상 app/config/models/student_portal initializer를 sys.modules 우회로 호출하지 않는다.

### 설치 라이브러리 경계
c2_br_library_read_manifest.json은 현재 설치 distribution20의 코드/metadata 정확982파일 hash 목록이다. importlib.metadata/packaging으로 설치 정보만 수집했고 Flask/ORM target package는 import하지 않았다. missing=[]는 설치 항목 존재일 뿐 runtime 검증이 아니다.
- site-packages 루트 전체·패키지 디렉터리 전체 read allowlist 금지. 목록 파일만 read 허용, pycache 금지. exact-source loader로 compile하는 code와 native dependency 파일을 구분한다.
- native Windows DLL/stdlib/인코딩 로딩은 별도 interpreter manifest가 필요하다. **첫 source compile 전 preflight에서 sys.executable/sys.base_prefix의 CPython runtime·stdlib 코드/필수 native 파일을 경로+hash로 새 evidence manifest에 열거하고 freeze**한다. site-packages나 user 경로는 이 절차로 추가할 수 없다. OS 시스템 DLL은 로더 의존성으로 기록하며 exhaustive OS sandbox 주장은 하지 않는다.
- preflight는 명시 목록 열거/해시/설치 metadata 읽기만, 앱/모델 compile/import/mapper/DB/WSGI/외부 실행 없음. manifest 밖 파일이 필요하면 중단하고 추가 exact 승인, 자동 범위 확장 금지.
- speculative pycache/metadata 접근을 라이브러리가 삼켜도 unexpected audit denial로 실패 처리. 실제 dependency 부족을 설치/네트워크로 자동 보완하지 않는다.

## F3. 분리 metadata의 FK 해석
실제19는 fresh db.metadata 하나에 원문대로 등록하고, sidecar4는 별도 MetaData에만 등록한다. sidecar→실제 FK는 **실제 Table.c의 Column 객체를 ForeignKey에 직접 전달**한다. 문자열로 다른 metadata table을 찾도록 맡기지 않는다. sidecar 내부 FK만 동일 sidecar metadata의 exact Column 객체를 사용한다.
- 실제19 metadata create 순서 후 sidecar 순서는 revisions→heads→receipts→outbox. revisions의 parent self-reference는 같은 Table의 Column 객체로 해석한다.
- actual metadata.tables key/각 Table columns/constraints/index/관계 signature를 sidecar 등록 전후 비교해 불변 확인. 실제 metadata에 sidecar/대체 참조 테이블 등록 금지.
- 실제 전체 fresh metadata에 DDL을 실행할 수 있는 것은 exact19의 setup뿐. DB 최종 table set23을 독립 SQLite sqlite_schema로 확인한다.
- cross-metadata FK DDL이나 sorter가 실제 환경에서 실패하면 BLOCKED. table 복제/metadata 합침/관계 삭제로 조용히 우회하지 않는다.

## F4. 물리 전이 제약과 command 검사의 구분
공통 DB 강제: PK/unique/FK, integer typeof·범위, digest hex64, nullable/CHECK, 아래 trigger. command 강제: 현재 권한/audience/명시 course-session 관계, 요청 CAS 기대값, payload canonicalization, legacy digest/업무 정책. command 검사를 DB물리 보장이라고 보고하지 않는다.

### revision INSERT
- revision_no=1이면 parent=NULL이며 해당 submission의 head가 없어야 한다.
- revision_no>1이면 parent non-NULL, 같은 submission의 현재 head가 존재하고 generation=revision_no-1, head.revision_id=parent, parent.revision_no=revision_no-1이어야 한다.
- self-parent, 미래 parent, 건너뛰기, 타submission parent, parent=NULL의 후속 revision, parent 있는 초기 revision은 BEFORE INSERT trigger로 거부한다.
- BEFORE INSERT conflict guard는 PK 및 uq_br_revision_no/uq_br_revision_target 충돌 모두 거부. BEFORE UPDATE/DELETE는 전부 거부.

### head INSERT/UPDATE
- 초기 INSERT는 generation=1, 대상 revision_no=1/parent=NULL/동일 submission일 때만.
- UPDATE에서 submission_id 불변, generation=OLD.generation+1, NEW revision의 revision_no=NEW.generation, parent=OLD.revision_id, 동일 submission이어야 한다. legacy_digest는 새 revision.legacy_digest와 같아야 한다. 다른 컬럼/값 변경 금지.
- 기대 generation/revision의 WHERE와 rowcount=1은 고정 command가 강제한다. trigger만으로 호출자의 기대값을 증명하지 않는다.
- DELETE 전부 거부. BEFORE INSERT에서 기존 PK 충돌은 전부 거부하므로 INSERT OR REPLACE/REPLACE 및 INSERT...ON CONFLICT DO UPDATE도 우회할 수 없다. 일반 UPDATE는 위 합법 전이만 허용.

### receipt/outbox
모든 UPDATE/DELETE 거부, BEFORE INSERT에서 PK/각 unique 충돌 거부(두 REPLACE와 UPSERT 포함). assignment/submission 일치, receipt.actor 및 revision.actor 일치, outbox recipient가 현재 assignment.teacher_id와 일치하는 검사는 command transaction 내부에서 한다. outbox pending/attempt0만 허용.

### 독립 음성 acceptance
구현이 생성한 metadata/schema manifest끼리 비교하는 것만으로 통과시키지 않는다. fixed raw-DML test profile로 아래 위반을 별도 NEW owner에서 하나씩 실행하고 거부 예외+전체23 rows/schema 불변을 확인한다.
- 각 immutable table UPDATE/DELETE/PK와 alternate unique 각각의 두 REPLACE/UPSERT.
- revision 초기/후속/null/self/미래/외부parent/번호건너뛰기, head 초기번호/대상불일치/submission변경/generation유지·감소·+2/잘못parent·digest/DELETE/PK REPLACE/UPSERT.
- 독립 FK 위반 및 참조 삭제 RESTRICT(다른 constraint로 먼저 실패해 가린 결과 금지).
- 합법 초기/후속 revision→head 전이 양성, 직접 UPDATE가 command authorization 증거는 아님을 명시.
- FKcheck=[], integrity=ok, recursive_triggers=ON 및 runtime OFF 거부. 모든 trigger exact name/SQL을 신규 schema 파일과 독립 기대사양 두 곳에서 대조한다.
원안 trigger 이름은 table-short 조합 대신 `br_<table suffix>_<rule>_guard` 고정 규칙이며 rule은 immutable: insert_conflict/update/delete, revisions 추가: lineage_insert, heads: transition_insert/transition_update/insert_conflict/delete다. 허용 객체 목록은 이 닫힌 조합에서 코드로 산출한다.

## F5. HTTP/CAS/replay 계약
### multipart/form-data POST의 exact 필드
모든 scalar는 form에서만 채택, 각 key 정확1회, 미등록 form/query actor·role·target·token/header override는 거부. query는 비어 있어야 한다. Content-Type 불일치415, schema 오류400/422. route assignment_id는 URL에서만, body assignment_id/student_id/actor_id/role 금지.
- csrf_token: 실제 session token, nonempty 문자열 최대512 bytes.
- content: nonblank UTF8, 최대262144 bytes, 저장 원문 bytes 그대로 digest(검증용 strip 여부로 원문을 조용히 바꾸지 않음).
- enrollment_id/course_id: canonical UUID 문자열36. session_id: UUID36 또는 정확 빈 문자열(unknown).
- idempotency_key: server 발급 UUID36, 임의 client actor 인코딩 금지.
- expected_submission_id: UUID36 또는 정확 `absent`.
- expected_generation: canonical ASCII 정수문자열0~2147483647 (sign/공백/선행0/bool 문자열 불허).
- expected_revision_id: UUID36 또는 정확 `absent`.
- expected_legacy_digest: 소문자hex64.
- file: 최대1 part, 없거나 filename 빈값이면 첨부없음. 기존 첨부의 유지·삭제 선택은 이 B-R에 없으며 재제출은 새 file 또는 첨부없음으로 새 capture를 만든다. 기존 파일은 삭제하지 않는다.

전체 multipart body 최대18MiB, form parts 최대16, scalar 최대10개(위 정확10), file part최대1, 파일16MiB, filename UTF8최대255bytes. Werkzeug parser 메모리/스풀 정책은 owner 전용 stream_factory로 묶고 first write 전에 guard 검사한다. csrf token·파일 content 포함 전체를 로그에 남기지 않는다. canonical digest envelope 최대1MiB를 직렬화 전 누적예산 검사한다.

### 초기/기존/GET 상태
ON GET은 업무write0. submission 없음: expected_submission_id=absent, expected_generation=0, expected_revision_id=absent. 기존 submission이나 head 없으면 generation0/revision absent이되 submission_id는 실제UUID. head 있으면 실제generation/revision.
legacy_snapshot은 **assignment와 해당 본인 submission의 전체 DB컬럼을 이름순서로** 저장, submission 없으면 NULL. 날짜는 UTC-naive ISO8601 microseconds, bool은0/1, 정수는JSON정수, NULL명시, string 원문, 부동소수 컬럼은 해당2모델에 없음을 원문 signature로 검사한다. content/file_path/file_name/score/feedback/graded_by/모든시간/통계 포함. request pre-state와 commit 후 post-state를 분리한다.
- expected_legacy_digest는 GET 읽기 snapshot의 digest다. command는 첫 BEGIN IMMEDIATE 뒤 fresh 조회한 pre-state와 비교한다.
- revision.legacy_snapshot/legacy_digest와 head.legacy_digest는 실제 submit()+flush/통계 반영 **후 post-state**다.
- request_digest는 operation='assignment_submit', actorID, URL assignmentID, binding3, expected_submission_id/generation/revision/legacy_digest, 원문 content, file의 논리 manifest(filename/size/sha256; owner 실제경로 제외)을 canonical JSON으로 묶은 sha256. csrf/session/random storage path/응답시간은 제외. idempotency key는 receipt lookup key이며 digest envelope에는 별도로 포함하지 않는다.

### 판정 순서(POST)
1. flag 분기, 로그인/decorator/hook → strict body/CSRF 검증. malformed/auth/CSRF 실패는 업무 DML/파일0.
2. BEGIN IMMEDIATE → actor/본인유일성/audience/active scope 재검사 → graded 또는 채점필드 잔존 거부409.
3. 기존 receipt lookup: 다른 request_digest409, 같은 digest는 현재 권한·graded 검사를 통과했을 때 저장응답 재전송. 이 replay는 현재 head가 전진했더라도 허용하고 mutation/알림/새파일0. 채점 이후 replay는409, 권한회수 replay403.
4. receipt 없으면 expected submission/head/pre-state digest를 fresh 상태와 비교, 다르면409. 두 최초제출은 한 성공, 다른 key stale absent은409; 동일key/동일envelope는 기존 receipt replay.
5. 입력 file 검증/staging, 실제 submission/통계+revision/head/receipt/Notification/outbox 저장·flush·commit. commit 후 응답 실패의 재요청은3의 replay다.

응답 business `authorized=false, eligible=false, verified=false, official=false, adopted=false` 고정. `access_checked=true`를 따로 쓰더라도 업무권한/채택 DTO를 발급하지 않는다. late/권한/CSRF/unsupported/graded/conflict 오류에 성공receipt를 남기지 않는다.

## F6. 상충 role과 legacy hook
ON 제안 권한 pair는 (role='student', role_level의 DB typeof=integer이고 값5또는6)만이다. 5는 현재 가입 소스,6은 명시 legacy 호환이다. student+level1~4/NULL/float/string/bool 취급 모호값은 거부, 다른 role은 level5/6이어도 거부. 이 제한은 이번 실행 승인안에서 요청하는 충돌 방지 정책으로 **아직 대표가 실제 운영 채택한 규칙은 아니다.** SQLite에서 bool이1로 저장되면 integer1 거부로 처리한다. 고정 user fixture는 소스 근거가 있는5/6만 양성이다.
- raw is_active는0/1정수 중1, is_deleted는0만 허용. ORM 변환으로 비정상 저장값을 양성으로 바꾸지 않는다.
- 실제 before_request email hook은 원문 보존한 선행 **legacy 제한**일 뿐 신규 ON authority가 아니다.
- email-only(user_id 연결0): hook 통과해도 ON403.
- user_id 연결2개: ON403.
- user_id 정확1개지만 그 학생.email≠principal.email, 또는 principal.email의 학생 행2개 이상, 또는 email이 다른 학생에 연결: ON403. hook이 먼저 withdrawn redirect하면 그 선행 결과로 종료하고 ON허용으로 합산하지 않는다.
- 정상 user_id/email 일치1개: hook의 퇴원제한을 포함해 통과해야 ON양성. withdrawn 학생은 ON scope에서 status active가 아니면403; hook이 먼저 redirect하면 별도 기록.
- role master_admin의 legacy decorator 통과를 ON adapter 허가로 취급하지 않는다. anonymous는 실제 Flask-Login의 redirect/401를 기록, 업무mutation0.

## F7. child capability와 고정 race profile
### readback
부모 runner만 정확 sys.executable로 E/br_assignment/readback.py를 `--capability-stdin` 인수 하나로 새 자식 실행할 수 있다. cwd repo root, 환경은 네개의 테스트변수+Windows 최소runtime PATH/SystemRoot 및 패키지 탐색에 필요한 명시환경만, 사용자secret 환경전달 금지. PYTHONPATH는 승인namespace만. shell=False, interpreter/entrypoint hash 고정, 다른 subprocess/명령/임의 args 금지.
- 모든 writer connection 닫힘/flush완료/동결 source hash/schema hash/owner·sentinel·DB file identity 확정 후, parent가 현재 run에 발급한 1회 capability를 inherited stdin pipe로만 전달한다. command line/로그/외부요청은 경로·capability 입력 통로가 아니다.
- capability는 run ID/nonce, parent PID, owner canonical path, sentinel/file identity, DB SHA256, source/schema digest, 허용 readback purpose만 결합. parent memory의 발급/소비 registry와 직접 만든 child/pipe의 소유관계가 trust root다. JSON 안의 자기주장 signature만 검증하는 방식은 금지한다.
- child는 inherited pipe에서만 수신, 새 경로 생성/다른 DB fallback 없음. ancestor/sentinel/identity/hash/source/schema 일치 후 parent가 발급한 owner 고정경로에 대해 내부 생성 read-only sqlite URI(mode=ro)를 연다. 이는 readback profile만의 URI 예외이며 caller URI 허용이 아니다. query_only=ON+authorizer SELECT/PRAGMA 조회만, DML/DDL/write filesystem 거부.
- parent가 child생성 전capability 발급, pipe전달 후single consumption, child종료 뒤폐기. 재시도는 동일capability 재사용하지 않고 새로검증/발급. 종료후 임의 retainedDB reopen 금지. 읽기결과는 child stdout→parent가 evidence에 기록(원문/개인정보는 synthetic여도 내용출력 최소화).
- source/schema/identity mismatch, reused cap, arbitrary CLI path, child write·DDL·다른프로세스 시도는 부정 대조로 거부한다. OS상 악성동일사용자 전체 격리를 보장하지는 않는다.

### 고정 profile(별도 issued helper, 일반 command owner와 분리)
- B-R07 revoke_actor: users의 고정 STUDENT_A is_active=0만, distinct connection1, reset불가. 본인연결 등 임의필드 금지.
- B-R07 revoke_enrollment: ENROLLMENT_A status='cancelled', completed_at=고정 timestamp만, distinct connection1.
- B-R07 grade_target: TARGET_SUBMISSION_A score=80/feedback='synthetic-grade'/graded_by=TEACHER_A/graded_at=고정timestamp/status='graded', TARGET_ASSIGNMENT_A graded_submissions만 실제 grade() 의미로갱신. 생성·다른학생·다른table 쓰기금지.
- 동시 writer는 학생 command connection1+고정 helper connection1, barrier schedule과합법직렬결과를 기록. 실제 teacher route 검증으로 부르지 않는다.
- B-R01/F4 negative-DML profile은 신규희생owner의sidecar4 및 명시 FK target삭제검사만 허용, test별transaction rollback/전체snapshot확인. 일반런타임권한확장 금지.
- profile 이름/발급capability는 caller가임의선택할수없고 runner의고정slice dispatch만 발급. 모든helper도commit boundary검사한다.

## 제출 전 검증
v2는 원문 보존 및 추가manifest3으로 source/hash closure를 구체화했다. 아직 runtime interpreter manifest/실제 mapper/DDL/렌더는 실행되지 않았다. preflight에서 허용된 CPython runtime 파일 열거로 닫히지 않으면 실행을 중단하며 site-packages/user경로확대는 추가승인이다. 독립 재검토에서 차단 지적이 해소됐는지 확인 후에만 대표님께 승인문안을 제출한다. 기존 승인된 정책 외 충돌 role/제약은 명시 신규제안으로 남긴다. 전체 closeout은 없다.
