# -*- coding: utf-8 -*-
"""course1.json이 build_elem.py의 RULES 원문과 일치하는지 자동 검증한다.

docs/tutorial/prompt_0_콘텐츠추출.md의 "검증" 절을 그대로 코드로 옮긴 것 -
카드 4장 / 문항 4개 수, say/why 문자 단위 일치, remember/note 키가
원문에 있을 때만 존재하는지, 원고지 표기법(!/#/{}) 보존, 문항4 오답이
!.가 아니라 #.인지까지 전부 확인한다.

사용법: python check_course1.py <course1.json 경로> <build_elem.py 경로>
"""
import json
import re
import sys


def load_rules(build_elem_path):
    src = open(build_elem_path, encoding='utf-8').read()
    m = re.search(r'^RULES = \[.*?\n\]\n', src, re.S | re.M)
    if not m:
        raise RuntimeError(f'{build_elem_path}에서 RULES 리스트를 찾지 못했습니다')
    # gp.py 의존성을 피하려고 grid/ex는 임포트하지 않고, RULES 리터럴 안에서
    # 실제로 쓰이는 문자열 상수(Q1/Q2/EL)만 값을 채워 넣고 이 블록만 단독 실행한다.
    ns = {'Q1': '“', 'Q2': '”', 'EL': '…'}
    exec(m.group(0), ns)
    return {r['no']: r for r in ns['RULES']}


