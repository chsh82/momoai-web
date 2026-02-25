# -*- coding: utf-8 -*-
"""도서 관리 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.books import books_bp
from app.books.forms import BookForm
from app.books.isbn_service import ISBNService
from app.models import db, Book, EssayBook


@books_bp.route('/')
@login_required
def index():
    """도서 목록"""
    # 검색 및 필터
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    sort_by = request.args.get('sort', 'recent')

    # 기본 쿼리
    query = Book.query

    # 검색 (제목, 저자, ISBN)
    if search:
        query = query.filter(
            db.or_(
                Book.title.contains(search),
                Book.author.contains(search),
                Book.isbn.contains(search)
            )
        )

    # 카테고리 필터
    if category_filter:
        query = query.filter_by(category=category_filter)

    # 정렬
    if sort_by == 'title':
        query = query.order_by(Book.title.asc())
    elif sort_by == 'author':
        query = query.order_by(Book.author.asc())
    elif sort_by == 'recent':
        query = query.order_by(Book.created_at.desc())
    else:
        query = query.order_by(Book.created_at.desc())

    books = query.all()

    return render_template('books/index.html',
                         books=books,
                         search=search,
                         category_filter=category_filter,
                         sort_by=sort_by)


@books_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """도서 추가"""
    form = BookForm()

    if form.validate_on_submit():
        book = Book(
            user_id=current_user.user_id,
            title=form.title.data,
            author=form.author.data if form.author.data else None,
            publisher=form.publisher.data if form.publisher.data else None,
            isbn=form.isbn.data if form.isbn.data else None,
            publication_year=form.publication_year.data if form.publication_year.data else None,
            category=form.category.data if form.category.data else None,
            description=form.description.data if form.description.data else None,
            cover_image_url=form.cover_image_url.data if form.cover_image_url.data else None
        )

        db.session.add(book)
        db.session.commit()

        flash(f'"{book.title}" 도서가 추가되었습니다.', 'success')
        return redirect(url_for('books.detail', book_id=book.book_id))

    return render_template('books/form.html',
                         form=form,
                         title='새 도서 추가',
                         is_edit=False)


@books_bp.route('/<book_id>')
@login_required
def detail(book_id):
    """도서 상세"""
    book = Book.query.get_or_404(book_id)

    # 이 도서를 참고한 첨삭 목록
    essay_relations = EssayBook.query.filter_by(book_id=book_id).all()
    essays = [rel.essay for rel in essay_relations]

    return render_template('books/detail.html',
                         book=book,
                         essays=essays)


@books_bp.route('/<book_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(book_id):
    """도서 수정"""
    book = Book.query.get_or_404(book_id)

    # 권한 확인 (본인 또는 관리자만)
    if book.user_id != current_user.user_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('books.detail', book_id=book_id))

    form = BookForm(obj=book)

    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data if form.author.data else None
        book.publisher = form.publisher.data if form.publisher.data else None
        book.isbn = form.isbn.data if form.isbn.data else None
        book.publication_year = form.publication_year.data if form.publication_year.data else None
        book.category = form.category.data if form.category.data else None
        book.description = form.description.data if form.description.data else None
        book.cover_image_url = form.cover_image_url.data if form.cover_image_url.data else None

        db.session.commit()

        flash(f'"{book.title}" 정보가 수정되었습니다.', 'success')
        return redirect(url_for('books.detail', book_id=book.book_id))

    return render_template('books/form.html',
                         form=form,
                         title=f'{book.title} 수정',
                         is_edit=True,
                         book=book)


@books_bp.route('/<book_id>/delete', methods=['POST'])
@login_required
def delete(book_id):
    """도서 삭제"""
    book = Book.query.get_or_404(book_id)

    # 권한 확인
    if book.user_id != current_user.user_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('books.detail', book_id=book_id))

    book_title = book.title

    db.session.delete(book)
    db.session.commit()

    flash(f'"{book_title}" 도서가 삭제되었습니다.', 'info')
    return redirect(url_for('books.index'))


# API: ISBN 조회
@books_bp.route('/api/isbn-lookup', methods=['POST'])
@login_required
def isbn_lookup():
    """ISBN으로 도서 정보 조회"""
    data = request.get_json(silent=True) or {}
    isbn = data.get('isbn', '').strip()

    if not isbn:
        return jsonify({'success': False, 'message': 'ISBN을 입력하세요.'}), 400

    # ISBN 조회
    book_info = ISBNService.lookup_isbn(isbn)

    if not book_info:
        return jsonify({'success': False, 'message': 'ISBN으로 도서 정보를 찾을 수 없습니다.'}), 404

    return jsonify({
        'success': True,
        'book': book_info
    })
