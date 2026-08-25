# -*- coding: utf-8 -*-
"""모모의 책장 커리큘럼 관리 라우트"""
from flask import render_template, request
from flask_login import login_required
from sqlalchemy import distinct

from app.curriculum import curriculum_bp
from app.models import db
from app.models.curriculum import CurriculumWeek
from app.utils.decorators import requires_permission_level

GRADE_CHOICES = [
    ('초1', '초등 1학년'), ('초2', '초등 2학년'), ('초3', '초등 3학년'),
    ('초4', '초등 4학년'), ('초5', '초등 5학년'), ('초6', '초등 6학년'),
    ('중1', '중등 1학년'), ('중2', '중등 2학년'), ('중3', '중등 3학년'),
    ('고1', '고등 1학년'), ('고2', '고등 2학년'), ('고3', '고등 3학년'),
]
GRADE_LABELS = dict(GRADE_CHOICES)


@curriculum_bp.route('/')
@login_required
@requires_permission_level(2)
def index():
    """연도/분기/학년별 커리큘럼 주차 목록 (매니저 이상만 접근 가능)"""
    year = request.args.get('year', type=int)
    quarter = request.args.get('quarter') or None
    grade = request.args.get('grade') or None

    query = CurriculumWeek.query
    if year:
        query = query.filter(CurriculumWeek.year == year)
    if quarter:
        query = query.filter(CurriculumWeek.quarter == quarter)
    if grade:
        query = query.filter(CurriculumWeek.grade == grade)

    weeks = query.order_by(
        CurriculumWeek.grade, CurriculumWeek.quarter, CurriculumWeek.week_number
    ).all()

    years = [r[0] for r in db.session.query(distinct(CurriculumWeek.year))
             .order_by(CurriculumWeek.year.desc()).all()]
    quarters = sorted(r[0] for r in db.session.query(distinct(CurriculumWeek.quarter)).all())

    return render_template(
        'curriculum/list.html',
        weeks=weeks,
        years=years,
        quarters=quarters,
        grade_choices=GRADE_CHOICES,
        grade_labels=GRADE_LABELS,
        filter_year=year,
        filter_quarter=quarter,
        filter_grade=grade,
        total_count=CurriculumWeek.query.count(),
    )
