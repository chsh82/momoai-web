# 튜토리얼 개발 1단계 — 초등 코스1을 momoai.kr에서 동작시키기

너는 momoai.kr 리포에서 작업한다. 0단계에서 만든 `app/tutorial/content/elem/course1.json`을 읽어,
**로그인한 학생이 홈 → 레슨(카드 읽기) → 문제 풀기 → 결과까지 실제로 눌러서 진행**할 수 있게 만든다.
진도와 정답을 DB에 저장한다. 참고 화면설계 HTML(초등 샘플)이 함께 전달된다 — 이 파일의 CSS와 JS를 최대한 그대로 재사용한다.

---

## 먼저 리포를 조사한다 (추측하지 말 것)

아래를 코드에서 직접 확인하고, 확인한 실제 경로/이름을 쓴다. 못 찾으면 나에게 물어본다.

1. **앱 팩토리와 블루프린트 등록 방식** — `create_app()`이 어디 있고 기존 블루프린트를 어떻게 `register_blueprint` 하는가. 같은 방식으로 `tutorial` 블루프린트를 등록한다.
2. **base.html의 블록 이름** — `{% block content %}` / `{% block title %}` / `{% block scripts %}` 등 실제 이름. 새 템플릿이 이걸 `extends` 한다.
3. **로그인 사용자 모델** — Flask-Login `current_user`의 모델명·PK, 그리고 **학생/학부모를 구분하는 필드**(예: role). 튜토리얼은 학생만 진도를 저장한다.
4. **CSRF 설정** — Flask-WTF `CSRFProtect`가 켜져 있는가. 켜져 있으면 `fetch POST`에 CSRF 토큰을 반드시 실어야 한다(아래 참조).
5. **정적 파일 경로** — 기존 `static/` 구조(css/js 위치)와 `url_for('static', ...)` 관례.
6. **마일리지 적립 함수 `award_points()`** — `mileage_service.py`에 있다. 모든 적립은 이 함수 하나를 통해서만 나가고(라우트가 `point_events`에 직접 INSERT하지 않음), 활동코드별 `confirm_delay_hours`로 즉시 확정/pending을 정한다. 튜토리얼은 퀴즈(QZ01/QZ02)와 같은 **즉시 확정** 패턴을 따른다. 함수 시그니처와 활동코드 등록 방식(활동코드 테이블/상수, 포인트 값·상한·`confirm_delay_hours` 설정 위치)을 코드에서 확인하고 그대로 맞춘다.

---

## 만들 것

### 1. 블루프린트 `app/tutorial/`

```
app/tutorial/
  __init__.py          # bp = Blueprint('tutorial', __name__, url_prefix='/tutorial',
                       #                 template_folder='templates', static_folder=None)
  routes.py
  models.py
  content.py           # JSON 로더
  content/elem/course1.json   # 0단계 산출물 (이미 있음)
  templates/tutorial/
    home.html
    lesson.html
    result.html
```

`create_app()`에서 이 블루프린트를 기존 방식과 동일하게 등록한다.

### 2. 콘텐츠 로더 `content.py`

- 앱 시작 시 `content/` 아래 JSON을 한 번 읽어 메모리에 캐시하는 단순 함수.
  `get_course(track, course)`, `get_lesson(track, course, lesson_id)` 정도.
- 파일이 없거나 JSON이 깨지면 빈 값이 아니라 **명확한 에러 로그**를 남긴다.

### 3. 모델 `models.py` — 새 테이블 2개

기존 `db = SQLAlchemy()` 인스턴스를 import 해서 쓴다(새로 만들지 말 것).

```python
class TutorialProgress(db.Model):
    __tablename__ = 'tutorial_progress'
    id         = mapped_column(Integer, primary_key=True)
    user_id    = mapped_column(ForeignKey('<실제 유저 테이블>.id'), index=True, nullable=False)
    track      = mapped_column(String(16), nullable=False)   # 'elem'
    course     = mapped_column(String(16), nullable=False)   # 'course1'
    lesson_id  = mapped_column(String(32), nullable=False)   # 'elem-c1-l1'
    status     = mapped_column(String(16), default='in_progress')  # in_progress|done
    score      = mapped_column(Integer, default=0)
    total      = mapped_column(Integer, default=0)
    done_at    = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint('user_id','lesson_id', name='uq_prog_user_lesson'),)

class TutorialAttempt(db.Model):
    __tablename__ = 'tutorial_attempt'
    id          = mapped_column(Integer, primary_key=True)
    user_id     = mapped_column(ForeignKey('<실제 유저 테이블>.id'), index=True, nullable=False)
    lesson_id   = mapped_column(String(32), nullable=False)
    question_id = mapped_column(String(48), nullable=False)
    rule_no     = mapped_column(String(8))
    correct     = mapped_column(Boolean, nullable=False)
    created_at  = mapped_column(DateTime, default=datetime.utcnow)
```

