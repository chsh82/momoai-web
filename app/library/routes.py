# -*- coding: utf-8 -*-
"""도서 자료실 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from app.utils.file_utils import safe_original_filename
import uuid
import os

from app.library import library_bp
from app.models import db, Book, Video, Student
from app.models.library import HallOfFame, AdmissionInfo
from app.models.parent_student import ParentStudent

# 학년 → LV 태그 매핑
GRADE_TO_LV = {
    '초1': 'LV1', '초2': 'LV2', '초3': 'LV3',
    '초4': 'LV4', '초5': 'LV5', '초6': 'LV6',
    '중1': 'LV7', '중2': 'LV8', '중3': 'LV9',
    '고1': 'LV9', '고2': 'LV10', '고3': 'LV10',
}
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
    import json
    page = request.args.get('page', 1, type=int)
    current_domain = request.args.get('domain', '')
    current_subject = request.args.get('subject', '')
    current_badge = request.args.get('badge', '')
    per_page = 12

    # 학년 필터: grade 파라미터가 URL에 없으면 역할별 자동 감지
    grade_param = request.args.get('grade', None)  # None = URL에 grade 없음
    auto_grade = ''
    if grade_param is None:
        # 학생: 본인 학년으로 자동 설정
        if current_user.role == 'student':
            student = Student.query.filter_by(email=current_user.email).first()
            if student and student.grade:
                auto_grade = GRADE_TO_LV.get(student.grade, '')
        # 학부모: 연계된 자녀 중 가장 높은 학년으로 설정
        elif current_user.role == 'parent':
            parent_relations = ParentStudent.query.filter_by(
                parent_id=current_user.user_id, is_active=True
            ).all()
            child_lvs = []
            for pr in parent_relations:
                child = pr.student
                if child and child.grade:
                    lv = GRADE_TO_LV.get(child.grade, '')
                    if lv:
                        child_lvs.append(lv)
            if child_lvs:
                auto_grade = max(child_lvs, key=lambda x: int(x.replace('LV', '')))
        current_grade = auto_grade
    else:
        current_grade = grade_param  # 빈 문자열 포함 명시적 값 사용

    query = Book.query
    if current_grade:
        query = query.filter(Book.grade_tags.like(f'%"{current_grade}"%'))
    if current_domain:
        query = query.filter(Book.domain_tags.like(f'%"{current_domain}"%'))
    if current_subject:
        query = query.filter(Book.subject_tags.like(f'%"{current_subject}"%'))
    if current_badge == 'curriculum':
        query = query.filter(Book.is_curriculum == True)
    elif current_badge == 'recommended':
        query = query.filter(Book.is_recommended == True)
    elif current_badge == 'textbook':
        query = query.filter(Book.is_textbook_work == True)
    elif current_badge == 'snu':
        query = query.filter(Book.is_snu_classic == True)

    books = query.order_by(Book.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 전체 주제 태그 목록 (자동완성용)
    all_subjects = set()
    for (tags_json,) in db.session.query(Book.subject_tags).filter(Book.subject_tags != None).all():
        try:
            for t in json.loads(tags_json or '[]'):
                if t:
                    all_subjects.add(t)
        except Exception:
            pass

    return render_template('library/books.html',
                         books=books,
                         current_grade=current_grade,
                         current_domain=current_domain,
                         current_subject=current_subject,
                         current_badge=current_badge,
                         auto_grade=auto_grade,
                         all_subjects=sorted(all_subjects))


@library_bp.route('/books/<book_id>')
@login_required
def book_detail(book_id):
    """추천도서 상세"""
    from app.models.book import BookRating
    book = Book.query.get_or_404(book_id)

    # 현재 사용자의 기존 평점 조회
    my_rating = None
    if current_user.role == 'student':
        my_rating = BookRating.query.filter_by(
            book_id=book_id, user_id=current_user.user_id
        ).first()

    # 목록 복귀용 파라미터
    back_page = request.args.get('page', 1, type=int)
    back_grade = request.args.get('grade', '')
    back_domain = request.args.get('domain', '')
    back_subject = request.args.get('subject', '')
    back_badge = request.args.get('badge', '')

    # 이전/다음 책 계산 (동일 필터 기준)
    per_page = 12
    nav_query = Book.query
    if back_grade:
        nav_query = nav_query.filter(Book.grade_tags.like(f'%"{back_grade}"%'))
    if back_domain:
        nav_query = nav_query.filter(Book.domain_tags.like(f'%"{back_domain}"%'))
    if back_subject:
        nav_query = nav_query.filter(Book.subject_tags.like(f'%"{back_subject}"%'))
    if back_badge == 'curriculum':
        nav_query = nav_query.filter(Book.is_curriculum == True)
    elif back_badge == 'recommended':
        nav_query = nav_query.filter(Book.is_recommended == True)
    elif back_badge == 'textbook':
        nav_query = nav_query.filter(Book.is_textbook_work == True)
    elif back_badge == 'snu':
        nav_query = nav_query.filter(Book.is_snu_classic == True)

    all_ids = [row[0] for row in nav_query.order_by(Book.created_at.desc()).with_entities(Book.book_id).all()]
    try:
        cur_idx = all_ids.index(book_id)
    except ValueError:
        cur_idx = -1

    prev_book_id = all_ids[cur_idx - 1] if cur_idx > 0 else None
    prev_page = ((cur_idx - 1) // per_page) + 1 if prev_book_id else 1

    next_book_id = all_ids[cur_idx + 1] if 0 <= cur_idx < len(all_ids) - 1 else None
    next_page = ((cur_idx + 1) // per_page) + 1 if next_book_id else 1

    return render_template('library/book_detail.html',
                         book=book,
                         my_rating=my_rating,
                         back_page=back_page,
                         back_grade=back_grade,
                         back_domain=back_domain,
                         back_subject=back_subject,
                         back_badge=back_badge,
                         prev_book_id=prev_book_id,
                         prev_page=prev_page,
                         next_book_id=next_book_id,
                         next_page=next_page)


@library_bp.route('/books/<book_id>/rate', methods=['POST'])
@login_required
def rate_book(book_id):
    """도서 평점 등록/수정 (학생만)"""
    if current_user.role != 'student':
        return jsonify({'success': False, 'message': '학생만 평점을 등록할 수 있습니다.'}), 403

    book = Book.query.get_or_404(book_id)
    from app.models.book import BookRating

    data = request.get_json(silent=True) or {}
    try:
        fun_score = int(data.get('fun_score', 0))
        usefulness_score = int(data.get('usefulness_score', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': '점수 형식이 올바르지 않습니다.'}), 400

    if not (1 <= fun_score <= 5 and 1 <= usefulness_score <= 5):
        return jsonify({'success': False, 'message': '점수는 1~5 사이여야 합니다.'}), 400

    existing = BookRating.query.filter_by(
        book_id=book_id, user_id=current_user.user_id
    ).first()

    if existing:
        existing.fun_score = fun_score
        existing.usefulness_score = usefulness_score
        is_update = True
    else:
        rating = BookRating(
            book_id=book_id,
            user_id=current_user.user_id,
            fun_score=fun_score,
            usefulness_score=usefulness_score
        )
        db.session.add(rating)
        is_update = False

    db.session.commit()

    # 갱신된 통계 반환
    db.session.refresh(book)
    return jsonify({
        'success': True,
        'message': '평점이 수정되었습니다.' if is_update else '평점이 등록되었습니다.',
        'avg_score': book.avg_score,
        'avg_fun': book.avg_fun_score,
        'avg_usefulness': book.avg_usefulness_score,
        'rating_count': book.rating_count
    })


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

    from app.utils.image_utils import get_post_images
    images = get_post_images('hall_of_fame', post.post_id)
    return render_template('library/hall_of_fame_detail.html',
                         post=post,
                         images=images)


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

    from app.utils.image_utils import get_post_images
    images = get_post_images('admission_info', post.post_id)
    return render_template('library/admission_info_detail.html',
                         post=post,
                         images=images)


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
    import json as _json
    if request.method == 'POST':
        try:
            grade_tags = request.form.getlist('grade_tags')
            domain_tags = request.form.getlist('domain_tags')
            subject_raw = request.form.get('subject_tags', '')
            subject_tags = [t.strip() for t in subject_raw.replace('，', ',').split(',') if t.strip()]

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
                cover_image_url=request.form.get('cover_image_url') or None,
                is_curriculum=bool(request.form.get('is_curriculum')),
                is_recommended=bool(request.form.get('is_recommended')),
                is_textbook_work=bool(request.form.get('is_textbook_work')),
                is_snu_classic=bool(request.form.get('is_snu_classic')),
                grade_tags=_json.dumps(grade_tags, ensure_ascii=False) if grade_tags else None,
                domain_tags=_json.dumps(domain_tags, ensure_ascii=False) if domain_tags else None,
                subject_tags=_json.dumps(subject_tags, ensure_ascii=False) if subject_tags else None,
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
    import json as _json
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        try:
            grade_tags = request.form.getlist('grade_tags')
            domain_tags = request.form.getlist('domain_tags')
            subject_raw = request.form.get('subject_tags', '')
            subject_tags = [t.strip() for t in subject_raw.replace('，', ',').split(',') if t.strip()]

            book.title = request.form.get('title')
            book.author = request.form.get('author')
            book.publisher = request.form.get('publisher') or None
            book.isbn = request.form.get('isbn') or None
            book.publication_year = int(request.form.get('publication_year')) if request.form.get('publication_year') else None
            book.category = request.form.get('category') or None
            book.description = request.form.get('description') or None
            book.recommendation_reason = request.form.get('recommendation_reason') or None
            book.cover_image_url = request.form.get('cover_image_url') or None
            book.is_curriculum = bool(request.form.get('is_curriculum'))
            book.is_recommended = bool(request.form.get('is_recommended'))
            book.is_textbook_work = bool(request.form.get('is_textbook_work'))
            book.is_snu_classic = bool(request.form.get('is_snu_classic'))
            book.grade_tags = _json.dumps(grade_tags, ensure_ascii=False) if grade_tags else None
            book.domain_tags = _json.dumps(domain_tags, ensure_ascii=False) if domain_tags else None
            book.subject_tags = _json.dumps(subject_tags, ensure_ascii=False) if subject_tags else None

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

                    ext = os.path.splitext(file.filename)[1]
                    original_filename = safe_original_filename(file.filename) or f"file{ext}"
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
            db.session.flush()  # post_id 확보

            # 이미지 업로드 처리 (최대 10장)
            from app.utils.image_utils import save_post_images
            img_files = request.files.getlist('images')
            for img in save_post_images(img_files, 'hall_of_fame', post.post_id, current_user.user_id):
                db.session.add(img)

            db.session.commit()

            flash('명예의 전당 게시글이 등록되었습니다.', 'success')
            return redirect(url_for('library.hall_of_fame_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    students = Student.query.order_by(Student.name).all()
    return render_template('library/admin/hall_of_fame_form.html',
                         post=None,
                         students=students,
                         images=[])


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

                    ext = os.path.splitext(file.filename)[1]
                    original_filename = safe_original_filename(file.filename) or f"file{ext}"
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

            # 이미지 삭제 처리
            from app.models.post_image import PostImage
            from app.utils.image_utils import delete_post_image, save_post_images
            delete_ids = request.form.getlist('delete_images')
            for img_id in delete_ids:
                img = PostImage.query.get(img_id)
                if img and img.post_id == post.post_id:
                    delete_post_image(img)

            # 새 이미지 업로드
            existing_count = PostImage.query.filter_by(board_type='hall_of_fame', post_id=post.post_id).count()
            img_files = request.files.getlist('images')
            for img in save_post_images(img_files, 'hall_of_fame', post.post_id, current_user.user_id, existing_count):
                db.session.add(img)

            db.session.commit()

            flash('명예의 전당 게시글이 수정되었습니다.', 'success')
            return redirect(url_for('library.hall_of_fame_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    from app.utils.image_utils import get_post_images
    images = get_post_images('hall_of_fame', post.post_id)
    students = Student.query.order_by(Student.name).all()
    return render_template('library/admin/hall_of_fame_form.html',
                         post=post,
                         students=students,
                         images=images)


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

                    ext = os.path.splitext(file.filename)[1]
                    original_filename = safe_original_filename(file.filename) or f"file{ext}"
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
            db.session.flush()  # post_id 확보

            # 이미지 업로드 처리 (최대 10장)
            from app.utils.image_utils import save_post_images
            img_files = request.files.getlist('images')
            for img in save_post_images(img_files, 'admission_info', post.post_id, current_user.user_id):
                db.session.add(img)

            db.session.commit()

            flash('입시정보 게시글이 등록되었습니다.', 'success')
            return redirect(url_for('library.admission_info_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'등록 중 오류가 발생했습니다: {str(e)}', 'error')

    return render_template('library/admin/admission_info_form.html',
                         post=None,
                         images=[])


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

                    ext = os.path.splitext(file.filename)[1]
                    original_filename = safe_original_filename(file.filename) or f"file{ext}"
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

            # 이미지 삭제 처리
            from app.models.post_image import PostImage
            from app.utils.image_utils import delete_post_image, save_post_images
            delete_ids = request.form.getlist('delete_images')
            for img_id in delete_ids:
                img = PostImage.query.get(img_id)
                if img and img.post_id == post.post_id:
                    delete_post_image(img)

            # 새 이미지 업로드
            existing_count = PostImage.query.filter_by(board_type='admission_info', post_id=post.post_id).count()
            img_files = request.files.getlist('images')
            for img in save_post_images(img_files, 'admission_info', post.post_id, current_user.user_id, existing_count):
                db.session.add(img)

            db.session.commit()

            flash('입시정보 게시글이 수정되었습니다.', 'success')
            return redirect(url_for('library.admission_info_detail', post_id=post.post_id))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'error')

    from app.utils.image_utils import get_post_images
    images = get_post_images('admission_info', post.post_id)
    return render_template('library/admin/admission_info_form.html',
                         post=post,
                         images=images)


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
