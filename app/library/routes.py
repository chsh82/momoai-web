# -*- coding: utf-8 -*-
"""도서 자료실 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
import uuid
import os

from app.library import library_bp
from app.models import db, Book, Video, Student
from app.models.library import HallOfFame, AdmissionInfo
from app.utils.decorators import requires_permission_level


# ==================== 유틸리티 함수 ====================

def extract_youtube_video_id(url):
    """Extract video ID from YouTube URL"""
    import re
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ==================== 메인 페이지 ====================

@library_bp.route('/')
@login_required
def index():
    """도서 자료실 메인 페이지"""
    # 최신 유튜브 영상 4개
    latest_videos = Video.query.filter_by(is_public=True).order_by(
        Video.created_at.desc()
    ).limit(4).all()

    # 추천도서 4개
    recommended_books = Book.query.order_by(Book.created_at.desc()).limit(4).all()

    # 명예의 전당 최신 3개
    hall_of_fame_posts = HallOfFame.query.filter_by(is_published=True).order_by(
        HallOfFame.created_at.desc()
    ).limit(3).all()

    # 입시정보 최신 3개 (공개 기간 내)
    today = date.today()
    admission_posts = AdmissionInfo.query.filter(
        db.or_(
            AdmissionInfo.publish_date == None,
            db.and_(
                AdmissionInfo.publish_date <= today,
                db.or_(
                    AdmissionInfo.expire_date == None,
                    AdmissionInfo.expire_date >= today
                )
            )
        )
    ).order_by(
        AdmissionInfo.is_important.desc(),
        AdmissionInfo.created_at.desc()
    ).limit(3).all()

    return render_template('library/index.html',
                         latest_videos=latest_videos,
                         recommended_books=recommended_books,
                         hall_of_fame_posts=hall_of_fame_posts,
                         admission_posts=admission_posts)


# ==================== 유튜브 영상 ====================

@library_bp.route('/videos')
@login_required
def videos():
    """유튜브 영상 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    videos = Video.query.filter_by(is_public=True).order_by(
        Video.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('library/videos.html',
                         videos=videos)


@library_bp.route('/videos/<video_id>')
@login_required
def video_detail(video_id):
    """유튜브 영상 상세"""
    video = Video.query.get_or_404(video_id)

    # 조회수 증가
    video.view_count += 1
    db.session.commit()

    return render_template('library/video_detail.html',
                         video=video)


# ==================== 추천도서 ====================

@library_bp.route('/books')
@login_required
def books():
    """추천도서 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    books = Book.query.order_by(Book.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('library/books.html',
                         books=books)


@library_bp.route('/books/<book_id>')
@login_required
def book_detail(book_id):
    """추천도서 상세"""
    book = Book.query.get_or_404(book_id)

    return render_template('library/book_detail.html',
                         book=book)


# ==================== 명예의 전당 ====================

@library_bp.route('/hall-of-fame')
@login_required
def hall_of_fame():
    """명예의 전당 목록"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    per_page = 20

    query = HallOfFame.query.filter_by(is_published=True)

    if category:
        query = query.filter_by(category=category)

    posts = query.order_by(HallOfFame.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('library/hall_of_fame.html',
                         posts=posts,
                         current_category=category)


@library_bp.route('/hall-of-fame/<post_id>')
@login_required
def hall_of_fame_detail(post_id):
    """명예의 전당 상세"""
    post = HallOfFame.query.get_or_404(post_id)

    if not post.is_published and not current_user.is_admin:
        flash('공개되지 않은 게시글입니다.', 'error')
        return redirect(url_for('library.hall_of_fame'))

    # 조회수 증가
    post.view_count += 1
    db.session.commit()

    return render_template('library/hall_of_fame_detail.html',
                         post=post)


# ==================== 입시정보 ====================

@library_bp.route('/admission-info')
@login_required
def admission_info():
    """입시정보 목록"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    per_page = 20

    today = date.today()
    query = AdmissionInfo.query.filter(
        db.or_(
            AdmissionInfo.publish_date == None,
            db.and_(
                AdmissionInfo.publish_date <= today,
                db.or_(
                    AdmissionInfo.expire_date == None,
                    AdmissionInfo.expire_date >= today
                )
            )
        )
    )

    if category:
        query = query.filter_by(category=category)

    posts = query.order_by(
        AdmissionInfo.is_important.desc(),
        AdmissionInfo.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('library/admission_info.html',
                         posts=posts,
                         current_category=category)


@library_bp.route('/admission-info/<post_id>')
@login_required
def admission_info_detail(post_id):
    """입시정보 상세"""
    post = AdmissionInfo.query.get_or_404(post_id)

    # 공개 기간 확인
    if not post.is_active() and not current_user.is_admin:
        flash('공개 기간이 아닌 게시글입니다.', 'error')
        return redirect(url_for('library.admission_info'))

    # 조회수 증가
    post.view_count += 1
    db.session.commit()

    return render_template('library/admission_info_detail.html',
                         post=post)


# ==================== 관리자 전용 ====================

# 유튜브 영상 관리
@library_bp.route('/admin/videos/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_video():
    """영상 등록"""
    if request.method == 'POST':
        try:
            # Extract YouTube video ID
            youtube_url = request.form.get('youtube_url')
            youtube_video_id = extract_youtube_video_id(youtube_url)

            # Parse dates
            publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

            # Create video with basic target_audience (all grades)
            video = Video(
                video_id=str(uuid.uuid4()),
                title=request.form.get('title'),
                description=request.form.get('description') or None,
                grade=request.form.get('grade'),
                youtube_url=youtube_url,
                youtube_video_id=youtube_video_id,
                publish_date=publish_date,
                end_date=end_date,
                is_public=bool(request.form.get('is_public')),
                target_audience='{"type": "grade", "grades": []}',  # Empty = all grades
                created_by=current_user.user_id
            )

            db.session.add(video)
            db.session.commit()

            flash('영상이 등록되었습니다.', 'success')
            return redirect(url_for('library.video_detail', video_id=video.video_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/video_form.html', video=None)


@library_bp.route('/admin/videos/<video_id>/edit', methods=['GET', 'POST'])
@requires_permission_level(2)
def edit_video(video_id):
    """영상 수정"""
    video = Video.query.get_or_404(video_id)

    if request.method == 'POST':
        try:
            # Extract YouTube video ID
            youtube_url = request.form.get('youtube_url')
            youtube_video_id = extract_youtube_video_id(youtube_url)

            # Parse dates
            publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

            # Update video
            video.title = request.form.get('title')
            video.description = request.form.get('description') or None
            video.grade = request.form.get('grade')
            video.youtube_url = youtube_url
            video.youtube_video_id = youtube_video_id
            video.publish_date = publish_date
            video.end_date = end_date
            video.is_public = bool(request.form.get('is_public'))

            db.session.commit()

            flash('영상이 수정되었습니다.', 'success')
            return redirect(url_for('library.video_detail', video_id=video.video_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/video_form.html', video=video)


@library_bp.route('/admin/videos/<video_id>/delete', methods=['POST'])
@requires_permission_level(2)
def delete_video(video_id):
    """영상 삭제"""
    try:
        video = Video.query.get_or_404(video_id)
        db.session.delete(video)
        db.session.commit()

        flash('영상이 삭제되었습니다.', 'success')
        return redirect(url_for('library.videos'))

    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('library.video_detail', video_id=video_id))


# 추천도서 관리
@library_bp.route('/admin/books/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_book():
    """도서 등록"""
    if request.method == 'POST':
        try:
            book = Book(
                book_id=str(uuid.uuid4()),
                user_id=current_user.user_id,
                title=request.form.get('title'),
                author=request.form.get('author'),
                publisher=request.form.get('publisher') or None,
                isbn=request.form.get('isbn') or None,
                publication_year=int(request.form.get('publication_year')) if request.form.get('publication_year') else None,
                category=request.form.get('category') or None,
                description=request.form.get('description') or None,
                recommendation_reason=request.form.get('recommendation_reason') or None,
                cover_image_url=request.form.get('cover_image_url') or None
            )

            db.session.add(book)
            db.session.commit()

            flash('도서가 등록되었습니다.', 'success')
            return redirect(url_for('library.book_detail', book_id=book.book_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/book_form.html', book=None)


@library_bp.route('/admin/books/<book_id>/edit', methods=['GET', 'POST'])
@requires_permission_level(2)
def edit_book(book_id):
    """도서 수정"""
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        try:
            book.title = request.form.get('title')
            book.author = request.form.get('author')
            book.publisher = request.form.get('publisher') or None
            book.isbn = request.form.get('isbn') or None
            book.publication_year = int(request.form.get('publication_year')) if request.form.get('publication_year') else None
            book.category = request.form.get('category') or None
            book.description = request.form.get('description') or None
            book.recommendation_reason = request.form.get('recommendation_reason') or None
            book.cover_image_url = request.form.get('cover_image_url') or None

            db.session.commit()

            flash('도서 정보가 수정되었습니다.', 'success')
            return redirect(url_for('library.book_detail', book_id=book.book_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/book_form.html', book=book)


@library_bp.route('/admin/books/<book_id>/delete', methods=['POST'])
@requires_permission_level(2)
def delete_book(book_id):
    """도서 삭제"""
    try:
        book = Book.query.get_or_404(book_id)
        db.session.delete(book)
        db.session.commit()

        flash('도서가 삭제되었습니다.', 'success')
        return redirect(url_for('library.books'))

    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('library.book_detail', book_id=book_id))


# ==================== 관리자 전용 - 기존 코드 ====================

# 명예의 전당 관리
@library_bp.route('/admin/hall-of-fame/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_hall_of_fame():
    """명예의 전당 게시글 생성"""
    if request.method == 'POST':
        try:
            # Handle file upload
            file_path = None
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'hall_of_fame')
                    os.makedirs(upload_folder, exist_ok=True)

                    original_filename = secure_filename(file.filename)
                    ext = os.path.splitext(original_filename)[1]
                    stored_filename = f"{uuid.uuid4().hex}{ext}"

                    file_full_path = os.path.join(upload_folder, stored_filename)
                    file.save(file_full_path)
                    file_path = os.path.join('hall_of_fame', stored_filename)

            # Create post
            post = HallOfFame(
                post_id=str(uuid.uuid4()),
                title=request.form.get('title'),
                content=request.form.get('content'),
                category=request.form.get('category'),
                student_id=request.form.get('student_id') or None,
                award_name=request.form.get('award_name') or None,
                grade=request.form.get('grade') or None,
                file_path=file_path,
                is_published=bool(request.form.get('is_published')),
                created_by=current_user.user_id,
                created_at=datetime.now()
            )

            db.session.add(post)
            db.session.commit()

            flash('명예의 전당 게시글이 등록되었습니다.', 'success')
            return redirect(url_for('library.hall_of_fame_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    students = Student.query.order_by(Student.name).all()
    return render_template('library/admin/hall_of_fame_form.html',
                         post=None,
                         students=students)


@library_bp.route('/admin/hall-of-fame/<post_id>/edit', methods=['GET', 'POST'])
@requires_permission_level(2)
def edit_hall_of_fame(post_id):
    """명예의 전당 게시글 수정"""
    post = HallOfFame.query.get_or_404(post_id)

    if request.method == 'POST':
        try:
            # Handle file operations
            if request.form.get('remove_file') == '1' and post.file_path:
                # Delete old file
                old_file = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
                if os.path.exists(old_file):
                    os.remove(old_file)
                post.file_path = None

            # Handle new file upload
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    # Delete old file if exists
                    if post.file_path:
                        old_file = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'hall_of_fame')
                    os.makedirs(upload_folder, exist_ok=True)

                    original_filename = secure_filename(file.filename)
                    ext = os.path.splitext(original_filename)[1]
                    stored_filename = f"{uuid.uuid4().hex}{ext}"

                    file_full_path = os.path.join(upload_folder, stored_filename)
                    file.save(file_full_path)
                    post.file_path = os.path.join('hall_of_fame', stored_filename)

            # Update post
            post.title = request.form.get('title')
            post.content = request.form.get('content')
            post.category = request.form.get('category')
            post.student_id = request.form.get('student_id') or None
            post.award_name = request.form.get('award_name') or None
            post.grade = request.form.get('grade') or None
            post.is_published = bool(request.form.get('is_published'))
            post.updated_at = datetime.now()

            db.session.commit()

            flash('명예의 전당 게시글이 수정되었습니다.', 'success')
            return redirect(url_for('library.hall_of_fame_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    students = Student.query.order_by(Student.name).all()
    return render_template('library/admin/hall_of_fame_form.html',
                         post=post,
                         students=students)


@library_bp.route('/admin/hall-of-fame/<post_id>/delete', methods=['POST'])
@requires_permission_level(2)
def delete_hall_of_fame(post_id):
    """명예의 전당 게시글 삭제"""
    try:
        post = HallOfFame.query.get_or_404(post_id)

        # Delete file if exists
        if post.file_path:
            file_full_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        db.session.delete(post)
        db.session.commit()

        flash('명예의 전당 게시글이 삭제되었습니다.', 'success')
        return redirect(url_for('library.hall_of_fame'))

    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('library.hall_of_fame_detail', post_id=post_id))


# 입시정보 관리
@library_bp.route('/admin/admission-info/new', methods=['GET', 'POST'])
@requires_permission_level(2)
def create_admission_info():
    """입시정보 게시글 생성"""
    if request.method == 'POST':
        try:
            # Handle file upload
            file_path = None
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'admission_info')
                    os.makedirs(upload_folder, exist_ok=True)

                    original_filename = secure_filename(file.filename)
                    ext = os.path.splitext(original_filename)[1]
                    stored_filename = f"{uuid.uuid4().hex}{ext}"

                    file_full_path = os.path.join(upload_folder, stored_filename)
                    file.save(file_full_path)
                    file_path = os.path.join('admission_info', stored_filename)

            # Parse dates
            publish_date = None
            if request.form.get('publish_date'):
                publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d').date()

            expire_date = None
            if request.form.get('expire_date'):
                expire_date = datetime.strptime(request.form.get('expire_date'), '%Y-%m-%d').date()

            # Create post
            post = AdmissionInfo(
                post_id=str(uuid.uuid4()),
                title=request.form.get('title'),
                content=request.form.get('content'),
                category=request.form.get('category'),
                target_grades=request.form.get('target_grades') or None,
                external_url=request.form.get('external_url') or None,
                file_path=file_path,
                publish_date=publish_date,
                expire_date=expire_date,
                is_important=bool(request.form.get('is_important')),
                created_by=current_user.user_id,
                created_at=datetime.now()
            )

            db.session.add(post)
            db.session.commit()

            flash('입시정보 게시글이 등록되었습니다.', 'success')
            return redirect(url_for('library.admission_info_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/admission_info_form.html',
                         post=None)


@library_bp.route('/admin/admission-info/<post_id>/edit', methods=['GET', 'POST'])
@requires_permission_level(2)
def edit_admission_info(post_id):
    """입시정보 게시글 수정"""
    post = AdmissionInfo.query.get_or_404(post_id)

    if request.method == 'POST':
        try:
            # Handle file operations
            if request.form.get('remove_file') == '1' and post.file_path:
                # Delete old file
                old_file = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
                if os.path.exists(old_file):
                    os.remove(old_file)
                post.file_path = None

            # Handle new file upload
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    # Delete old file if exists
                    if post.file_path:
                        old_file = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
                        if os.path.exists(old_file):
                            os.remove(old_file)

                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'admission_info')
                    os.makedirs(upload_folder, exist_ok=True)

                    original_filename = secure_filename(file.filename)
                    ext = os.path.splitext(original_filename)[1]
                    stored_filename = f"{uuid.uuid4().hex}{ext}"

                    file_full_path = os.path.join(upload_folder, stored_filename)
                    file.save(file_full_path)
                    post.file_path = os.path.join('admission_info', stored_filename)

            # Parse dates
            if request.form.get('publish_date'):
                post.publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d').date()
            else:
                post.publish_date = None

            if request.form.get('expire_date'):
                post.expire_date = datetime.strptime(request.form.get('expire_date'), '%Y-%m-%d').date()
            else:
                post.expire_date = None

            # Update post
            post.title = request.form.get('title')
            post.content = request.form.get('content')
            post.category = request.form.get('category')
            post.target_grades = request.form.get('target_grades') or None
            post.external_url = request.form.get('external_url') or None
            post.is_important = bool(request.form.get('is_important'))
            post.updated_at = datetime.now()

            db.session.commit()

            flash('입시정보 게시글이 수정되었습니다.', 'success')
            return redirect(url_for('library.admission_info_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/admission_info_form.html',
                         post=post)


@library_bp.route('/admin/admission-info/<post_id>/delete', methods=['POST'])
@requires_permission_level(2)
def delete_admission_info(post_id):
    """입시정보 게시글 삭제"""
    try:
        post = AdmissionInfo.query.get_or_404(post_id)

        # Delete file if exists
        if post.file_path:
            file_full_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), post.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        db.session.delete(post)
        db.session.commit()

        flash('입시정보 게시글이 삭제되었습니다.', 'success')
        return redirect(url_for('library.admission_info'))

    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('library.admission_info_detail', post_id=post_id))
