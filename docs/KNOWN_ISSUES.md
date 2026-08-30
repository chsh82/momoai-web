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