추가로 **코스 완료 보상 지급 기록** 테이블 하나를 더 둔다. 코스별 100점을 최초 1회만 주기 위한 중복 방지 장치다.

```python
class TutorialCourseReward(db.Model):
    __tablename__ = 'tutorial_course_reward'
    id        = mapped_column(Integer, primary_key=True)
    user_id   = mapped_column(ForeignKey('<실제 유저 테이블>.id'), index=True, nullable=False)
    track     = mapped_column(String(16), nullable=False)   # 'elem'
    course    = mapped_column(String(16), nullable=False)   # 'course1'
    points    = mapped_column(Integer, default=100)
    rewarded_at = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id','track','course', name='uq_reward_user_course'),)
```

- SQLAlchemy 2.0 스타일(`mapped_column`)을 쓰되, **기존 모델이 1.x 선언형이면 그 스타일에 맞춘다.** 리포의 기존 모델을 먼저 보고 통일한다.
- 이 프로젝트는 기동 시 `db.create_all()`이 도니 새 테이블은 자동 생성된다. 그래도 **Alembic 마이그레이션 파일을 생성**하고(`flask db migrate -m "tutorial progress/attempt/reward"`), 리뷰 후 커밋한다. 서버 반영은 기존 패턴(create_all이 만들고 Alembic stamp)을 따른다.

### 4. 라우트 `routes.py`

- `GET /tutorial/` → `home.html`. 코스 목록과 **현재 사용자의 코스1 진도**(완료 레슨 수/전체)를 계산해 넘긴다.
- `GET /tutorial/elem/course1/<lesson_id>` → `lesson.html`.
  레슨 dict를 `tojson`으로 템플릿에 심는다(SSR 유지, 별도 API 왕복 없음).
  **한 레슨은 학습 화면과 퀴즈 화면 두 단계로 나뉜다.** 두 화면 모두 이 한 라우트/한 템플릿 안의 `.screen` 섹션이고, "퀴즈 풀기" 버튼을 누르면 `tutorial.js`가 화면만 전환한다(서버 왕복 없음). 샘플 HTML의 `#learn`(카드 + 퀴즈 풀기 버튼) → `#quiz-screen`(문제 + 다시 읽기 버튼) 구조를 그대로 옮긴다. 진행 점(dots)과 결과 버튼은 퀴즈 화면에만 둔다.
- `POST /tutorial/api/answer` (login_required) → `{lesson_id, question_id, rule_no, correct}` 저장(Attempt 1행).
- `POST /tutorial/api/complete` (login_required) → 해당 레슨 Progress를 `done`, score/total 기록, `done_at` 설정.
  그런 다음 **코스 완료 판정 + 마일리지 적립**을 아래 5절대로 처리한다.
- 비로그인 사용자: 레슨 열람은 허용하되, 저장 API는 401을 반환하고 프런트는 "로그인하면 진도가 저장돼요" 안내만 띄운다. (진도 없이도 문제는 풀린다)

권한: 학부모 계정은 진도 저장 대상이 아니다. `current_user`가 학생이 아닐 때 저장 API는 조용히 무시(204)한다.

### 4-1. 마일리지 적립 — 코스 완료 시 100점 (코스별 최초 1회)

적립은 **레슨 단위가 아니라 코스 단위**다. `/api/complete`에서 방금 레슨을 `done` 처리한 직후, 아래를 순서대로 한 트랜잭션에서 처리한다.

1. 방금 완료된 레슨이 속한 **코스의 전체 레슨 id 목록**을 콘텐츠 JSON에서 읽는다.
2. 이 학생의 `TutorialProgress` 중 그 코스에서 `status='done'`인 레슨 수를 센다.
3. `done 수 == 코스 전체 레슨 수`가 **이번에 처음으로** 참이 됐는지 확인한다.
   판정 근거는 `TutorialCourseReward`의 존재 여부다 — `(user_id, track, course)` 행이 **없을 때만** 적립한다.
