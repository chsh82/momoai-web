# -*- coding: utf-8 -*-
"""
전공 나침반 — 중등 관심 전공 성향 검사 채점 엔진
momoai.kr 이식용. 외부 의존성 없음 (표준 라이브러리만).

핵심: 학과군마다 문항 은행에 실린 배점 총량과 2지/4지 등장 비율이 달라
      아무렇게나 찍어도 특정 학과군이 1순위가 되기 쉽다. 그래서 무작위 응답을
      기준선으로 삼아 표준점수(z)로 순위를 낸다. 문항을 더하거나 빼도
      기준선이 자동으로 다시 계산되므로 은행 확장 시 균형을 따로 맞출 필요가 없다.
"""
import json, math, os
from pathlib import Path

BASE = Path(__file__).parent
GROUP_ORDER = ["LIT", "HUM", "LAW", "ECON", "SOC", "MEDIA", "MATH", "PHYS", "CHEM",
               "BIO", "MECH", "ELEC", "ARCH", "MED", "PHAR", "AGRI", "EDU", "ART"]
AXIS_PAIRS = [("P", "T"), ("I", "M"), ("L", "N"), ("R", "C")]

# 미수렴 판정 임계값 — 파일럿 데이터로 보정할 값
UNRESOLVED_GAP = 0.35    # 1순위 z - 3순위 z 가 이 값 이하면 미수렴
UNRESOLVED_FLOOR = 0.50  # 1순위 z 가 이 값 미만이면 미수렴


def load(form="mid"):
    """form: 'mid'(중등 40문항)"""
    items = json.loads((BASE / "items.json").read_text(encoding="utf-8"))
    content = json.loads((BASE / "content.json").read_text(encoding="utf-8"))
    return items["forms"][form]["items"], content


def _round(x, digits=0):
    """JS Math.round 호환 (.5는 항상 올림). Python round()는 은행가 반올림이라 다름."""
    m = 10 ** digits
    return math.floor(x * m + 0.5) / m


def baseline(items):
    """무작위 응답의 기대값과 분산. 문항 세트에서만 계산되며 응답과 무관하다."""
    E = {k: 0.0 for k in GROUP_ORDER}
    Var = {k: 0.0 for k in GROUP_ORDER}
    for it in items:
        n = len(it["o"])
        for k in GROUP_ORDER:
            m = m2 = 0.0
            for o in it["o"]:
                w = o["v"].get(k, 0)
                m += w
                m2 += w * w
            m /= n
            m2 /= n
            E[k] += m
            Var[k] += (m2 - m * m)
    return E, Var


def score(answers, form="mid", items=None):
    """
    answers : list[int]  각 문항에서 고른 선택지 index (0부터). 길이 = 문항 수.
    반환    : dict (아래 RESULT SCHEMA 참조)
    """
    if items is None:
        items, _ = load(form)
    if len(answers) != len(items):
        raise ValueError("응답 수(%d)가 문항 수(%d)와 다릅니다" % (len(answers), len(items)))

    raw = {k: 0 for k in GROUP_ORDER}
    axes = {k: 0 for k in "PTIMLNRC"}
    for it, pick in zip(items, answers):
        if pick is None or not (0 <= pick < len(it["o"])):
            raise ValueError("선택지 index 범위 오류: %r" % pick)
        o = it["o"][pick]
        for k, v in o["v"].items():
            raw[k] += v
        for k, v in o.get("a", {}).items():
            axes[k] += v

    E, Var = baseline(items)
    z = {}
    for k in GROUP_ORDER:
        sd = math.sqrt(Var[k])
        z[k] = (raw[k] - E[k]) / sd if sd > 0 else 0.0

    rank = sorted(
        ({"key": k,
          "raw": raw[k],
          "z": _round(z[k] * 100) / 100,
          "score": max(5, min(99, int(_round(50 + 12 * z[k]))))}
         for k in GROUP_ORDER),
        key=lambda r: (-r["z"], -r["raw"]))

    unresolved = (rank[0]["z"] - rank[2]["z"]) <= UNRESOLVED_GAP or rank[0]["z"] < UNRESOLVED_FLOOR
    axis_out = [{"left": a, "right": b,
                 "left_score": axes[a], "right_score": axes[b],
                 "position": int(_round(axes[b] / (axes[a] + axes[b] or 1) * 100))}
                for a, b in AXIS_PAIRS]

    return {"form": form, "rank": rank, "axes": axis_out, "unresolved": unresolved,
            "top3": [r["key"] for r in rank[:3]]}


def render_payload(result, content):
    """화면 렌더용 조립. 중등부터는 학생층에도 실제 학과명을 노출한다.
       teacher.table 의 village 열은 초등 호기심 지도와의 종단 대조용이다."""
    G = content["groups"]
    top = result["rank"][:3]
    student = {
        "headline": " · ".join(G[r["key"]]["n"] for r in top[:2]),
        "unresolved": result["unresolved"],
        "axes": result["axes"],
        "from_villages": _village_summary(result, G),
        "cards": [{
            "rank": i + 1, "key": r["key"], "name": G[r["key"]]["n"], "color": G[r["key"]]["c"],
            "score": r["score"], "line": G[r["key"]]["line"],
            "college": G[r["key"]]["col"], "departments": G[r["key"]]["dept"],
            "subjects": G[r["key"]]["sub"], "quests": G[r["key"]]["q"],
            "books": G[r["key"]]["b"], "prompts": G[r["key"]]["w"],
        } for i, r in enumerate(top)],
    }
    teacher = {
        "unresolved": result["unresolved"], "axes": result["axes"],
        "table": [{
            "rank": i + 1, "key": r["key"], "name": G[r["key"]]["n"],
            "score": r["score"], "z": r["z"],
            "college": G[r["key"]]["col"], "village": G[r["key"]]["vil"],
        } for i, r in enumerate(result["rank"])],
    }
    return {"student": student, "teacher": teacher}


def _village_summary(result, G):
    """상위 5개 학과군이 초등 9마을 중 어느 계열에서 왔는지 가중 집계."""
    tally = {}
    for i, r in enumerate(result["rank"][:5]):
        v = G[r["key"]]["vil"]
        tally[v] = tally.get(v, 0) + (5 - i)
    return [k for k, _ in sorted(tally.items(), key=lambda kv: -kv[1])]


if __name__ == "__main__":
    import random
    for form in ("mid",):
        items, content = load(form)
        picks = [random.randrange(len(it["o"])) for it in items]
        r = score(picks, form, items)
        p = render_payload(r, content)
        print(form, len(items), "문항 →", p["student"]["headline"],
              [x["name"] + str(x["score"]) for x in p["student"]["cards"]],
              "| 마을계열:", p["student"]["from_villages"][:2],
              "미수렴" if r["unresolved"] else "")
