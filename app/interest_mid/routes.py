# -*- coding: utf-8 -*-
"""중등 전공 나침반 라우트.

문항은행(items.json)·채점엔진(scoring.py)은 app/sources/middle_compass/에
원본 그대로 두고 여기서는 화면(질문/결과/인쇄)만 붙인다. 중등 학생용
40문항 폼만 다룬다. 저장은 세션에만 하며 DB에는 남기지 않는다 - 아직
학생 출시 게이트로 제한하며 momoai_web 데이터 모델과 연동하지 않는다.
"""
from flask import render_template, request, session, redirect, url_for, flash, abort
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.interest_mid import interest_mid_bp
from app.sources.middle_compass import scoring as engine
from app.utils.student_launch import student_launch_required

FORM = 'mid'
SESSION_KEY = 'interest_mid_result'


@interest_mid_bp.route('/')
@student_launch_required('STUDENT_INTEREST_MID_ENABLED')
def index():
    """중등 전공 나침반 - 시작 화면."""
    items, _ = engine.load(FORM)
    return render_template('interest_mid/index.html', item_count=len(items))


@interest_mid_bp.route('/quiz')
@student_launch_required('STUDENT_INTEREST_MID_ENABLED')
def quiz():
    """40문항(원본 순서)의 5문항 단위 화면. 마지막에 전체를 검증·제출."""
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
@student_launch_required('STUDENT_INTEREST_MID_ENABLED')
def submit():
    # This application generates CSRF tokens but has no global CSRFProtect.
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    items, content = engine.load(FORM)
    answers = []
    for i, q in enumerate(items):
        raw = request.form.get(f'q{i}')
        if raw is None:
            flash(f'{i + 1}번 문항에 응답하지 않았습니다.', 'error')
            return redirect(url_for('interest_mid.quiz'))
        try:
            pick = int(raw)
        except (ValueError, TypeError):
            flash(f'{i + 1}번 문항 응답값이 올바르지 않습니다.', 'error')
            return redirect(url_for('interest_mid.quiz'))
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
@student_launch_required('STUDENT_INTEREST_MID_ENABLED')
def result():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('interest_mid.index'))
    return render_template('interest_mid/result.html', **ctx)


@interest_mid_bp.route('/print')
@student_launch_required('STUDENT_INTEREST_MID_ENABLED')
def print_view():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('interest_mid.index'))
    return render_template('interest_mid/print.html', **ctx)
