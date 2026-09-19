# -*- coding: utf-8 -*-
"""초등 공부력 테스트 라우트.

지정된 신버전 원본(sources/elementary-study/current.html, 32문항)은
핸드오프 패키지에 파일 자체가 없어(매니페스트에 해시만 등록, 실물 누락)
쓸 수 없다. 사용자 확인 하에 같은 패키지 안에 보존돼 있던 구버전
초등 5~6학년 폼(app/sources/middle_study/items.json 의 "elem", 33문항)을
임시로 그대로 사용한다. 문항·채점 로직은 손대지 않았고, study_mid와
같은 엔진(app/sources/middle_study/scoring.py)을 grade='elem'으로
호출하는 차이뿐이다. 저장은 세션에만 하며 DB에는 남기지 않는다.
"""
from flask import render_template, request, session, redirect, url_for, flash

from app.study_elem import study_elem_bp
from app.sources.middle_study import scoring as engine
from app.utils.decorators import requires_role

GRADE = 'elem'
RESPONDENT = 'student'
SESSION_KEY = 'study_elem_result'


def _form():
    items_json, content = engine.load()
    form = engine.build_form(GRADE, RESPONDENT, items_json, content)
    return form, content


@study_elem_bp.route('/')
@requires_role('admin')
def index():
    """초등 공부력 테스트 - 시작 화면."""
    form, content = _form()
    return render_template('study_elem/index.html', item_count=len(form['items']),
                            meta=content.get('meta'))


@study_elem_bp.route('/quiz')
@requires_role('admin')
def quiz():
    """33문항(고정 배열 순서) 응답 화면 - 한 화면에 전부 표시 후 일괄 제출."""
    form, content = _form()
    scales = content['scales']
    lead = content.get('lead', {})
    items = []
    for i, q in enumerate(form['items']):
        prefix = lead.get(str(q['lead']), '') if q.get('lead') else ''
        items.append({
            'index': i,
            'text': prefix + q['t'],
            'options': scales[q['s']],
        })
    return render_template('study_elem/quiz.html', items=items, item_count=len(items))


@study_elem_bp.route('/submit', methods=['POST'])
@requires_role('admin')
def submit():
    form, content = _form()
    item_count = len(form['items'])
    answers = []
    for i in range(item_count):
        raw = request.form.get(f'q{i}')
        if raw is None:
            flash(f'{i + 1}번 문항에 응답하지 않았습니다.', 'error')
            return redirect(url_for('study_elem.quiz'))
        answers.append(int(raw))

    result = engine.score(answers, form, RESPONDENT)
    level = engine.level_info(result['level'], content)
    session[SESSION_KEY] = {'result': result, 'level': level, 'answers': answers}
    return redirect(url_for('study_elem.result'))


def _result_context():
    data = session.get(SESSION_KEY)
    if not data:
        return None
    _, content = engine.load()
    element_meta = {e['k']: e for e in content['elements'][GRADE]}
    weak_meta = element_meta.get(data['result']['weak_key']) if data['result']['weak_key'] else None
    return {
        'result': data['result'],
        'level': data['level'],
        'element_meta': element_meta,
        'weak_meta': weak_meta,
    }


@study_elem_bp.route('/result')
@requires_role('admin')
def result():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('study_elem.index'))
    return render_template('study_elem/result.html', **ctx)


@study_elem_bp.route('/print')
@requires_role('admin')
def print_view():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('study_elem.index'))
    return render_template('study_elem/print.html', **ctx)
