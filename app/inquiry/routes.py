# -*- coding: utf-8 -*-
"""문의 게시판 라우트"""
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.inquiry import inquiry_bp
from app.models import db, User, ParentStudent, Student, CourseEnrollment
from app.models.inquiry import InquiryPost, InquiryReply


def _get_children_teachers(parent_id):
    """학부모의 자녀가 수강 중인 강사 목록 반환"""
    children = db.session.query(Student).join(
        ParentStudent, ParentStudent.student_id == Student.student_id
    ).filter(ParentStudent.parent_id == parent_id).all()

    teachers_map = {}  # teacher_id -> {'user': User, 'course_names': [str]}
    for child in children:
        enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id, status='active'
        ).all()
        for enr in enrollments:
            course = enr.course
            if course and course.teacher_id and course.teacher:
                tid = course.teacher_id
                if tid not in teachers_map:
                    teachers_map[tid] = {
                        'user': course.teacher,
                        'course_names': []
                    }
                teachers_map[tid]['course_names'].append(course.name)

    return list(teachers_map.values())


@inquiry_bp.route('/')
@login_required
def index():
    """문의 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    if current_user.role == 'admin':
        # 관리자: 전체 조회
        status_filter = request.args.get('status', '')
        query = InquiryPost.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        pagination = query.order_by(InquiryPost.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        pending_count = InquiryPost.query.filter_by(status='pending').count()

    elif current_user.role == 'teacher':
        # 강사: 자신에게 온 문의만
        status_filter = request.args.get('status', '')
        query = InquiryPost.query.filter_by(recipient_id=current_user.user_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        pagination = query.order_by(InquiryPost.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        pending_count = InquiryPost.query.filter_by(
            recipient_id=current_user.user_id, status='pending').count()

    else:
        # 학부모/학생: 본인 글만
        pagination = InquiryPost.query.filter_by(author_id=current_user.user_id).order_by(
            InquiryPost.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        status_filter = ''
        pending_count = 0

    return render_template('inquiry/index.html',
                           pagination=pagination,
                           status_filter=status_filter,
                           pending_count=pending_count)


@inquiry_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_inquiry():
    """문의 작성 (학부모/학생만)"""
    if current_user.role not in ('parent', 'student'):
        flash('문의 작성은 학부모/학생만 가능합니다.', 'warning')
        return redirect(url_for('inquiry.index'))

    # 자녀의 담당 강사 목록
    teachers_data = _get_children_teachers(current_user.user_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_private = 'is_private' in request.form
        recipient_type = request.form.get('recipient_type', 'admin')
        recipient_id = None

        if recipient_type == 'teacher':
            recipient_id = request.form.get('recipient_id', '').strip() or None
            if not recipient_id:
                flash('수신 강사를 선택해주세요.', 'danger')
                return render_template('inquiry/new.html',
                                       title_val=title, content_val=content,
                                       teachers_data=teachers_data)

        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('inquiry/new.html',
                                   title_val=title, content_val=content,
                                   teachers_data=teachers_data)

        post = InquiryPost(
            author_id=current_user.user_id,
            title=title,
            content=content,
            is_private=is_private,
            recipient_id=recipient_id
        )
        db.session.add(post)
        db.session.commit()

        flash('문의가 등록되었습니다. 빠른 시일 내에 답변드리겠습니다.', 'success')
        return redirect(url_for('inquiry.detail', inquiry_id=post.inquiry_id))

    return render_template('inquiry/new.html',
                           title_val='', content_val='',
                           teachers_data=teachers_data)


@inquiry_bp.route('/<string:inquiry_id>')
@login_required
def detail(inquiry_id):
    """문의 상세"""
    post = InquiryPost.query.get_or_404(inquiry_id)

    # 비공개 글: 작성자 또는 담당 수신자(강사/관리자)만 열람
    if post.is_private:
        is_author = current_user.user_id == post.author_id
        is_recipient = (current_user.role == 'admin' or
                        current_user.user_id == post.recipient_id)
        if not is_author and not is_recipient:
            abort(403)

    # 강사는 자신에게 온 문의만 열람
    if current_user.role == 'teacher' and post.recipient_id != current_user.user_id:
        abort(403)

    return render_template('inquiry/detail.html', post=post)


@inquiry_bp.route('/<string:inquiry_id>/reply', methods=['POST'])
@login_required
def reply(inquiry_id):
    """답변 작성 (관리자/강사만)"""
    post = InquiryPost.query.get_or_404(inquiry_id)

    # 강사는 자신에게 온 문의만 답변 가능
    if current_user.role == 'teacher':
        if post.recipient_id != current_user.user_id:
            abort(403)
    elif current_user.role != 'admin':
        abort(403)

    content = request.form.get('content', '').strip()
    if not content:
        flash('답변 내용을 입력해주세요.', 'danger')
        return redirect(url_for('inquiry.detail', inquiry_id=inquiry_id))

    reply_obj = InquiryReply(
        inquiry_id=inquiry_id,
        author_id=current_user.user_id,
        content=content
    )
    db.session.add(reply_obj)
    post.status = 'answered'
    db.session.commit()

    flash('답변이 등록되었습니다.', 'success')
    return redirect(url_for('inquiry.detail', inquiry_id=inquiry_id))


@inquiry_bp.route('/<string:inquiry_id>/delete', methods=['POST'])
@login_required
def delete_inquiry(inquiry_id):
    """문의 삭제 (작성자 또는 관리자)"""
    post = InquiryPost.query.get_or_404(inquiry_id)

    if current_user.user_id != post.author_id and current_user.role != 'admin':
        abort(403)

    db.session.delete(post)
    db.session.commit()

    flash('문의가 삭제되었습니다.', 'success')
    return redirect(url_for('inquiry.index'))
