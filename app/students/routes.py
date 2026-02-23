# -*- coding: utf-8 -*-
"""학생 관리 라우트"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.students import students_bp
from app.students.forms import StudentForm, StudentSearchForm
from app.models import db, Student
from app.utils.report_generator import ReportGenerator


@students_bp.route('/')
@login_required
def index():
    """학생 목록"""
    # 검색 폼
    search_form = StudentSearchForm(request.args, meta={'csrf': False})

    # 기본 쿼리 (관리자는 모든 학생, 강사는 자신의 학생만)
    if current_user.role in ['admin', 'manager'] or (hasattr(current_user, 'role_level') and current_user.role_level <= 2):
        # 관리자/매니저는 모든 학생 조회 (임시 학생 제외)
        query = Student.query.filter_by(is_temp=False)
    else:
        # 강사는 자신의 학생만 조회 (임시 학생 제외)
        query = Student.query.filter_by(teacher_id=current_user.user_id, is_temp=False)

    # 검색어 필터
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(Student.name.contains(search))

    # 학년 필터
    grade_filter = request.args.get('grade_filter', '').strip()
    if grade_filter:
        query = query.filter_by(grade=grade_filter)

    # 정렬 (이름순)
    students = query.order_by(Student.name).all()

    return render_template('students/index.html',
                         students=students,
                         search_form=search_form,
                         search=search,
                         grade_filter=grade_filter)


@students_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """학생 추가"""
    form = StudentForm()

    if form.validate_on_submit():
        student = Student(
            teacher_id=current_user.user_id,
            name=form.name.data,
            grade=form.grade.data,
            email=form.email.data if form.email.data else None,
            phone=form.phone.data if form.phone.data else None,
            notes=form.notes.data if form.notes.data else None
        )

        db.session.add(student)
        db.session.commit()

        flash(f'{student.name} 학생이 추가되었습니다.', 'success')
        return redirect(url_for('students.index'))

    return render_template('students/form.html',
                         form=form,
                         title='새 학생 추가',
                         is_edit=False)


@students_bp.route('/<student_id>')
@login_required
def detail(student_id):
    """학생 상세"""
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (관리자는 모든 학생, 강사는 본인의 학생만)
    is_admin = current_user.role in ['admin', 'manager'] or (hasattr(current_user, 'role_level') and current_user.role_level <= 2)
    if not is_admin and student.teacher_id != current_user.user_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('students.index'))

    # 학생의 첨삭 목록 (최신순)
    essays = student.essays[::-1] if student.essays else []

    # Phase 2: 점수 데이터 수집 (차트용)
    score_data = {
        'labels': [],  # 첨삭 날짜/제목
        'total_scores': [],  # 총점
        'has_data': False
    }

    for essay in reversed(essays):  # 오래된 순서로 정렬 (차트용)
        if essay.result and essay.result.total_score is not None:
            # 라벨: "v1 (12/01)" 형식
            label = f"v{essay.current_version}"
            if essay.created_at:
                label += f" ({essay.created_at.strftime('%m/%d')})"

            score_data['labels'].append(label)
            score_data['total_scores'].append(float(essay.result.total_score))
            score_data['has_data'] = True

    # Phase 2: 레이더 차트용 데이터 (최신 첨삭의 18개 지표)
    radar_data = {
        'thinking_types': {},
        'integrated_indicators': {},
        'has_data': False
    }

    if essays:
        # 최신 첨삭 (점수가 있는 것 중에서)
        latest_essay_with_scores = None
        for essay in essays:  # essays는 이미 최신순
            if essay.result and essay.scores:
                latest_essay_with_scores = essay
                break

        if latest_essay_with_scores:
            from app.models import EssayScore
            # 최신 버전의 점수 가져오기
            scores = EssayScore.query.filter_by(
                essay_id=latest_essay_with_scores.essay_id,
                version_id=latest_essay_with_scores.result.version_id
            ).all()

            for score in scores:
                if score.category == '사고유형':
                    radar_data['thinking_types'][score.indicator_name] = float(score.score)
                elif score.category == '통합지표':
                    radar_data['integrated_indicators'][score.indicator_name] = float(score.score)

            if radar_data['thinking_types'] or radar_data['integrated_indicators']:
                radar_data['has_data'] = True

    return render_template('students/detail.html',
                         student=student,
                         essays=essays,
                         score_data=score_data,
                         radar_data=radar_data)


@students_bp.route('/<student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(student_id):
    """학생 수정"""
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (관리자는 모든 학생, 강사는 본인의 학생만)
    is_admin = current_user.role in ['admin', 'manager'] or (hasattr(current_user, 'role_level') and current_user.role_level <= 2)
    if not is_admin and student.teacher_id != current_user.user_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('students.index'))

    form = StudentForm(obj=student)

    if form.validate_on_submit():
        student.name = form.name.data
        student.grade = form.grade.data
        student.email = form.email.data if form.email.data else None
        student.phone = form.phone.data if form.phone.data else None
        student.notes = form.notes.data if form.notes.data else None

        db.session.commit()

        flash(f'{student.name} 학생 정보가 수정되었습니다.', 'success')
        return redirect(url_for('students.detail', student_id=student.student_id))

    return render_template('students/form.html',
                         form=form,
                         title=f'{student.name} 정보 수정',
                         is_edit=True,
                         student=student)


@students_bp.route('/<student_id>/delete', methods=['POST'])
@login_required
def delete(student_id):
    """학생 삭제"""
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (관리자는 모든 학생, 강사는 본인의 학생만)
    is_admin = current_user.role in ['admin', 'manager'] or (hasattr(current_user, 'role_level') and current_user.role_level <= 2)
    if not is_admin and student.teacher_id != current_user.user_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('students.index'))

    student_name = student.name

    db.session.delete(student)
    db.session.commit()

    flash(f'{student_name} 학생이 삭제되었습니다.', 'info')
    return redirect(url_for('students.index'))


@students_bp.route('/<student_id>/report')
@login_required
def student_report(student_id):
    """학생 리포트 보기"""
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (본인 학생만 또는 관리자)
    if student.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('students.index'))

    # 기간 파라미터
    period = request.args.get('period', 'month')  # month, quarter, semester

    if period == 'month':
        start_date = datetime.utcnow() - timedelta(days=30)
        period_name = '최근 1개월'
    elif period == 'quarter':
        start_date = datetime.utcnow() - timedelta(days=90)
        period_name = '최근 3개월'
    elif period == 'semester':
        start_date = datetime.utcnow() - timedelta(days=180)
        period_name = '최근 6개월'
    else:
        start_date = datetime.utcnow() - timedelta(days=30)
        period_name = '최근 1개월'

    # 리포트 생성
    generator = ReportGenerator(student_id, start_date=start_date)
    report_data = generator.generate_report()

    return render_template('students/report.html',
                         student=student,
                         report=report_data,
                         period=period,
                         period_name=period_name)
