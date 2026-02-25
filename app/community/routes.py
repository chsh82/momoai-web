# -*- coding: utf-8 -*-
"""커뮤니티 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pathlib import Path
import uuid

from app.community import community_bp
from app.community.forms import PostForm, CommentForm
from app.models import db, Post, Comment, PostLike, Notification, Tag, PostTag, Bookmark, PostFile


@community_bp.route('/')
@login_required
def index():
    """게시판 목록"""
    # 필터 및 검색
    category_filter = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'recent')

    # 기본 쿼리
    query = Post.query

    # 카테고리 필터
    if category_filter:
        query = query.filter_by(category=category_filter)

    # 검색 (제목, 내용)
    if search:
        query = query.filter(
            db.or_(
                Post.title.contains(search),
                Post.content.contains(search)
            )
        )

    # 정렬
    if sort_by == 'recent':
        query = query.order_by(Post.is_pinned.desc(), Post.created_at.desc())
    elif sort_by == 'views':
        query = query.order_by(Post.is_pinned.desc(), Post.views.desc())
    elif sort_by == 'likes':
        query = query.order_by(Post.is_pinned.desc(), Post.likes_count.desc())
    else:
        query = query.order_by(Post.is_pinned.desc(), Post.created_at.desc())

    posts = query.all()

    return render_template('community/index.html',
                         posts=posts,
                         category_filter=category_filter,
                         search=search,
                         sort_by=sort_by)


@community_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """게시글 작성"""
    if current_user.role != 'admin':
        flash('관리자만 게시글을 작성할 수 있습니다.', 'error')
        return redirect(url_for('community.index'))

    form = PostForm()

    if form.validate_on_submit():
        post = Post(
            user_id=current_user.user_id,
            title=form.title.data,
            content=form.content.data,
            category=form.category.data
        )

        db.session.add(post)
        db.session.flush()  # post_id 생성

        # 태그 처리
        if form.tags.data:
            tag_names = [t.strip() for t in form.tags.data.split(',') if t.strip()]
            for tag_name in tag_names[:5]:  # 최대 5개까지
                # 태그가 이미 존재하는지 확인
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()

                # PostTag 생성
                post_tag = PostTag(post_id=post.post_id, tag_id=tag.tag_id)
                db.session.add(post_tag)

        # 파일 처리
        if form.files.data:
            upload_folder = Path(current_app.config['POST_FILES_FOLDER'])
            for file in form.files.data:
                if file and file.filename:
                    # 안전한 파일명 생성
                    original_filename = secure_filename(file.filename)
                    file_ext = Path(original_filename).suffix
                    stored_filename = f"{uuid.uuid4()}{file_ext}"

                    # 파일 저장
                    file_path = upload_folder / stored_filename
                    file.save(str(file_path))

                    # 파일 정보 저장
                    post_file = PostFile(
                        post_id=post.post_id,
                        filename=original_filename,
                        stored_filename=stored_filename,
                        file_size=file_path.stat().st_size,
                        file_type=file.content_type
                    )
                    db.session.add(post_file)

        db.session.commit()

        flash('게시글이 작성되었습니다.', 'success')
        return redirect(url_for('community.detail', post_id=post.post_id))

    return render_template('community/form.html',
                         form=form,
                         title='새 게시글 작성',
                         is_edit=False)


@community_bp.route('/<post_id>')
@login_required
def detail(post_id):
    """게시글 상세"""
    post = Post.query.get_or_404(post_id)

    # 조회수 증가
    post.views += 1
    db.session.commit()

    # 댓글 폼
    comment_form = CommentForm()

    # 최상위 댓글만 가져오기 (대댓글은 replies로 접근)
    comments = Comment.query.filter_by(post_id=post_id, parent_comment_id=None)\
        .order_by(Comment.created_at.asc()).all()

    return render_template('community/detail.html',
                         post=post,
                         comment_form=comment_form,
                         comments=comments)


@community_bp.route('/<post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    """게시글 수정"""
    post = Post.query.get_or_404(post_id)

    # 권한 확인
    if current_user.role != 'admin':
        flash('관리자만 게시글을 수정할 수 있습니다.', 'error')
        return redirect(url_for('community.detail', post_id=post_id))

    form = PostForm(obj=post)

    # 기존 태그 로드
    if request.method == 'GET':
        existing_tags = [pt.tag.name for pt in post.post_tags]
        form.tags.data = ', '.join(existing_tags)

    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        post.category = form.category.data

        # 기존 태그 삭제
        for post_tag in post.post_tags:
            db.session.delete(post_tag)

        # 새 태그 추가
        if form.tags.data:
            tag_names = [t.strip() for t in form.tags.data.split(',') if t.strip()]
            for tag_name in tag_names[:5]:  # 최대 5개까지
                # 태그가 이미 존재하는지 확인
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                    db.session.flush()

                # PostTag 생성
                post_tag = PostTag(post_id=post.post_id, tag_id=tag.tag_id)
                db.session.add(post_tag)

        db.session.commit()

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('community.detail', post_id=post.post_id))

    return render_template('community/form.html',
                         form=form,
                         title='게시글 수정',
                         is_edit=True,
                         post=post)


@community_bp.route('/<post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    """게시글 삭제"""
    post = Post.query.get_or_404(post_id)

    # 권한 확인
    if current_user.role != 'admin':
        flash('관리자만 게시글을 삭제할 수 있습니다.', 'error')
        return redirect(url_for('community.detail', post_id=post_id))

    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'info')
    return redirect(url_for('community.index'))


# API: 좋아요
@community_bp.route('/api/posts/<post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    """게시글 좋아요"""
    post = Post.query.get_or_404(post_id)

    # 이미 좋아요를 눌렀는지 확인
    existing_like = PostLike.query.filter_by(
        user_id=current_user.user_id,
        post_id=post_id
    ).first()

    if existing_like:
        # 좋아요 취소
        db.session.delete(existing_like)
        post.likes_count = max(0, post.likes_count - 1)
        action = 'unliked'
    else:
        # 좋아요 추가
        like = PostLike(user_id=current_user.user_id, post_id=post_id)
        db.session.add(like)
        post.likes_count += 1
        action = 'liked'

        # 알림 생성 (게시글 작성자에게, 본인 좋아요가 아닌 경우)
        if post.user_id != current_user.user_id:
            Notification.create_notification(
                user_id=post.user_id,
                notification_type='like',
                title=f"{current_user.name}님이 좋아요를 눌렀습니다",
                message=f'"{post.title}" 게시글에 좋아요를 눌렀습니다',
                link_url=url_for('community.detail', post_id=post_id),
                related_user_id=current_user.user_id,
                related_entity_type='post',
                related_entity_id=post_id
            )

    db.session.commit()

    return jsonify({
        'success': True,
        'action': action,
        'likes_count': post.likes_count
    })


# API: 댓글 작성
@community_bp.route('/api/posts/<post_id>/comments', methods=['POST'])
@login_required
def add_comment(post_id):
    """댓글 작성"""
    post = Post.query.get_or_404(post_id)

    content = request.json.get('content', '').strip()
    parent_comment_id = request.json.get('parent_comment_id')

    if not content:
        return jsonify({'success': False, 'message': '댓글 내용을 입력하세요.'}), 400

    comment = Comment(
        post_id=post_id,
        user_id=current_user.user_id,
        content=content,
        parent_comment_id=parent_comment_id if parent_comment_id else None
    )

    db.session.add(comment)
    db.session.commit()

    # 알림 생성 (게시글 작성자에게, 본인 댓글이 아닌 경우)
    if post.user_id != current_user.user_id:
        if parent_comment_id:
            # 대댓글인 경우
            parent_comment = Comment.query.get(parent_comment_id)
            notification_title = f"{current_user.name}님이 답글을 남겼습니다"
            notification_message = f'"{parent_comment.content[:50]}..." 에 대한 답글: {content[:100]}'
            # 원댓글 작성자에게도 알림
            if parent_comment.user_id != current_user.user_id:
                Notification.create_notification(
                    user_id=parent_comment.user_id,
                    notification_type='comment',
                    title=notification_title,
                    message=notification_message,
                    link_url=url_for('community.detail', post_id=post_id),
                    related_user_id=current_user.user_id,
                    related_entity_type='comment',
                    related_entity_id=comment.comment_id
                )
        else:
            # 일반 댓글인 경우
            notification_title = f"{current_user.name}님이 댓글을 남겼습니다"
            notification_message = f'"{post.title}" 에 댓글: {content[:100]}'

        Notification.create_notification(
            user_id=post.user_id,
            notification_type='comment',
            title=notification_title,
            message=notification_message,
            link_url=url_for('community.detail', post_id=post_id),
            related_user_id=current_user.user_id,
            related_entity_type='comment',
            related_entity_id=comment.comment_id
        )

    return jsonify({
        'success': True,
        'comment': {
            'comment_id': comment.comment_id,
            'user_name': current_user.name,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        }
    })


# API: 댓글 삭제
@community_bp.route('/api/comments/<comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    """댓글 삭제"""
    comment = Comment.query.get_or_404(comment_id)

    # 권한 확인
    if comment.user_id != current_user.user_id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'success': True})


# API: 북마크
@community_bp.route('/api/posts/<post_id>/bookmark', methods=['POST'])
@login_required
def bookmark_post(post_id):
    """게시글 북마크"""
    post = Post.query.get_or_404(post_id)

    # 이미 북마크했는지 확인
    existing_bookmark = Bookmark.query.filter_by(
        user_id=current_user.user_id,
        post_id=post_id
    ).first()

    if existing_bookmark:
        # 북마크 취소
        db.session.delete(existing_bookmark)
        action = 'unbookmarked'
    else:
        # 북마크 추가
        bookmark = Bookmark(user_id=current_user.user_id, post_id=post_id)
        db.session.add(bookmark)
        action = 'bookmarked'

    db.session.commit()

    return jsonify({
        'success': True,
        'action': action
    })


@community_bp.route('/bookmarks')
@login_required
def bookmarks():
    """내 북마크 목록"""
    # 북마크한 게시글 목록
    bookmarked_posts = db.session.query(Post)\
        .join(Bookmark, Bookmark.post_id == Post.post_id)\
        .filter(Bookmark.user_id == current_user.user_id)\
        .order_by(Bookmark.created_at.desc())\
        .all()

    return render_template('community/bookmarks.html',
                         posts=bookmarked_posts)


@community_bp.route('/tags/<tag_name>')
@login_required
def tag_posts(tag_name):
    """특정 태그의 게시글 목록"""
    tag = Tag.query.filter_by(name=tag_name).first_or_404()

    # 이 태그를 가진 게시글들
    posts = db.session.query(Post)\
        .join(PostTag, PostTag.post_id == Post.post_id)\
        .filter(PostTag.tag_id == tag.tag_id)\
        .order_by(Post.created_at.desc())\
        .all()

    return render_template('community/tag_posts.html',
                         tag=tag,
                         posts=posts)


# 파일 다운로드
@community_bp.route('/files/<file_id>/download')
@login_required
def download_file(file_id):
    """파일 다운로드"""
    post_file = PostFile.query.get_or_404(file_id)

    upload_folder = current_app.config['POST_FILES_FOLDER']

    return send_from_directory(
        upload_folder,
        post_file.stored_filename,
        as_attachment=True,
        download_name=post_file.filename
    )
