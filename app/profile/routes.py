# -*- coding: utf-8 -*-
"""프로필 라우트"""
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os
import uuid

from app.profile import profile_bp
from app.profile.forms import ProfileEditForm, PasswordChangeForm
from app.models import db, User, Essay, Student, Post, Book, EssayResult


@profile_bp.route('/')
@login_required
def index():
    """프로필 페이지"""
    user = current_user

    # 기본 통계
    total_essays = Essay.query.filter_by(user_id=user.user_id).count()
    total_students = Student.query.filter_by(teacher_id=user.user_id).count()
    total_posts = Post.query.filter_by(user_id=user.user_id).count()
    total_books = Book.query.filter_by(user_id=user.user_id).count()

    # 최근 활동 (30일)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_essays = Essay.query.filter_by(user_id=user.user_id)\
        .filter(Essay.created_at >= thirty_days_ago).count()
    recent_posts = Post.query.filter_by(user_id=user.user_id)\
        .filter(Post.created_at >= thirty_days_ago).count()

    # 평균 점수
    avg_score = db.session.query(func.avg(EssayResult.total_score))\
        .join(Essay, Essay.essay_id == EssayResult.essay_id)\
        .filter(Essay.user_id == user.user_id)\
        .filter(EssayResult.total_score.isnot(None))\
        .scalar()

    # 최근 활동 내역 (최신 10개)
    recent_activities = []

    # 최근 첨삭
    recent_essay_list = Essay.query.filter_by(user_id=user.user_id)\
        .order_by(Essay.created_at.desc())\
        .limit(5).all()
    for essay in recent_essay_list:
        recent_activities.append({
            'type': 'essay',
            'icon': '📝',
            'title': f'첨삭 시작: {essay.title or essay.student.name + "의 논술"}',
            'time': essay.created_at,
            'link': url_for('essays.result', essay_id=essay.essay_id) if essay.status in ['reviewing', 'completed'] else None
        })

    # 최근 게시글
    recent_post_list = Post.query.filter_by(user_id=user.user_id)\
        .order_by(Post.created_at.desc())\
        .limit(5).all()
    for post in recent_post_list:
        recent_activities.append({
            'type': 'post',
            'icon': '💬',
            'title': f'게시글 작성: {post.title}',
            'time': post.created_at,
            'link': url_for('community.detail', post_id=post.post_id)
        })

    # 시간순 정렬
    recent_activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = recent_activities[:10]

    return render_template('profile/index.html',
                         user=user,
                         total_essays=total_essays,
                         total_students=total_students,
                         total_posts=total_posts,
                         total_books=total_books,
                         recent_essays=recent_essays,
                         recent_posts=recent_posts,
                         avg_score=avg_score,
                         recent_activities=recent_activities)


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """프로필 수정"""
    form = ProfileEditForm(obj=current_user)

    # 학생인 경우 Student 레코드 찾기
    student_record = None
    if current_user.role == 'student':
        student_record = Student.query.filter_by(user_id=current_user.user_id).first()

    # GET 요청 시 기존 데이터 로드
    if request.method == 'GET':
        form.phone.data = current_user.phone
        form.country.data = current_user.country
        form.city.data = current_user.city
        if student_record:
            form.grade.data = student_record.grade
            form.school.data = student_record.school
            form.birth_date.data = student_record.birth_date
            if student_record.country:
                form.country.data = student_record.country
            if student_record.city:
                form.city.data = student_record.city

    if form.validate_on_submit():
        # 이메일 중복 확인 (자신의 이메일 제외)
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user and existing_user.user_id != current_user.user_id:
            flash('이미 사용 중인 이메일입니다.', 'error')
            return render_template('profile/edit.html', form=form, student_record=student_record)

        # User 테이블 업데이트
        current_user.name = form.name.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data if form.phone.data else None
        current_user.country = form.country.data if form.country.data else None
        current_user.city = form.city.data if form.city.data else None

        # 학생인 경우 Student 테이블도 업데이트
        if current_user.role == 'student' and student_record:
            student_record.name = form.name.data
            student_record.email = form.email.data
            student_record.phone = form.phone.data if form.phone.data else None
            student_record.country = form.country.data if form.country.data else None
            student_record.city = form.city.data if form.city.data else None

            if form.grade.data:
                student_record.grade = form.grade.data
            if form.school.data:
                student_record.school = form.school.data
            if form.birth_date.data:
                student_record.birth_date = form.birth_date.data

        # 학부모인 경우 연결된 자녀에게 거주 정보 동기화
        if current_user.role == 'parent':
            from app.models.parent_student import ParentStudent
            new_country = form.country.data if form.country.data else None
            new_city = form.city.data if form.city.data else None
            if new_country or new_city:
                parent_links = ParentStudent.query.filter_by(
                    parent_id=current_user.user_id, is_active=True
                ).all()
                for ps in parent_links:
                    child_student = Student.query.get(ps.student_id)
                    if child_student:
                        child_student.country = new_country
                        child_student.city = new_city
                        if child_student.user_id:
                            child_user = User.query.filter_by(user_id=child_student.user_id).first()
                            if child_user:
                                child_user.country = new_country
                                child_user.city = new_city

        # 프로필 이미지 업로드 처리
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename:
                # 업로드 폴더 생성
                upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
                os.makedirs(upload_folder, exist_ok=True)

                # 안전한 파일명 생성
                original_filename = secure_filename(file.filename)
                file_ext = os.path.splitext(original_filename)[1]
                stored_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(upload_folder, stored_filename)

                # 파일 저장
                file.save(file_path)

                # DB에 정보 저장
                current_user.profile_image_filename = original_filename
                current_user.profile_image_path = os.path.join('profiles', stored_filename)

        db.session.commit()

        flash('프로필이 수정되었습니다.', 'success')
        return redirect(url_for('profile.index'))

    return render_template('profile/edit.html', form=form, student_record=student_record)


@profile_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """비밀번호 변경"""
    form = PasswordChangeForm()

    if form.validate_on_submit():
        # 현재 비밀번호 확인
        if not current_user.check_password(form.current_password.data):
            flash('현재 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('profile/change_password.html', form=form)

        # 새 비밀번호 설정
        current_user.set_password(form.new_password.data)
        db.session.commit()

        flash('비밀번호가 변경되었습니다.', 'success')
        return redirect(url_for('profile.index'))

    return render_template('profile/change_password.html', form=form)


@profile_bp.route('/image/<user_id>')
@login_required
def profile_image(user_id):
    """프로필 이미지 다운로드"""
    user = User.query.get_or_404(user_id)

    if not user.profile_image_path:
        # 기본 이미지 반환 또는 404
        flash('프로필 이미지가 없습니다.', 'error')
        return redirect(url_for('profile.index'))

    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_directory = os.path.dirname(os.path.join(upload_folder, user.profile_image_path))
        file_name = os.path.basename(user.profile_image_path)

        return send_from_directory(
            file_directory,
            file_name,
            as_attachment=False  # 브라우저에서 바로 표시
        )
    except Exception as e:
        flash(f'이미지를 불러올 수 없습니다: {str(e)}', 'error')
        return redirect(url_for('profile.index'))
