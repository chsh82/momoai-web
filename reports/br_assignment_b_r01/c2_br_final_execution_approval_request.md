# C2B-R 최종 실행 승인 요청

상태: REVIEW_PASSED_FOR_APPROVAL_REQUEST / USER_EXECUTION_APPROVAL_PENDING / NO_CLOSEOUT.

## 판정과 문서 우선순위
- 최초 독립 검토 deleg_75c9cc3d: 차단7건, passed=false. 실패 이력을 유지한다.
- v2 독립 재검토 deleg_61ce2928: passed=true, blocking_findings=[], 비차단 권고4건. 이는 승인 요청을 제출할 수 있다는 판정이지 실제 실행/구현 PASS가 아니다.
- 적용 순서: 이 문서의 아래 보충 → c2_br_execution_gate_v2_addendum.md → P3-02C2B-R_학생과제_격리실행_승인안.md. exact source/gate/library manifest3을 함께 적용한다. 기존 원문을 덮어쓰지 않는다.
- 리뷰어는 문서·필요 소스만 읽었으며 실행/SQL/앱 import/DB/Git/네트워크/파일 쓰기/독립 해시 재계산을 하지 않았다. 아래 보충은 부모의 권고 반영이며 추가 독립 리뷰 결과로 집계하지 않는다.

## 마지막 권고4 반영
1. head의 초기 INSERT와 후속 UPDATE 모두 legacy_digest=대상 revision.legacy_digest를 물리 trigger로 강제한다. 초기 잘못된 digest와 후속 잘못된 digest의 독립 raw-DML 음성시험을 각각 기록한다.
2. multipart의 파일 파싱/해싱은 제한된 메모리 스트림으로만 처리한다. body18MiB/file16MiB/field·part수/동시요청 제한을 적용하고 디스크 spool fallback은 금지한다. 초과는 거부하며 owner 임시 스풀을 자동 생성하지 않는다. 따라서 replay·권한/CSRF 거부의 파일0은 staging/final뿐 아니라 parser 디스크 쓰기0도 포함한다. 메모리 자원 한계로 이 계약을 지키지 못하면 BLOCKED로 보고하고 스풀 정책 변경은 추가 승인한다.
3. B-R07 고정 enrollment 회수 helper는 실제 모델 소스 상태값 dropped와 고정 completed_at을 사용한다. 앞선 cancelled 제안은 대체한다. 실제 운영 철회 workflow/교사 route를 실행하는 시험이라고 부르지 않고, 고정 실제2connection 비활성 상태 전이 시험으로 보고한다.
4. student+정수 level5/6, course-less/임시학생/첨부-only 미지원, 현재 수강·수업 기간 제한은 이번 합성 격리시험에 한정한 신규 제안이다. 운영 정책 채택/권한 변경은 승인 대상이 아니다.

## 이번에 승인받을 정확 범위
- repo 신규3: app/student_portal/assignment_p3_adapter.py, app/services/p3_assignment_store.py, app/services/p3_assignment_schema.py.
- repo 기존2 최소구간: app/student_portal/routes.py의 assignment_detail/submit_assignment ON 분기, templates/student/assignment_detail.html의 ON 폼/None 가드. OFF 기존 업무 본문 보존.
- 외부 실행5: br_assignment/run_br_assignment.py, isolation_kernel.py, source_loader.py, test_assignment_real_route.py, readback.py (같은 phase02b2 외부 증거 루트 아래).
- 실제 소스 모델19테이블+신규4, 총23의 NEW sentinel-owned scratch SQLite에서 실제 함수 slice/Flask-Login/Flask-WTF/ORM/Jinja WSGI 시험. 정상 앱 bootstrap과 운영 실행이 아니다.
- strict vertical TDD: 행동 하나씩 실제 RED→최소 구현→동일 assertion GREEN→회귀. 동결 순서3종/독립 새 프로세스 readback/독립 리뷰 및 보존 검증까지. 미달/SKIP는 그대로 보고한다.
- loader/mapper/DDL/격리 경계가 실패하면 승인 밖 우회 없이 BLOCKED. runtime manifest에 사용자·site-packages 경로를 자동 확장하지 않는다.

## 승인 제외
정상 앱·운영 DB·실자료·provider/Push·외부 전송·브라우저/서버·P2/base·기존 C2A·전역 metadata/model/migration·기존 Essay reset/delete 수정·commit/push/배포·전체 closeout.

reset/delete409는 이미 정책 승인됐지만 이번 실행의 구현 범위 밖이다. 전체 원본 보호 완료를 주장하지 않는다. 과거 C2A strict TDD PARTIAL 및 symlink SKIP는 유지한다.

## 대표 승인 문안
> 원안과 v2 보완 및 최종 보충을 적용해 repo 신규3·기존2 최소구간·외부실행5만 구현하고, 실제19+신규4 총23의 NEW scratch SQLite에서 strict vertical TDD와 실제 source-slice WSGI/Jinja로 검증한다. role pair·미지원 대상·기간 제한은 합성 격리시험용 신규 제안으로만 승인하며 운영 정책 채택은 아니다. 정상 앱/운영/실자료/외부 전송/기존 C2A/P2/metadata/migration/reset-delete/배포는 제외하고, 미달은 표시하며 전체 작업을 종결하지 않는다.

이 문안에 대한 대표님의 명시 실행 승인 전까지 코드 수정/모델 import/SQL/WSGI 시험은 하지 않는다.
