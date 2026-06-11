# -*- coding: utf-8 -*-
"""모모아이 분기 리포트 - 관리자/강사 라우트"""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.admin import admin_bp
from app.models import db
from app.models.essay_report import EssayReport
from app.models.payment_period import PaymentPeriod
from app.models.student import Student
from app.utils.auth_utils import requires_role


@admin_bp.route('/essay-reports')
@login_required
@requires_role('admin', 'teacher')
def essay_reports():
    """분기별 리포트 목록"""
    period_id = request.args.get('period_id')

    quarters = PaymentPeriod.query.filter_by(period_type='quarterly')\
        .order_by(PaymentPeriod.year.desc(), PaymentPeriod.period_number.desc()).all()

    selected_period = None
    reports = []
    if period_id:
        selected_period = PaymentPeriod.query.get(period_id)
        if selected_period:
            reports = EssayReport.query.filter_by(period_id=period_id)\
                .join(Student, EssayReport.student_id == Student.student_id)\
                .order_by(Student.name).all()
    elif quarters:
        # 기본: 가장 최근 분기
        selected_period = quarters[0]
        reports = EssayReport.query.filter_by(period_id=selected_period.period_id)\
            .join(Student, EssayReport.student_id == Student.student_id)\
            .order_by(Student.name).all()

    return render_template(
        'admin/essay_reports/list.html',
        quarters=quarters,
        selected_period=selected_period,
        reports=reports,
    )


@admin_bp.route('/essay-reports/generate', methods=['POST'])
@login_required
@requires_role('admin', 'teacher')
def generate_essay_reports():
    """선택한 분기의 리포트 일괄 생성"""
    from app.essays.report_generator import generate_reports_for_period

    period_id = request.form.get('period_id')
    period = PaymentPeriod.query.get_or_404(period_id)

    result = generate_reports_for_period(period)

    if result['errors']:
        flash(f"생성 완료 {result['created']}건, 오류 {len(result['errors'])}건: "
              + ', '.join(result['errors'][:3]), 'warning')
    else:
        flash(f"리포트 {result['created']}건 생성 완료 (첨삭 없음 {result['skipped']}건 건너뜀)", 'success')

    return redirect(url_for('admin.essay_reports', period_id=period_id))


@admin_bp.route('/essay-reports/<report_id>', methods=['GET', 'POST'])
@login_required
@requires_role('admin', 'teacher')
def review_essay_report(report_id):
    """리포트 검수 화면 - 강사 총평 작성 + 발행"""
    report = EssayReport.query.get_or_404(report_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_comment':
            report.teacher_comment = request.form.get('teacher_comment', '').strip()
            db.session.commit()
            flash('강사 총평이 저장되었습니다.', 'success')

        elif action == 'publish':
            report.teacher_comment = request.form.get('teacher_comment', '').strip()
            report.status = 'published'
            report.reviewed_by = current_user.user_id
            report.reviewed_at = datetime.utcnow()
            report.published_at = datetime.utcnow()
            db.session.commit()
            flash('리포트가 발행되었습니다. 학부모에게 공개됩니다.', 'success')
            return redirect(url_for('admin.essay_reports',
                                    period_id=report.period_id))

        elif action == 'unpublish':
            report.status = 'reviewing'
            report.published_at = None
            db.session.commit()
            flash('발행이 취소되었습니다.', 'info')

    return render_template('admin/essay_reports/review.html', report=report)


@admin_bp.route('/essay-reports/<report_id>/regenerate', methods=['POST'])
@login_required
@requires_role('admin', 'teacher')
def regenerate_essay_report(report_id):
    """리포트 재생성 (AI 재호출)"""
    from app.essays.report_generator import generate_report

    report = EssayReport.query.get_or_404(report_id)
    if report.status == 'published':
        flash('발행된 리포트는 재생성할 수 없습니다.', 'error')
        return redirect(url_for('admin.review_essay_report', report_id=report_id))

    try:
        generate_report(report.student, report.period)
        flash('리포트가 재생성되었습니다.', 'success')
    except Exception as e:
        flash(f'재생성 오류: {e}', 'error')

    return redirect(url_for('admin.review_essay_report', report_id=report_id))
