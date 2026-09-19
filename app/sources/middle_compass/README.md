# 전공 나침반 — 이식 패키지

중등 관심 전공 성향 검사. 서울대 학과 체계를 18개 학과군으로 나눈다.
호기심 지도와 **채점 엔진 구조가 동일**하고(무작위 응답 기준 표준화), 차이는 세 가지다.

1. 학생 화면에도 실제 학과명을 노출한다.
2. 학과군마다 고교 선택과목이 붙는다.
3. 결과에 초등 9마을 대응이 함께 나온다 (종단 대조용).

| 파일 | 내용 |
|---|---|
| `items.json` | 문항 은행 (`mid` 40문항) |
| `content.json` | 18학과군 정의, 4축 정의, 인장 SVG |
| `scoring.py` | 채점 엔진 + 렌더 페이로드 조립 (의존성 없음) |

---

## 1. 데이터 스키마

문항 구조는 호기심 지도와 동일하다. 마을 키 대신 학과군 키를 쓴다.

```jsonc
{ "p": "계열 안에서",
  "q": "자연과학 안에서 더 끌리는 일은?",
  "o": [ { "t": "전제에서 결론까지 빈틈없이 증명한다",
           "v": { "MATH": 3 }, "a": { "T":1, "I":1, "R":1 } }, … ] }
```

학과군 하나:
```jsonc
"MATH": {
  "n": "수학·통계", "c": "#2C7A8C",
  "vil": "비밀 실험실",                    // ← 초등 호기심 지도 대응 마을
  "col": "자연과학대학",                   // 소속 단과대
  "dept": "수리과학부, 통계학과",          // 서울대 학과 실명
  "line": "전제에서 결론까지 …",
  "sub": "미적분, 기하, 확률과 통계, …",   // 고교 선택과목
  "q": [탐구주제 3], "b": [도서 2], "w": [글감 2]
}
```

### 18학과군 키
`LIT HUM LAW ECON SOC MEDIA MATH PHYS CHEM BIO MECH ELEC ARCH MED PHAR AGRI EDU ART`

색상은 대응 마을의 색 계열을 쓴다. 초등 검사와 나란히 놓았을 때 계통이 보인다.

---

## 2. 채점 계약

```python
from scoring import load, score, render_payload

items, content = load("mid")
result  = score(picks, "mid", items)
payload = render_payload(result, content)
```

### 출력 (`score`)
```jsonc
{
  "form": "mid",
  "rank": [ { "key":"MATH", "raw":14, "z":1.83, "score":72 }, … ],   // 18개
  "axes": [ … ],
  "unresolved": false,       // 미수렴 판정 (상위 3개가 붙어 있음)
  "top3": ["MATH","PHYS","ELEC"]
}
```

### 출력 (`render_payload`)
- `student.headline` — 1·2순위 학과군 이름
- `student.from_villages` — 상위 5개 학과군을 마을로 가중 집계한 순서
- `student.cards[]` — 학과명·선택과목·탐구·도서·글감 포함 (중등은 노출해도 된다)
- `teacher.table[]` — 18개 전체 + `village` 열 (초등 결과와 대조용)

---

## 3. 문항 구성

| 파트 | 문항 | 형식 | 역할 |
|---|---|---|---|
| 기사 관심 | 8 | 4지선다 | 계열 간 대분류 |
| 수행평가 주제 | 8 | 4지선다 | 실제 활동 선호 |
| 진술 선호 | 8 | 2지선다 | 세계관 축 |
| 활동·과목 | 8 | 4지선다 | 과목·동아리·진로 장면 |
| **계열 안에서** | 8 | 4지선다 | **계열 내부 학과 변별 (배점 3점)** |

마지막 파트가 학과 수준까지 좁히는 핵심이다. 자연과학 안에서 증명이냐 측정이냐
합성이냐 생명이냐를 강제로 고르게 한다. 이 8문항을 넣고 배점이 가장 얇던
약학·간호가 10 → 15점, 의학 계열이 13 → 18점으로 올라갔다.

---

## 4. 검증값

무작위 응답 3만 회, 18개 균등값 5.6%

| 지표 | 값 |
|---|---|
| 1순위 분포 | 4.6 ~ 6.7% |
| 미수렴 판정 | 16.5% |

미수렴 16.5%는 무작위 응답 기준이다. 실제 학생은 일관되게 답하므로 낮게 나오지만,
중3에서도 이 비율이 높으면 학부모 불만이 생긴다. 파일럿 후 임계값 조정이 필요하다.

---

## 5. Flask 연동 예시

```python
from tests.major_compass.scoring import load, score, render_payload

_ITEMS, _CONTENT = load("mid")

@bp.get("/form")
def get_form():
    return jsonify([{ "p": i["p"], "q": i["q"],
                      "o": [o["t"] for o in i["o"]] } for i in _ITEMS])

@bp.post("/submit")
def submit():
    body = request.get_json()
    result  = score(body["answers"], "mid", _ITEMS)
    payload = render_payload(result, _CONTENT)
    save_attempt(body["student_id"], body["answers"], result)
    # 초등 결과가 있으면 종단 비교를 붙인다
    prev = fetch_latest_curiosity(body["student_id"])
    if prev:
        payload["longitudinal"] = compare(prev["rank"], result, _CONTENT)
    return jsonify(payload)
```

### 종단 비교 방법
초등 결과의 `top3` (마을 키)와 중등 결과의 `student.from_villages` 를 대조한다.
**이동 자체는 문제가 아니다. 이동의 계기를 묻는 것이 상담의 핵심이다.**

---

## 6. 저장 스키마 제안

```sql
CREATE TABLE compass_attempt (
  id          BIGSERIAL PRIMARY KEY,
  student_id  BIGINT NOT NULL,
  taken_at    DATE   NOT NULL,
  answers     JSONB  NOT NULL,
  rank        JSONB  NOT NULL,
  axes        JSONB  NOT NULL,
  unresolved  BOOLEAN NOT NULL,
  engine_ver  TEXT   NOT NULL      -- 'mc-0.2'
);
```

재검사 주기는 한 학기. 축이 초등과 동일하므로 `axes` 는 초3부터 고1까지
한 그래프에 그대로 올라간다.

---

## 7. 조정 가능한 상수

| 상수 | 현재값 | 의미 |
|---|---|---|
| `UNRESOLVED_GAP` | 0.35 | 1순위 z − 3순위 z 가 이 값 이하면 미수렴 |
| `UNRESOLVED_FLOOR` | 0.50 | 1순위 z 가 이 값 미만이면 미수렴 |

## 8. 남은 작업
- 약학·간호 문항 2~3개 보강 (18개 중 여전히 최저 배점 15점)
- 추천 도서를 모모의 책장 보유 도서로 교체
- 고교 선택과목은 학교 개설 과목·대학 권장 이수 과목과 대조 필요 (참고용 표기 유지)
- 고등 버전은 학과군 18개를 학과·탐구주제 단위로 다시 분해. 축은 그대로 둘 것