def main():
    if len(sys.argv) != 3:
        print('사용법: python check_course1.py <course1.json> <build_elem.py>')
        return 1

    course_path, build_elem_path = sys.argv[1], sys.argv[2]
    failures = []

    def fail(msg):
        failures.append(msg)

    by_no = load_rules(build_elem_path)
    data = json.load(open(course_path, encoding='utf-8'))

    lesson = data['lessons'][0]
    cards = lesson['cards']
    questions = lesson['questions']

    # 1) 카드 4장 / 문항 4개
    if len(cards) != 4:
        fail(f'카드 개수가 4가 아님: {len(cards)}')
    if len(questions) != 4:
        fail(f'문항 개수가 4가 아님: {len(questions)}')

    expected_card_nos = ['2', '5', '6', '10']
    card_by_no = {c['no']: c for c in cards}
    if [c['no'] for c in cards] != expected_card_nos:
        fail(f'카드 순서/구성이 다름: {[c["no"] for c in cards]} (기대: {expected_card_nos})')

    # 2) 카드별 원문 대조
    for no in expected_card_nos:
        if no not in card_by_no:
            fail(f'카드 no={no} 없음')
            continue
        c = card_by_no[no]
        r = by_no.get(no)
        if r is None:
            fail(f'RULES에 no={no} 없음 (build_elem.py 확인 필요)')
            continue

        # say/why 문자 단위 일치
        if c.get('say') != r.get('say'):
            fail(f'[no={no}] say가 RULES 원문과 다름: {c.get("say")!r} != {r.get("say")!r}')
        if c.get('why') != r.get('why'):
            fail(f'[no={no}] why가 RULES 원문과 다름: {c.get("why")!r} != {r.get("why")!r}')
        if c.get('title') != r.get('title'):
            fail(f'[no={no}] title이 RULES 원문과 다름: {c.get("title")!r} != {r.get("title")!r}')

        # star: 없으면 false
        expected_star = r.get('star', False)
        if c.get('star') != expected_star:
            fail(f'[no={no}] star 불일치: {c.get("star")} != {expected_star}')

        # remember: try_가 있을 때만 존재
        has_try = 'try_' in r
        has_remember = 'remember' in c
        if has_try and not has_remember:
            fail(f'[no={no}] RULES에 try_가 있는데 remember 키가 없음')
        elif not has_try and has_remember:
            fail(f'[no={no}] RULES에 try_가 없는데 remember 키가 있음(원문에 없는 필드 생성 금지): {c.get("remember")!r}')
        elif has_try and c.get('remember') != r['try_']:
            fail(f'[no={no}] remember가 try_ 원문과 다름: {c.get("remember")!r} != {r["try_"]!r}')

        # note: RULES에 있을 때만 존재
        has_note = 'note' in r
        has_card_note = 'note' in c
        if has_note and not has_card_note:
            fail(f'[no={no}] RULES에 note가 있는데 카드에 note 키가 없음')
        elif not has_note and has_card_note:
            fail(f'[no={no}] RULES에 note가 없는데 카드에 note 키가 있음: {c.get("note")!r}')
        elif has_note and c.get('note') != r['note']:
            fail(f'[no={no}] note가 원문과 다름: {c.get("note")!r} != {r["note"]!r}')

        # 카드 최상위 키는 category (tag 아님), grids[].tag는 그대로
        if 'tag' in c:
            fail(f'[no={no}] 카드 최상위에 tag 키가 남아있음(category로 바꿔야 함)')
        if c.get('category') != '관행':
            fail(f'[no={no}] category가 "관행"이 아님: {c.get("category")!r}')

        # grids: bad/good 존재 여부와 rows/tag/n이 원문과 일치
        has_bad, has_good = 'bad' in r, 'good' in r
        grids = c.get('grids', [])
        tones = [g.get('tone') for g in grids]
        if has_bad and 'bad' not in tones:
            fail(f'[no={no}] RULES에 bad가 있는데 grids에 bad가 없음')
        if not has_bad and 'bad' in tones:
            fail(f'[no={no}] RULES에 bad가 없는데 grids에 bad가 있음(빈 bad 생성 금지)')
        if has_good and 'good' not in tones:
            fail(f'[no={no}] RULES에 good이 있는데 grids에 good이 없음')

        for g in grids:
            tone = g.get('tone')
            src_rows = r.get(tone)
            src_cap = r.get(f'{tone}_cap')
            src_n = r.get('n')
            if g.get('rows') != src_rows:
                fail(f'[no={no}/{tone}] rows가 원문과 다름: {g.get("rows")!r} != {src_rows!r}')
            if g.get('tag') != src_cap:
                fail(f'[no={no}/{tone}] tag(캡션)가 원문과 다름: {g.get("tag")!r} != {src_cap!r}')
            expected_n = src_n if src_n is not None else None
            if g.get('n') != expected_n:
                fail(f'[no={no}/{tone}] n이 원문과 다름: {g.get("n")!r} != {expected_n!r} '
                     f'(원문에 n 없으면 null이어야 함)')

    # 3) 문항 id 순서
    expected_qids = ['elem-c1-l1-q1', 'elem-c1-l1-q2', 'elem-c1-l1-q3', 'elem-c1-l1-q4']
    actual_qids = [q.get('id') for q in questions]
    if actual_qids != expected_qids:
        fail(f'문항 id가 기대와 다름: {actual_qids} != {expected_qids}')

    # 4) 문항4 오답 보기는 !.가 아니라 #.
    q4 = next((q for q in questions if q.get('id') == 'elem-c1-l1-q4'), None)
    if q4 is None:
        fail('문항 elem-c1-l1-q4를 찾지 못함')
    else:
        wrong_opt = q4['opts'][0]['rows']
        if wrong_opt != ['해법은 달라요', '#.']:
            fail(f'문항4 오답 보기가 기대와 다름: {wrong_opt!r} != {["해법은 달라요", "#."]!r}')
        if '!.' in wrong_opt:
            fail('문항4 오답 보기에 !.가 남아있음(#.여야 함 - 오답 그림이 정답처럼 보이는 버그)')

    # 5) 원고지 표기법 보존 확인 (대표 샘플 몇 개)
    notation_checks = [
        (card_by_no['2']['grids'][1]['rows'][0], '!{ }', 'no=2 good grid'),
        (card_by_no['6']['grids'][0]['rows'][0], '!2!0!2!6', 'no=6 bad grid'),
        (card_by_no['6']['grids'][1]['rows'][0], '!{20}!{26}', 'no=6 good grid'),
        (card_by_no['10']['grids'][1]['rows'][0], '!{요.}', 'no=10 good grid'),
    ]
    for text, needle, label in notation_checks:
        if needle not in text:
            fail(f'원고지 표기법 유실: {label}에 {needle!r}가 없음 (실제: {text!r})')

    print(f'검사 항목: 카드 4장 대조, 문항 id/오답표기, 원고지 표기법 보존')
    print(f'실패: {len(failures)}건')
    for f in failures:
        print(f'  - {f}')

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