4. 적립: `award_points()`를 호출한다. 활동코드는 **새로 하나 만든다**(예 `TU01`, 활동명 "튜토리얼 코스 완료", 100점, `confirm_delay_hours=0` → 즉시 confirmed). 활동코드·포인트·확정지연을 등록하는 위치는 기존 QZ01/QZ02가 등록된 방식과 **똑같은 자리**에 추가한다.
5. 적립에 성공하면 `TutorialCourseReward` 행을 INSERT 한다. `award_points()` 호출과 이 INSERT는 **같은 트랜잭션**으로 묶어, 점수만 나가고 기록이 안 남는(또는 그 반대) 상황을 막는다. 유니크 제약(`uq_reward_user_course`)이 동시요청 중복까지 방어한다.

주의:
- 이미 코스를 깬 학생이 아무 레슨이나 **다시 풀어** 완료 조건이 또 참이 돼도, 3번의 `TutorialCourseReward` 존재 검사에서 걸러져 **재적립되지 않는다.**
- 상한(일일/월) 정책이 `award_points()` 안에서 적용된다면 그 결과(적립 거부/부분 적립)를 그대로 존중한다. 튜토리얼 쪽에서 상한을 우회하지 않는다.
- 코스 완료로 적립이 발생했는지 여부를 `/api/complete` 응답에 담아(`{"course_completed": true, "points": 100}`) 프런트가 결과 화면에서 "코스 완료! +100 모모 마일리지"를 보여줄 수 있게 한다. 코스 완료가 아니면 이 필드는 false.

### 5. 템플릿 (base.html 상속, Tailwind는 바깥 뼈대만)

- 세 템플릿 모두 `{% extends 'base.html' %}` 하고 실제 블록 이름을 쓴다.
- 튜토리얼 고유 스타일(원고지 칸·초등 팔레트·카드)은 **Tailwind로 옮기지 말고** 아래 CSS 파일을 링크한다.
  이유: Tailwind 재빌드 없이 배포되게, 그리고 원고지 칸은 유틸리티로 표현하기 어렵다.
- `home.html`은 코스 카드 3개(코스1 활성, 2·3 잠금)와 진도바. 샘플의 홈 마크업을 옮긴다.
- `lesson.html`은 **두 개의 `.screen` 섹션**을 담는다:
  - `#learn` — 카드 컨테이너(빈 div) + 맨 아래 "퀴즈 풀기" 버튼
  - `#quiz-screen` — 진행 점 + 문제 컨테이너(빈 div) + "다시 읽기" 버튼
  실제 카드/문제 렌더와 두 화면 사이 전환은 `tutorial.js`가 한다. 처음 진입 시 `#learn`만 보이고 `#quiz-screen`은 숨긴다.
  레슨 데이터는 `<script id="lessonData" type="application/json">{{ lesson|tojson }}</script>`로 심는다.
- `result.html`은 라우트에서 계산한 점수·마일리지·다시 볼 규정을 SSR로 보여준다.
  (또는 lesson.html 안에서 JS로 결과 화면 전환 — 샘플처럼 단일 페이지 전환이면 result.html은 생략 가능. 샘플 구조를 따르되, 새로고침해도 진도가 남게 저장은 서버에 한다.)

### 6. 정적 파일

- `app/static/css/tutorial.css` — **전달된 샘플 HTML의 `<style>` 내용을 그대로** 옮긴다.
  (`:root` 초등 팔레트 변수, `.gp` 원고지 칸, `.card`, `.opt`, `.result` 등. base.html의 Tailwind와 클래스명이 겹치지 않는지만 확인한다. 겹치면 `.tut-` 프리픽스를 붙인다)
- `app/static/js/tutorial.js` — 샘플의 `<script>` 내용을 옮기되 다음만 바꾼다:
  - 하드코딩된 `LESSON` 상수를 지우고, `#lessonData` script 태그의 JSON을 파싱해 쓴다.
  - 문항을 맞히면 `POST /tutorial/api/answer` 를, 레슨을 다 풀면 `POST /tutorial/api/complete` 를 `fetch`로 호출한다. 저장 실패해도 화면 진행은 막지 않는다(진도는 best-effort).
  - **정답 표시(○/✕ 도장)는 샘플에 이미 구현돼 있으니 그대로 옮긴다.** 문항을 풀면 정답이면 초록 ○, 틀리면 빨강 ✕가 선택지/입력 영역 오른쪽 위에 찍힌다(`.stamp` + `settle()`). 지우지 말 것. 선택지 채점은 `opts.children`가 아니라 **버튼 배열**을 순회해야 한다(도장이 첫 자식이라 인덱스가 밀리는 버그 방지 — 샘플에 반영돼 있음).
  - **CSRF**: 아래처럼 토큰을 헤더에 싣는다.

### 7. CSRF (Flask-WTF가 켜져 있으면 필수)

