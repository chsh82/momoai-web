# -*- coding: utf-8 -*-
"""중등 공부력 테스트 라우트.

문항은행(items.json)·채점엔진(scoring.py)은 app/sources/middle_study/에
원본 그대로 두고 여기서는 화면(질문/결과/인쇄)만 붙인다. 중등 학생용
폼만 다룬다(학부모용 폼은 이번 범위 밖). 저장은 세션에만 하며 DB에는
남기지 않는다 - 아직 관리자 검토 단계라 momoai_web 데이터 모델과
연동하지 않는다.
"""
from flask import render_template, request, session, redirect, url_for, flash

from app.study_mid import study_mid_bp
from app.sources.middle_study import scoring as engine
from app.utils.decorators import requires_role

GRADE = 'mid'
RESPONDENT = 'student'
SESSION_KEY = 'study_mid_result'


def _form():
    items_json, content = engine.load()
    form = engine.build_form(GRADE, RESPONDENT, items_json, content)
    return form, content


@study_mid_bp.route('/')
@requires_role('admin')
def index():
    """중등 공부력 테스트 - 시작 화면."""
    _, content = engine.load()
    form, _ = _form()
    return render_template('study_mid/index.html', item_count=len(form['items']),
                            meta=content.get('meta'))


@study_mid_bp.route('/quiz')
@requires_role('admin')
def quiz():
    """52문항(고정 배열 순서) 응답 화면 - 한 화면에 전부 표시 후 일괄 제출."""
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
    return render_template('study_mid/quiz.html', items=items, item_count=len(items))


@study_mid_bp.route('/submit', methods=['POST'])
@requires_role('admin')
def submit():
    form, content = _form()
    item_count = len(form['items'])
    answers = []
    for i in range(item_count):
        raw = request.form.get(f'q{i}')
        if raw is None:
            flash(f'{i + 1}번 문항에 응답하지 않았습니다.', 'error')
            return redirect(url_for('study_mid.quiz'))
        answers.append(int(raw))

    result = engine.score(answers, form, RESPONDENT)
    level = engine.level_info(result['level'], content)
    session[SESSION_KEY] = {'result': result, 'level': level, 'answers': answers}
    return redirect(url_for('study_mid.result'))


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


@study_mid_bp.route('/result')
@requires_role('admin')
def result():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('study_mid.index'))
    return render_template('study_mid/result.html', **ctx)


@study_mid_bp.route('/print')
@requires_role('admin')
def print_view():
    ctx = _result_context()
    if not ctx:
        flash('먼저 검사를 진행해 주세요.', 'error')
        return redirect(url_for('study_mid.index'))
    return render_template('study_mid/print.html', **ctx)
