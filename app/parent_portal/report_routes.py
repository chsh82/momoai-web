# -*- coding: utf-8 -*-
"""모모아이 분기 리포트 - 학부모 라우트"""
import io
from flask import render_template, abort, make_response, current_app
from flask_login import login_required, current_user

from app.parent_portal import parent_bp
from app.models import db
from app.models.essay_report import EssayReport
from app.models.parent_student import ParentStudent
from app.utils.auth_utils import requires_role


def _get_child_ids(parent_id):
    rels = ParentStudent.query.filter_by(parent_id=parent_id, is_active=True).all()
    return [r.student_id for r in rels if r.student_id]


@parent_bp.route('/essay-reports')
@login_required
@requires_role('parent')
def essay_reports():
    """자녀별 발행된 리포트 목록"""
    child_ids = _get_child_ids(current_user.user_id)
    reports = EssayReport.query\
        .filter(
            EssayReport.student_id.in_(child_ids),
            EssayReport.status == 'published'
        )\
        .order_by(EssayReport.published_at.desc()).all()

    # 자녀별 그룹
    reports_by_child = {}
    for r in reports:
        name = r.student.name
        reports_by_child.setdefault(name, []).append(r)

    return render_template(
        'parent/essay_reports/list.html',
        reports_by_child=reports_by_child,
    )


@parent_bp.route('/essay-reports/<report_id>')
@login_required
@requires_role('parent')
def view_essay_report(report_id):
    """리포트 상세 조회"""
    report = EssayReport.query.get_or_404(report_id)

    child_ids = _get_child_ids(current_user.user_id)
    if report.student_id not in child_ids or report.status != 'published':
        abort(403)

    return render_template('parent/essay_reports/detail.html', report=report)


@parent_bp.route('/essay-reports/<report_id>/pdf')
@login_required
@requires_role('parent')
def download_essay_report_pdf(report_id):
    """리포트 PDF 다운로드"""
    report = EssayReport.query.get_or_404(report_id)

    child_ids = _get_child_ids(current_user.user_id)
    if report.student_id not in child_ids or report.status != 'published':
        abort(403)

    try:
        from xhtml2pdf import pisa

        html_str = render_template('parent/essay_reports/pdf.html', report=report)
        buf = io.BytesIO()
        pisa.CreatePDF(io.StringIO(html_str), dest=buf, encoding='utf-8')
        buf.seek(0)

        filename = (
            f"모모아이분기리포트_{report.student.name}"
            f"_{report.period.label.replace(' ', '')}.pdf"
        )
        response = make_response(buf.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = \
            f'attachment; filename*=UTF-8\'\'{filename}'
        return response

    except Exception as e:
        current_app.logger.error(f'PDF 생성 오류: {e}')
        from flask import flash, redirect, url_for
        flash('PDF 생성 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('parent.view_essay_report', report_id=report_id))
