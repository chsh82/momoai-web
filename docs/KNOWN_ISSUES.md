# 알려진 문제

## OCR 첨삭 결과 저장 실패 - summary 컬럼에 dict 바인딩 오류 (2026-08-30 발견)

- **위치**: `app/essays/routes.py:1644` `_run_ocr_background`
- **증상**: `OCRHistory.summary` 컬럼에 dict 객체를 그대로 바인딩해
  `sqlite3.ProgrammingError: Error binding parameter 2: type 'dict' is not supported` 발생.
- **2차 문제**: 위 예외 발생 시 세션을 rollback하지 않고 그대로 재사용해
  `sqlalchemy.exc.PendingRollbackError`가 이어서 발생 - 세션이 오염된 채로
  다음 쿼리(`OCRHistory.query.get(ocr_id)`)까지 실패.
- **영향**: `ocr_id=1258` 학생의 첨삭 결과가 저장되지 않음(프로덕션 실사례,
  운영 로그에서 확인).
- **상태**: 이번 작업(FLASK_ENV 프로덕션 설정 수정) 범위 밖이라 미수정.
  별도로 (1) summary를 JSON 문자열로 직렬화하거나 컬럼 타입을 JSON으로
  바꾸고, (2) 예외 발생 시 `db.session.rollback()` 후 재조회하도록 고쳐야 함.

## manager/staff 계정이 "관리자" 섹션 외 사이드바 메뉴를 거의 못 볼 가능성 (2026-10-13 발견)

- **위치**: `templates/base.html` 사이드바 블록 조건문 전체.
- **증상**: "관리자" 섹션은 `current_user.has_permission_level(2)`(role_level
  기준)로 열리지만, 강사/학부모/학생 섹션은 전부 `current_user.role in
  [...]` **문자열** 기준으로 분기한다. manager/staff 계정의 `role` 값은
  `'manager'`/`'staff'`이지 `'admin'`이 아니므로, role_level상으로는
  "관리자" 섹션에 들어가도 그 외 섹션(강사/학부모/학생 전용 메뉴)에는
  전부 role 문자열 불일치로 걸러져 안 보일 가능성이 높다.
- **영향 범위**: 모모 에이전트 권한 확장 작업(2026-10-13, manager/staff를
  master_admin과 동일한 전체 범위로 설계) 과정에서 발견 - 같은 패턴이
  사이트 전체 사이드바에 더 있을 수 있다.
- **상태**: 실제 manager/staff 계정으로 로그인해 확인하는 과정이 아직
  없었음(코드 리딩만으로 발견) - 재현 확인 및 수정 범위 결정 필요.
  `docs/MOMOAI_site_manual_2026-10.md` 참고.

## 🤖모모 에이전트 사이드바 진입 링크가 백엔드 권한 확장을 못 따라감 (2026-10-13)

- **위치**: `templates/base.html`의 "관리자" 섹션 내 모모 에이전트 링크(`is_master_admin`
  조건)와 "강사" 섹션 내 링크(`is_teacher` 조건) - 두 블록만 있고 staff는
  둘 중 어디에도 안 걸려 진입 경로 자체가 없음.
- **상태**: `app/admin/hermes_routes.py` 백엔드는 이미 role_level 4(teacher)까지
  열려 있음(2026-10-13 권한 범위 확장 작업). 사이드바 링크만 못 따라간
  상태 - 미반영.

## `app/models/user.py`의 role_level 설명 주석이 실제 코드와 다름 (2026-10-13 발견)

- **위치**: `app/models/user.py`의 role_level 인라인 주석.
- **증상**: 주석은 `1=master, 2=manager, 3=teacher, 4=parent, 5=student`로
  적혀 있으나, 실제 동작 기준(`app/utils/decorators.py`)은
  `1=master, 2=manager, 3=staff, 4=teacher, 5=parent, 6=student`다 -
  staff가 빠지고 번호가 밀려 있는 오래된 틀린 주석.
- **상태**: 동작에는 영향 없음(주석만 틀림), 다음에 역할 관련 코드를 만질
  때 혼동하지 않도록 정정만 하면 됨 - 미반영.