base.html(또는 lesson.html)의 `<head>`에 `<meta name="csrf-token" content="{{ csrf_token() }}">`가 있는지 확인하고, 없으면 튜토리얼 템플릿 블록에 추가한다. `tutorial.js`의 fetch는:

```js
function post(url, body){
  const t=document.querySelector('meta[name="csrf-token"]');
  return fetch(url,{method:'POST',
    headers:{'Content-Type':'application/json', ...(t?{'X-CSRFToken':t.content}:{})},
    body:JSON.stringify(body)}).catch(()=>{});
}
```

라우트는 JSON 요청에서 `X-CSRFToken` 헤더를 CSRF로 인정하도록 한다(Flask-WTF 기본 동작 확인).

### 8. 진입점

- 기존 네비게이션/사이드바(학생용)에서 튜토리얼로 가는 링크 하나를 추가한다. 위치는 기존 학생 메뉴 관례를 따른다.

---

## 검증 (Playwright — 리포에 이미 있는 개발용 스크립트 방식 재사용)

로컬에서 다음을 통과해야 한다:

1. 서버 기동 후 `tutorial_progress`, `tutorial_attempt`, `tutorial_course_reward` 테이블이 생성됐는지 확인.
2. 학생 계정으로 `/tutorial/` 진입 → 코스1 카드 보임.
3. 레슨 진입 → **학습 화면(`#learn`)만** 보이고 카드 4장이 원고지 그림과 함께 렌더(특히 `{20}`가 한 칸에 두 글자, `!`가 강조로 보이는지). 이 시점에 퀴즈는 화면에 없다.
3-1. 학습 화면 맨 아래 "퀴즈 풀기" 버튼을 누르면 퀴즈 화면(`#quiz-screen`)으로 전환되고, "다시 읽기"를 누르면 학습 화면으로 돌아온다(둘 다 서버 왕복 없음).
4. 문제 1·2·4(고르기) 정답/오답 즉시 피드백, 문제 3(칸 채우기)에서 `20 26 년`을 올바른 칸에 놓으면 초록, 틀리면 빨강.
5. 4문제 다 풀면 결과가 뜨고, **DB에 Progress 1행(status=done) + Attempt 4행**이 저장됐는지 쿼리로 확인.
6. **코스 완료 적립**: 코스1의 레슨이 지금은 1개뿐이므로, 이 레슨을 done 하면 곧 코스 완료다. `award_points()`로 100점이 **즉시 confirmed**로 적립되고 `tutorial_course_reward`에 1행이 남는지 확인. `point_events`(또는 실제 포인트 테이블)에 활동코드 `TU01` 100점 행이 confirmed로 들어갔는지도 확인.
7. **중복 방지**: 같은 레슨을 다시 풀어 다시 완료해도 100점이 **또 적립되지 않고** `tutorial_course_reward` 행이 그대로 1개인지 확인.
8. 새로고침 후 홈 진도바가 반영됐는지 확인.
9. 비로그인으로 저장 API 호출 시 401, 화면은 계속 진행됨. 학부모 계정으로 저장 API 호출 시 204(무시), 적립 없음.

스크린샷을 `scripts/` 관례에 맞춰 저장하고, 통과 여부를 보고한다.

> 참고: 지금은 코스1에 레슨이 1개라 "코스 완료 = 레슨 완료"지만, 적립 판정 코드는 반드시 **"코스의 전 레슨 done"** 기준으로 짠다. 레슨 2·3이 추가되면 그때 자동으로 마지막 레슨에서만 적립되게, 레슨 수를 하드코딩하지 말고 콘텐츠 JSON에서 세도록 한다.

---

## 범위 밖 (다음 단계)

- 중등 트랙, 코스2·코스3, 원고지 연습장, 교사용 오답률 화면 → 손대지 않는다.
- 마일리지 시스템 자체를 새로 만들지 않는다. 기존 `award_points()`에 활동코드 `TU01`만 추가해 연동한다(4-1절).
- 표기 기준 미결(접속부사 뒤 쉼표, 가운뎃점) 관련 문항은 이번 콘텐츠에 없으니 신경 쓸 것 없다.

## 커밋

- 논리 단위로 나눠 커밋(블루프린트/모델/템플릿+정적/검증).
- **컴파일된 CSS가 필요하면 함께 커밋**한다(배포가 `git reset --hard`라 서버에서 빌드 안 함). tutorial.css는 순수 CSS라 빌드 불필요.
- 커밋 메시지는 한글, 기존 리포 관례를 따른다.
