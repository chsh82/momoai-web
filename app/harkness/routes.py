# -*- coding: utf-8 -*-
"""하크니스 게시판 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app.harkness import harkness_bp
from app.models import db, Course
from app.models.harkness_board import HarknessBoard, HarknessPost, HarknessComment, HarknessPostLike
from app.utils.harkness_utils import (
    can_access_harkness_board,
    get_accessible_harkness_boards,
    can_create_harkness_board,
    can_write_notice
)


# ==================== 게시판 목록 ====================

@harkness_bp.route('/')
@login_required
def index():
    """하크니스 게시판 목록"""
    # 접근 가능한 게시판 목록
    boards = get_accessible_harkness_boards(current_user)

    # 학생인데 접근 가능한 게시판이 없는 경우
    if current_user.role == 'student' and not boards:
        flash('하크니스 게시판의 접근 권한이 없습니다. 하크니스 수업을 수강 중인 학생만 이용할 수 있습니다.', 'error')
        return redirect(url_for('student.index'))

    # 생성 권한 확인
    can_create = can_create_harkness_board(current_user)

    return render_template('harkness/boards.html',
                         boards=boards,
                         can_create=can_create)


# ==================== 게시판 생성 ====================

@harkness_bp.route('/boards/new', methods=['GET', 'POST'])
@login_required
def create_board():
    """하크니스 게시판 생성"""
    if not can_create_harkness_board(current_user):
        flash('게시판 생성 권한이 없습니다.', 'error')
        return redirect(url_for('harkness.index'))

    if request.method == 'POST':
        board_type = request.form.get('board_type')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        course_id = request.form.get('course_id', '').strip() if board_type == 'course' else None

        if not title:
            flash('제목을 입력해주세요.', 'error')
            return redirect(url_for('harkness.create_board'))

        # 하크니스 전체 게시판은 관리자만 생성 가능
        if board_type == 'harkness_all' and not current_user.is_admin:
            flash('하크니스 전체 게시판은 관리자만 생성할 수 있습니다.', 'error')
            return redirect(url_for('harkness.create_board'))

        # 수업 게시판 생성 시 course_id 필수
        if board_type == 'course' and not course_id:
            flash('수업을 선택해주세요.', 'error')
            return redirect(url_for('harkness.create_board'))

        # 게시판 생성
        board = HarknessBoard(
            board_type=board_type,
            course_id=course_id if board_type == 'course' else None,
            title=title,
            description=description,
            created_by=current_user.user_id
        )
        db.session.add(board)
        db.session.commit()

        flash('게시판이 생성되었습니다.', 'success')
        return redirect(url_for('harkness.board_detail', board_id=board.board_id))

    # 강사가 담당하는 하크니스 수업 목록
    harkness_courses = []
    if current_user.role == 'teacher':
        harkness_courses = Course.query.filter_by(
            teacher_id=current_user.user_id,
            course_type='harkness',
            status='active'
        ).order_by(Course.course_name).all()

    return render_template('harkness/board_form.html',
                         harkness_courses=harkness_courses,
                         board=None)


# ==================== 게시판 상세 (게시글 목록) ====================

@harkness_bp.route('/boards/<board_id>')
@login_required
def board_detail(board_id):
    """하크니스 게시판 상세 (게시글 목록)"""
    board = HarknessBoard.query.get_or_404(board_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        flash('이 게시판에 접근할 권한이 없습니다. 하크니스 수업을 수강 중인 학생만 이용할 수 있습니다.', 'error')
        return redirect(url_for('harkness.index'))

    # 페이지네이션
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 검색
    search_query = request.args.get('q', '').strip()

    # 쿼리 생성
    query = HarknessPost.query.filter_by(board_id=board_id)

    if search_query:
        query = query.filter(
            db.or_(
                HarknessPost.title.contains(search_query),
                HarknessPost.content.contains(search_query)
            )
        )

    # 정렬: 공지사항 우선, 최신순
    query = query.order_by(
        HarknessPost.is_notice.desc(),
        HarknessPost.created_at.desc()
    )

    # 페이지네이션
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items

    return render_template('harkness/board.html',
                         board=board,
                         posts=posts,
                         pagination=pagination,
                         search_query=search_query,
                         can_write_notice=can_write_notice(current_user, board))


# ==================== 게시글 작성 ====================

@harkness_bp.route('/boards/<board_id>/posts/new', methods=['GET', 'POST'])
@login_required
def create_post(board_id):
    """하크니스 게시글 작성"""
    board = HarknessBoard.query.get_or_404(board_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        flash('이 게시판에 접근할 권한이 없습니다. 하크니스 수업을 수강 중인 학생만 이용할 수 있습니다.', 'error')
        return redirect(url_for('harkness.index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_notice = request.form.get('is_notice') == 'on'

        if not title or not content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return redirect(url_for('harkness.create_post', board_id=board_id))

        # 공지사항 권한 체크
        if is_notice and not can_write_notice(current_user, board):
            is_notice = False

        # 게시글 생성
        post = HarknessPost(
            board_id=board_id,
            author_id=current_user.user_id,
            title=title,
            content=content,
            is_notice=is_notice
        )
        db.session.add(post)
        db.session.commit()

        flash('게시글이 등록되었습니다.', 'success')
        return redirect(url_for('harkness.post_detail', board_id=board_id, post_id=post.post_id))

    return render_template('harkness/post_form.html',
                         board=board,
                         post=None,
                         can_write_notice=can_write_notice(current_user, board))


# ==================== 게시글 상세 ====================

@harkness_bp.route('/boards/<board_id>/posts/<post_id>')
@login_required
def post_detail(board_id, post_id):
    """하크니스 게시글 상세"""
    board = HarknessBoard.query.get_or_404(board_id)
    post = HarknessPost.query.get_or_404(post_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        flash('이 게시판에 접근할 권한이 없습니다. 하크니스 수업을 수강 중인 학생만 이용할 수 있습니다.', 'error')
        return redirect(url_for('harkness.index'))

    # 조회수 증가 (본인 글 제외)
    if post.author_id != current_user.user_id:
        post.view_count += 1
        db.session.commit()

    # 최상위 댓글 목록 (답글이 아닌 댓글만)
    comments = post.comments.filter_by(parent_comment_id=None).all()

    return render_template('harkness/post.html',
                         board=board,
                         post=post,
                         comments=comments)


# ==================== 게시글 수정 ====================

@harkness_bp.route('/boards/<board_id>/posts/<post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(board_id, post_id):
    """하크니스 게시글 수정"""
    board = HarknessBoard.query.get_or_404(board_id)
    post = HarknessPost.query.get_or_404(post_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        flash('이 게시판에 접근할 권한이 없습니다. 하크니스 수업을 수강 중인 학생만 이용할 수 있습니다.', 'error')
        return redirect(url_for('harkness.index'))

    # 본인 글이거나 관리자만 수정 가능
    if post.author_id != current_user.user_id and not current_user.is_admin:
        flash('수정 권한이 없습니다.', 'error')
        return redirect(url_for('harkness.post_detail', board_id=board_id, post_id=post_id))

    if request.method == 'POST':
        post.title = request.form.get('title', '').strip()
        post.content = request.form.get('content', '').strip()
        is_notice = request.form.get('is_notice') == 'on'

        if not post.title or not post.content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return render_template('harkness/post_form.html', board=board, post=post, can_write_notice=can_write_notice(current_user, board))

        # 공지사항 권한 체크
        if can_write_notice(current_user, board):
            post.is_notice = is_notice

        db.session.commit()

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('harkness.post_detail', board_id=board_id, post_id=post_id))

    return render_template('harkness/post_form.html',
                         board=board,
                         post=post,
                         can_write_notice=can_write_notice(current_user, board))


# ==================== 게시글 삭제 ====================

@harkness_bp.route('/boards/<board_id>/posts/<post_id>/delete', methods=['POST'])
@login_required
def delete_post(board_id, post_id):
    """하크니스 게시글 삭제"""
    board = HarknessBoard.query.get_or_404(board_id)
    post = HarknessPost.query.get_or_404(post_id)

    # 본인 글이거나 관리자만 삭제 가능
    if post.author_id != current_user.user_id and not current_user.is_admin:
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('harkness.post_detail', board_id=board_id, post_id=post_id))

    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('harkness.board_detail', board_id=board_id))


# ==================== 댓글 작성 ====================

@harkness_bp.route('/boards/<board_id>/posts/<post_id>/comments', methods=['POST'])
@login_required
def create_comment(board_id, post_id):
    """하크니스 댓글/답글 작성"""
    board = HarknessBoard.query.get_or_404(board_id)
    post = HarknessPost.query.get_or_404(post_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        return jsonify({'success': False, 'message': '접근 권한이 없습니다.'}), 403

    content = request.form.get('content', '').strip()
    parent_comment_id = request.form.get('parent_comment_id', '').strip() or None

    if not content:
        return jsonify({'success': False, 'message': '내용을 입력해주세요.'}), 400

    # 부모 댓글 확인 (답글인 경우)
    if parent_comment_id:
        parent_comment = HarknessComment.query.get(parent_comment_id)
        if not parent_comment or parent_comment.post_id != post_id:
            return jsonify({'success': False, 'message': '유효하지 않은 댓글입니다.'}), 400

    # 댓글/답글 생성
    comment = HarknessComment(
        post_id=post_id,
        author_id=current_user.user_id,
        parent_comment_id=parent_comment_id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'success': True,
        'comment': {
            'comment_id': comment.comment_id,
            'parent_comment_id': parent_comment_id,
            'author_name': current_user.name,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_author': True
        }
    })


# ==================== 댓글 삭제 ====================

@harkness_bp.route('/comments/<comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """하크니스 댓글 삭제"""
    comment = HarknessComment.query.get_or_404(comment_id)

    # 본인 댓글이거나 관리자만 삭제 가능
    if comment.author_id != current_user.user_id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '삭제 권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'success': True, 'message': '댓글이 삭제되었습니다.'})


# ==================== 게시글 좋아요 ====================

@harkness_bp.route('/posts/<post_id>/like', methods=['POST'])
@login_required
def toggle_like(post_id):
    """게시글 좋아요 토글"""
    post = HarknessPost.query.get_or_404(post_id)
    board = HarknessBoard.query.get_or_404(post.board_id)

    # 접근 권한 확인
    if not can_access_harkness_board(current_user, board):
        return jsonify({'success': False, 'message': '접근 권한이 없습니다.'}), 403

    # 이미 좋아요를 눌렀는지 확인
    existing_like = HarknessPostLike.query.filter_by(
        post_id=post_id,
        user_id=current_user.user_id
    ).first()

    if existing_like:
        # 좋아요 취소
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({
            'success': True,
            'liked': False,
            'like_count': post.like_count,
            'message': '좋아요를 취소했습니다.'
        })
    else:
        # 좋아요 추가
        like = HarknessPostLike(
            post_id=post_id,
            user_id=current_user.user_id
        )
        db.session.add(like)
        db.session.commit()
        return jsonify({
            'success': True,
            'liked': True,
            'like_count': post.like_count,
            'message': '좋아요를 눌렀습니다.'
        })
