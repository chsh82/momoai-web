# -*- coding: utf-8 -*-
"""
공부력 레벨 테스트 채점 엔진
momoai.kr 이식용. 외부 의존성 없음 (표준 라이브러리만).

채점식 : 문항점수 = 배점 × (응답−1)/4,  역문항은 배점 × (5−응답)/4
          평가요소 만점 = 배점 합,  총점 만점 = 200점 (중등 8요소×25 / 초등 5요소×40)
레벨    : 총점을 20점 구간으로 분할. LV1 20~40 … LV9 180~200
"""
import json, math
from pathlib import Path

BASE = Path(__file__).parent

# 판정 임계값 — 모두 파일럿 데이터로 보정할 값
INFLATE_MIN = 2      # 부풀림 탐지 문항 중 '매우 그렇다'(5) 응답이 이 수 이상이면 경고
FLAT_SD = 0.55       # 원응답값 표준편차가 이 값 미만이면 무성의 응답으로 보고 레벨 미산출
TOPHEAVY_GAP = 12    # 상위영역 평균 − 하위영역 평균이 이 값 이상이면 역피라미드 경고

LOWER_KEYS = {"MOT", "BAS", "RES", "ATT"}          # 토대 영역
UPPER_KEYS = {"EXE", "OBJ", "FLW", "SLF", "MET"}   # 자기관리·점검 영역


def load():
    items = json.loads((BASE / "items.json").read_text(encoding="utf-8"))
    content = json.loads((BASE / "content.json").read_text(encoding="utf-8"))
    return items, content


def _round(x, digits=0):
    """JS Math.round 호환 (.5는 항상 올림)."""
    m = 10 ** digits
    return math.floor(x * m + 0.5) / m


def build_form(grade, respondent, items_json, content):
    """
    grade      : 'mid' | 'elem'
    respondent : 'student' | 'parent'
    학부모 응답은 관찰 가능한 영역만 출제하고 레벨을 산출하지 않는다.
    문항 순서는 고정 셔플이라 모든 학생이 같은 순서를 본다.
    """
    elements = content["elements"][grade]
    qs = items_json["forms"][grade]["items"]
    if respondent == "parent":
        obs = content["parent_observable"][grade]
        elements = [e for e in elements if e["k"] in obs]
        core = [q for q in qs if q["e"] in obs]
        valid = [q for q in qs if q["e"] == "V"][:2]
        qs = core + valid
    gate_all = content["gates"][grade]
    full = [e["k"] for e in content["elements"][grade]]
    gates = [gate_all[full.index(e["k"])] for e in elements]
    return {"elements": elements, "gates": gates, "items": arrange(qs)}


def arrange(items):
    """같은 요소 문항이 이어붙지 않도록 고정 순서로 재배열.
       요소를 돌아가며 한 문항씩 뽑고, 매 바퀴 시작 요소를 한 칸씩 민다.
       부풀림 문항(V)은 마지막에 고르게 끼워 넣는다. JS 구현과 결과가 동일하다."""
    by_e, keys = {}, []
    for q in items:
        if q["e"] == "V":
            continue
        if q["e"] not in by_e:
            by_e[q["e"]] = []
            keys.append(q["e"])
        by_e[q["e"]].append(q)
    rounds = max(len(v) for v in by_e.values())
    out = []
    for r in range(rounds):
        for i in range(len(keys)):
            k = keys[(i + r) % len(keys)]
            if r < len(by_e[k]):
                out.append(by_e[k][r])
    V = [q for q in items if q["e"] == "V"]
    for i, q in enumerate(V):
        out.insert(math.floor((i + 1) * len(out) / (len(V) + 1)) + i, q)
    return out


def score(answers, form, respondent="student"):
    """
    answers : list[int]  각 문항 응답 1~5. 길이 = form['items'] 길이.
    form    : build_form() 반환값
    """
    items, elements, gates = form["items"], form["elements"], form["gates"]
    keys = [e["k"] for e in elements]
    if len(answers) != len(items):
        raise ValueError("응답 수(%d)가 문항 수(%d)와 다릅니다" % (len(answers), len(items)))

    raw = {k: 0.0 for k in keys}
    mx = {k: 0.0 for k in keys}
    core, v5, vn = [], 0, 0
    for it, v in zip(items, answers):
        if not (1 <= v <= 5):
            raise ValueError("응답값 범위 오류: %r (1~5)" % v)
        if it["e"] == "V":
            vn += 1
            if v == 5:
                v5 += 1
            continue
        rev = bool(it.get("rev"))
        core.append(v)  # 원응답값 (역문항 보정 금지)
        raw[it["e"]] += it["w"] * ((5 - v) if rev else (v - 1)) / 4
        mx[it["e"]] += it["w"]

    pct = {k: (_round(raw[k] / mx[k] * 1000) / 10 if mx[k] else 0) for k in keys}
    raw_total = sum(raw.values())
    raw_max = sum(mx.values())
    total = int(_round(raw_total / raw_max * 200))
    level = min(9, max(1, total // 20))

    weak = next((i for i, k in enumerate(keys) if pct[k] < gates[i]), -1)

    lo = [pct[k] for k in keys if k in LOWER_KEYS]
    up = [pct[k] for k in keys if k in UPPER_KEYS]
    topheavy = bool(lo and up and (sum(up) / len(up) - sum(lo) / len(lo) >= TOPHEAVY_GAP))

    mean = sum(core) / len(core)
    sd = math.sqrt(sum((x - mean) ** 2 for x in core) / len(core))
    flat = sd < FLAT_SD
    is_parent = respondent == "parent"

    return {
        "respondent": respondent,
        "elements": [{"key": k, "name": elements[i]["n"], "area": elements[i]["area"],
                      "group": elements[i]["g"], "raw": _round(raw[k] * 10) / 10,
                      "max": mx[k], "score": pct[k], "gate": gates[i],
                      "pass": pct[k] >= gates[i]} for i, k in enumerate(keys)],
        "total": total, "raw_total": _round(raw_total * 10) / 10, "raw_max": raw_max,
        # 학부모 응답과 일관 응답은 레벨을 내지 않는다
        "level": None if (is_parent or flat) else level,
        "level_suppressed": "parent_form" if is_parent else ("flat_response" if flat else None),
        "weak_index": weak, "weak_key": keys[weak] if weak >= 0 else None,
        "flags": {"inflate": v5 >= INFLATE_MIN, "inflate_count": v5, "validity_items": vn,
                  "flat": flat, "sd": _round(sd * 100) / 100, "topheavy": topheavy},
    }


def level_info(level, content):
    return content["levels"][level - 1] if level else None


if __name__ == "__main__":
    items_json, content = load()
    for grade in ("mid", "elem"):
        for who in ("student", "parent"):
            f = build_form(grade, who, items_json, content)
            # 긍정문 4점 / 역문항 2점 = 상위권 응답 패턴
            ans = [2 if q["e"] == "V" else (2 if q.get("rev") else 4) for q in f["items"]]
            r = score(ans, f, who)
            L = level_info(r["level"], content)
            print(grade, who, "문항", len(f["items"]),
                  "→ 총점", r["total"],
                  ("LV%d %s" % (r["level"], L["n"])) if L else "(레벨 미산출: %s)" % r["level_suppressed"],
                  "| 우선영역:", r["weak_key"] or "없음",
                  "| flags:", {k: v for k, v in r["flags"].items() if v is True})
