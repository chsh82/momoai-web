# -*- coding: utf-8 -*-
"""모모 소식 라우트"""
import posixpath

from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user

from app.news import news_bp
from app.models import db
from app.models.site_content import SiteContent
from app.news.introductions_v02 import candidate_pages


@news_bp.before_app_request
def guard_intro_candidate_artwork():
    """Keep direct Flask static URLs dark along with the review candidate.

    Reverse-proxy static aliases must exclude this directory before any future
    deployment; this local Flask guard cannot control an upstream file server.
    """
    filename = posixpath.normpath((request.view_args or {}).get('filename', '').replace('\\', '/'))
    if request.endpoint == 'static' and filename.startswith('news/introductions-v02/'):
        if current_app.config.get('NEWS_INTRO_V02_ENABLED', True) is not True:
            abort(404)


def get_or_create_content(key, default_title=''):
    content = SiteContent.query.get(key)
    if not content:
        content = SiteContent(key=key, title=default_title, content='')
    return content


@news_bp.route('/')
@login_required
def hub():
    """모모 소식 허브"""
    from app.models import Post
    notices = Post.query.filter_by(category='notice').order_by(
        Post.is_pinned.desc(), Post.created_at.desc(), Post.post_id.desc()).all()
    return render_template('news/hub.html', notices=notices)


@news_bp.route('/courses')
@login_required
def courses():
    """강좌 소개"""
    content = get_or_create_content('course_intro', '강좌 소개')
    return render_template('news/courses.html', content=content, intro_pages=candidate_pages('course'))


@news_bp.route('/courses/edit', methods=['GET', 'POST'])
@login_required
def edit_courses():
    """강좌 소개 수정 (관리자만)"""
    if current_user.role != 'admin':
        abort(403)

    content = get_or_create_content('course_intro', '강좌 소개')

    if request.method == 'POST':
        content.title = request.form.get('title', '강좌 소개').strip()
        content.content = request.form.get('content', '').strip()
        content.updated_by_id = current_user.user_id

        if not SiteContent.query.get('course_intro'):
            content.key = 'course_intro'
            db.session.add(content)

        db.session.commit()
        flash('강좌 소개가 저장되었습니다.', 'success')
        return redirect(url_for('news.courses'))

    return render_template('news/edit_content.html', content=content, content_type='강좌 소개',
                           save_url=url_for('news.edit_courses'), back_url=url_for('news.courses'))


@news_bp.route('/teachers')
@login_required
def teachers():
    """강사 소개 목록"""
    from app.models import User
    teacher_list = User.query.filter_by(role='teacher', is_active=True, teacher_intro_public=True).order_by(User.name).all()
    return render_template('news/teachers.html', teacher_list=teacher_list)


@news_bp.route('/teachers/<string:teacher_id>')
@login_required
def teacher_detail(teacher_id):
    """개별 강사 소개"""
    from app.models import User
    teacher = User.query.get_or_404(teacher_id)
    if teacher.role != 'teacher':
        abort(404)
    if not teacher.teacher_intro_public and current_user.role not in ('admin', 'teacher'):
        abort(403)
    return render_template('news/teacher_detail.html', teacher=teacher)


@news_bp.route('/about')
@login_required
def about():
    """모모 소개"""
    content = get_or_create_content('about_momo', '모모 소개')
    return render_template('news/about.html', content=content, intro_pages=candidate_pages('story'))


@news_bp.route('/about/edit', methods=['GET', 'POST'])
@login_required
def edit_about():
    """모모 소개 수정 (관리자만)"""
    if current_user.role != 'admin':
        abort(403)

    content = get_or_create_content('about_momo', '모모 소개')

    if request.method == 'POST':
        content.title = request.form.get('title', '모모 소개').strip()
        content.content = request.form.get('content', '').strip()
        content.updated_by_id = current_user.user_id

        if not SiteContent.query.get('about_momo'):
            content.key = 'about_momo'
            db.session.add(content)

        db.session.commit()
        flash('모모 소개가 저장되었습니다.', 'success')
        return redirect(url_for('news.about'))

    return render_template('news/edit_content.html', content=content, content_type='모모 소개',
                           save_url=url_for('news.edit_about'), back_url=url_for('news.about'))


@news_bp.route('/my-profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    """강사 본인 소개 수정"""
    if current_user.role != 'teacher':
        abort(403)

    if request.method == 'POST':
        import json
        current_user.teacher_intro = request.form.get('teacher_intro', '').strip()
        current_user.teacher_intro_public = 'teacher_intro_public' in request.form
        selected_grades = request.form.getlist('teacher_grades')
        current_user.teacher_grades = json.dumps(selected_grades, ensure_ascii=False)
        db.session.commit()
        flash('강사 정보가 저장되었습니다.', 'success')
        return redirect(url_for('news.teacher_detail', teacher_id=current_user.user_id))

    return render_template('news/my_profile.html')
