# -*- coding: utf-8 -*-
"""중등 전공 나침반 라우트.

문항은행(items.json)·채점엔진(scoring.py)은 app/sources/middle_compass/에
원본 그대로 두고 여기서는 화면(질문/결과/인쇄)만 붙인다. 중등 학생용
40문항 폼만 다룬다. 저장은 세션에만 하며 DB에는 남기지 않는다 - 아직
관리자 검토 단계라 momoai_web 데이터 모델과 연동하지 않는다.
"""
from flask import render_template, request, session, redirect, url_for, flash

from app.interest_mid import interest_mid_bp
from app.sources.middle_compass import scoring as engine
from app.utils.decorators import requires_role

FORM = 'mid'
SESSION_KEY = 'interest_mid_result'


@interest_mid_bp.route('/')
@requires_role('admin')
def index():
    """중등 전공 나침반 - 시작 화면."""
    items, _ = engine.load(FORM)
    return render_template('interest_mid/index.html', item_count=len(items))


@interest_mid_bp.route('/quiz')
@requires_role('admin')
def quiz():
    """40문항(문항은행 순서 그대로) 응답 화면 - 한 화면에 전부 표시 후 일괄 제출."""
    items, _ = engine.load(FORM)
    view_items = []
    for i, q in enumerate(items):
        view_items.append({
            'index': i,
            'prefix': q.get('p', ''),
            'question': q['q'],
            'options': [o['t'] for o in q['o']],
        })
    return render_template('interest_mid/quiz.html', items=view_items, item_count=len(items))


@interest_mid_bp.route('/submit', methods=['POST'])
@requires_role('admin')
def submit():
    items, content = engine.load(FORM)
    answers = []
    for i, q in enumerate(items):
        raw = request.form.get(f'q{i}')
        if raw is None:
            flash(f'{i + 1}번 문항에 응답하지 않았습니다.', 'error')
            return redirect(url_for('interest_mid.quiz'))
        pick = int(raw)
        if not (0 <= pick < len(q['o'])):
            flash(f'{i + 1}번 문항 응답값이 올바르지 않습니다.', 'error')
            return redirect(url_for('interest_mid.quiz'))
        answers.append(pick)

    result = engine.score(answers, FORM, items)
    payload = engine.render_payload(result, content)
    session[SESSION_KEY] = {'payload': payload, 'answers': answers}
    return redirect(url_for('interest_mid.result'))


def _result_context():
    data = session.get(SESSION_KEY)
    if not data:
        return None
    _, content = engine.load(FORM)
    student = data['payload']['student']
    axes = [
        {**axis, 'left_label': meta['l'][0], 'right_label': meta['l'][1]}
        for axis, meta in zip(student['axes'], content['axes'])
    ]
    return {'student': student, 'axes': axes}


@interest_mid_bp.route('/result')
@requires_role('admin')
def result():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('interest_mid.index'))
    return render_template('interest_mid/result.html', **ctx)


@interest_mid_bp.route('/print')
@requires_role('admin')
def print_view():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('interest_mid.index'))
    return render_template('interest_mid/print.html', **ctx)
