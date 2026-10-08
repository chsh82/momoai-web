# CLAUDE.md — 모모아이 프로젝트 작업 규칙

이 파일은 Claude Code가 `C:\Users\aproa\momoai_web` 프로젝트에서 작업할 때 반드시 따라야 할 프로젝트 규칙이다.

## 프로젝트 개요

- 프로젝트명: 모모아이 프로젝트 / momoai_web
- 성격: Flask 기반 MOMOAI 웹 애플리케이션
- 주요 사용자 역할: admin, teacher, parent, student
- 현재 인수 목표: 앱 내 고객 응대 기능 자동화와 에이전트 활동 설계/개발
- 대표 관심 예시: 보강 안내, 상담/보강/환불/문의 응대 자동화, 관리자 업무 보조

## 절대 안전 규칙

대표님 명시 금지사항:

- 학생들의 학습 자료 데이터를 손대거나 삭제하지 않는다.

다음 항목은 명시 승인 없이는 읽기/수정/삭제/실행을 하지 않는다.

- `.env`, API 키, 토큰, 쿠키, 비밀번호 등 secret 파일/값
- 운영 DB 및 로컬 데이터 파일: `momoai.db`, `tasks.db`, `instance/**`
- 사용자 업로드/산출물: `uploads/**`, `outputs/**`
- 학생 학습 콘텐츠/자료 데이터: `app/sources/**`, `app/tutorial/content/**`
- 개인정보성 원자료: 학생/학부모 연락처, 결제 정보, 첨삭 원문, 학습 결과 원자료
- 대량 수정/삭제 스크립트 실행
- `git push`, 배포, production 서비스 재시작, 운영 DB migration/수정

데이터가 필요한 작업은 먼저 구조/스키마/코드만 읽고, 실제 데이터 접근이 필요한 경우 Davinci/대표님에게 승인 요청한다.

## 작업 방식

1. 작업 전 확인
   - `git status --short`
   - 관련 README/문서
   - 관련 route/model/template/service 파일
   - 테스트 또는 최소 검증 명령

2. 변경 원칙
   - 작은 단위로 변경한다.
   - 기존 업무 흐름을 깨지 않는다.
   - 고객 응대 자동화는 “초안/분류/요약/업무 생성 보조”를 우선한다.
   - 일정 확정, 환불, DB 변경, 발송 같은 실제 상태 변경은 관리자/사용자 확인 후 수행되게 한다.
   - LLM이 보강 일정, 환불 금액, 학생 성과, 학습 데이터 값을 임의 생성하거나 확정하지 않게 한다.

3. 검증 원칙
   - 최소한 Python 문법 검사 또는 대상 테스트를 실행한다.
   - 가능하면 특정 기능의 Flask route 단위 테스트 또는 브라우저 수동 QA 경로를 제시한다.
   - 테스트 도구가 없는 경우 그 사실을 보고하고 대체 검증을 수행한다.

## 고객 응대/챗봇 관련 주요 파일

- `app/chat_widget/routes.py`
  - 학부모 대화 위젯 JSON API
  - 상담/보강/환불/문의 라우팅
  - 보강 옵션 조회 및 신청
  - 학부모 일정 동의 처리
  - 자유 텍스트 의도 분류

- `templates/partials/chat_widget.html`
  - 우측 하단 학부모 대화 위젯 UI
  - 상담/보강/환불/문의 진입
  - 대화 스레드 표시 및 답장

- `app/utils/llm_assist.py`
  - 관리자/응대용 소규모 LLM 보조 헬퍼
  - 클라이언트가 임의 프롬프트를 보내지 않도록 서버에서 프롬프트 조립

- `app/models/conversation.py`
  - 대화 스레드 및 메시지 모델

- `app/models/action_item.py`
  - 처리 대기 업무 모델
  - 고객 응대 자동화에서 “관리자 확인 필요”, “강사 확인 필요” 등 업무 생성 후보

- `app/models/consultation_request.py`
  - 상담/개별 보강 신청 흐름

- `app/models/makeup_request.py`
  - 그룹 보강 신청 흐름

- `app/models/notification.py`
  - 관리자/강사/학부모 알림

## 현재 chat_widget 설계상 중요한 안전 원칙

- LLM은 위젯 입구에서 의도 분류에만 사용된다.
- 분류 대상은 `consult`, `makeup`, `refund`, `inquiry`이다.
- 보강 일정, 환불 금액, 확정 처리처럼 틀리면 안 되는 값은 LLM이 자동으로 채우지 않는다.
- 실제 신청은 기존 구조화 폼을 통해 받는다.
- 자유 텍스트는 관리자 확인이 가능하도록 ConsultationRequest에 기록된다.

이 원칙을 깨지 말고 확장한다.

## 권장 확장 방향

우선순위 높은 안전한 확장:

1. 관리자용 응대 초안 생성
   - 학부모 메시지와 현재 신청 상태를 기반으로 답장 초안을 생성
   - 실제 전송은 관리자가 확인 후 클릭

2. 보강 안내 에이전트
   - 가능한 그룹 보강 시간 안내
   - 시간이 맞지 않으면 개별 보강 신청으로 안내
   - 강사/관리자 확인이 필요한 경우 ActionItem 생성 초안 또는 확인 요청

3. 대화 요약/상태 태그
   - 최근 대화 요약
   - “응답 필요”, “강사 확인 필요”, “관리자 승인 필요” 같은 상태 표시

4. ActionItem 자동 생성 보조
   - 고객 응대에서 후속 조치가 필요한 경우 업무 항목 생성
   - 단, 자동 완료/자동 확정은 금지

## Claude Code 실행 원칙

- 읽기 전용 분석은 `Read`, `Bash(git *)` 중심으로 제한한다.
- 코드 변경 작업은 필요한 파일 범위가 명확할 때만 수행한다.
- 위험한 Bash 명령, 삭제 명령, DB 수정 명령, 배포 명령은 실행하지 않는다.
- `.claude/settings.local.json`에 허용된 Python 명령이 있더라도 DB/학생자료에 영향이 있을 수 있는 스크립트는 승인 없이 실행하지 않는다.

권장 읽기 전용 분석 예시:

```bash
claude -p "고객 응대/보강 안내 자동화 관점에서 현재 chat_widget 구현을 분석하고, 수정 없이 개선 계획만 보고해줘. 학생 학습자료, DB, uploads, outputs, .env는 읽지 마." --allowedTools "Read,Bash(git *)" --max-turns 8
```

## 검증 명령 후보

현재 환경에서 확인된 최소 검증:

```bash
python - <<'PY'
from pathlib import Path
import ast, sys
paths=[p for p in Path('app').rglob('*.py')]
errs=[]
for p in paths:
    try:
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    except Exception as e:
        errs.append((str(p), type(e).__name__, str(e)))
print(f'parsed_py_files={len(paths)} errors={len(errs)}')
for e in errs[:20]: print(e)
sys.exit(1 if errs else 0)
PY
```

추가 테스트 도구가 준비되면 `pytest` 또는 기능별 route 테스트를 우선한다.

## 보고 형식

작업 완료 시 다음을 보고한다.

- 변경 파일
- 실행 명령
- 검증 결과
- 남은 리스크
- 대표님 승인 필요한 다음 작업
