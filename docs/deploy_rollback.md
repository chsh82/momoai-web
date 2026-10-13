# 배포 실패 시 복구 절차 (2026-10-13)

`.github/workflows/deploy.yml`은 2026-10-13부터 배포 대상 커밋을 별도 git
worktree에서 먼저 검증(의존성 설치 + CSS 빌드)한 뒤에만 운영 코드/CSS를
함께 반영한다. **이 단계(코드/CSS 반영 전)에서 실패하면 운영 HEAD·템플릿·
CSS는 전혀 바뀌지 않고 배포가 그냥 멈춘다**(실제 서버에서 성공/실패 양쪽
케이스 모두 git 해시 비교로 검증 완료) — 이 경우 복구 작업이 필요 없다,
그냥 원인을 고치고 다시 push하면 된다.

아래는 **코드/CSS 반영 이후**(= `git reset --hard`가 이미 실행된 이후) 단계
에서 문제가 생겼을 때의 복구 절차다.

## A. Alembic 마이그레이션(`flask db upgrade`) 실패

기존 스크립트가 마이그레이션 직전 DB를 자동 백업한다
(`~/momoai_web/backups/momoai_<YYYYMMDD_HHMMSS>_pre_alembic.db`). 마이그레이션이
실패해도 스크립트는 계속 진행해 서비스를 재시작한다(기존 동작, 이번 변경과
무관) — 즉 **코드는 새 버전인데 DB 스키마는 구버전**인 상태로 서비스가 뜰
수 있다.

1. `ssh chsh82@momoai.kr`
2. `journalctl -u momoai -n 100`로 실제 에러 확인(스키마 불일치로 인한
   쿼리 실패인지 확인)
3. 스키마 문제가 확인되면: 가장 최근 `*_pre_alembic.db` 백업을 복원
   ```bash
   cd ~/momoai_web
   sudo systemctl stop momoai
   cp backups/momoai_<타임스탬프>_pre_alembic.db instance/momoai.db
   ```
4. 코드도 같이 되돌려야 하면 아래 B의 2~4단계를 이어서 수행
5. `sudo systemctl start momoai` 후 `systemctl is-active momoai`로 확인

## B. 코드 반영 후 서비스가 안 뜨거나 즉시 죽는 경우

1. `ssh chsh82@momoai.kr`
2. `journalctl -u momoai -n 100`로 에러 확인
3. 직전 정상 커밋 확인: `cd ~/momoai_web && git log --oneline -10`
4. 그 커밋으로 되돌리기(코드 + CSS 둘 다, 커밋에 박혀있는 CSS를 신뢰하지
   말고 **반드시 그 커밋 기준으로 직접 재빌드**한다 - 과거 커밋의 CSS가
   당시에 수동으로 빌드·커밋된 거라 최신이 아닐 수 있음):
   ```bash
   cd ~/momoai_web
   git reset --hard <직전_정상_커밋_해시>
   npm ci
   NODE_ENV=production npm run build:css
   ```
5. DB 스키마가 새 코드 기준으로 이미 바뀌었고 구코드와 안 맞으면 위 A의
   DB 복원도 함께 수행
6. `sudo systemctl restart momoai`
7. `systemctl is-active momoai` + 실제 페이지 로딩 확인(가능하면 모모
   에이전트 등 최근 변경된 화면 직접 확인)

## C. 일반 원칙

- 코드와 CSS는 **항상 같은 커밋 기준으로 같이 되돌린다**(한쪽만 되돌리면
  이번에 고친 "코드는 새 것, CSS는 헌 것" 문제가 롤백 과정에서 재발할 수
  있음).
- `git reset --hard`는 로컬 변경사항을 날리는 파괴적 명령이다 - 운영
  디렉터리에 배포 스크립트 밖에서 수동으로 건드린 파일이 있는지 먼저
  `git status`로 확인하고 진행한다.
- 가능하면 이 문서의 수동 절차 대신, 문제를 고친 커밋을 새로 만들어
  `master`에 push해서 정식 파이프라인(검증→반영)을 다시 타게 하는 쪽을
  우선한다 - 수동 SSH 복구는 정식 파이프라인을 못 쓸 정도로 급할 때만.
