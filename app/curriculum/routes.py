# -*- coding: utf-8 -*-
"""모모의 책장 커리큘럼 관리 라우트"""
import io
from datetime import datetime

from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import distinct

from app.curriculum import curriculum_bp
from app.curriculum.importer import parse_workbook, apply_import
from app.models import db
from app.models.book import Book
from app.models.curriculum import CurriculumWeek
from app.utils.decorators import requires_permission_level

GRADE_CHOICES = [
    ('초1', '초등 1학년'), ('초2', '초등 2학년'), ('초3', '초등 3학년'),
    ('초4', '초등 4학년'), ('초5', '초등 5학년'), ('초6', '초등 6학년'),
    ('중1', '중등 1학년'), ('중2', '중등 2학년'), ('중3', '중등 3학년'),
    ('고1', '고등 1학년'), ('고2', '고등 2학년'), ('고3', '고등 3학년'),
]
GRADE_LABELS = dict(GRADE_CHOICES)


@curriculum_bp.route('/')
@login_required
@requires_permission_level(2)
def index():
    """연도/분기/학년별 커리큘럼 주차 목록 (매니저 이상만 접근 가능)"""
    year = request.args.get('year', type=int)
    quarter = request.args.get('quarter') or None
    grade = request.args.get('grade') or None

    query = CurriculumWeek.query
    if year:
        query = query.filter(CurriculumWeek.year == year)
    if quarter:
        query = query.filter(CurriculumWeek.quarter == quarter)
    if grade:
        query = query.filter(CurriculumWeek.grade == grade)

    weeks = query.order_by(
        CurriculumWeek.grade, CurriculumWeek.quarter, CurriculumWeek.week_number
    ).all()

    years = [r[0] for r in db.session.query(distinct(CurriculumWeek.year))
             .order_by(CurriculumWeek.year.desc()).all()]
    quarters = sorted(r[0] for r in db.session.query(distinct(CurriculumWeek.quarter)).all())

    return render_template(
        'curriculum/list.html',
        weeks=weeks,
        years=years,
        quarters=quarters,
        grade_choices=GRADE_CHOICES,
        grade_labels=GRADE_LABELS,
        filter_year=year,
        filter_quarter=quarter,
        filter_grade=grade,
        total_count=CurriculumWeek.query.count(),
    )


@curriculum_bp.route('/upload', methods=['GET'])
@login_required
@requires_permission_level(2)
def upload_page():
    return render_template('curriculum/upload.html')


@curriculum_bp.route('/upload', methods=['POST'])
@login_required
@requires_permission_level(2)
def upload():
    """엑셀 업로드 -> "연간 전체 리스트" 시트 파싱 -> curriculum_weeks/books upsert.
    같은 (연도, 분기, 학년, 주차) 조합은 덮어쓰므로 같은 파일을 수정해서 다시 올려도 안전함."""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '파일을 선택하세요.'}), 400
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'error': '.xlsx 파일만 업로드할 수 있습니다.'}), 400

    try:
        rows = parse_workbook(io.BytesIO(file.read()))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if not rows:
        return jsonify({'error': '파싱된 데이터가 없습니다. 파일 형식을 확인하세요.'}), 400

    stats = apply_import(rows, current_user.user_id)
    db.session.commit()
    return jsonify({'ok': True, **stats})


@curriculum_bp.route('/books/search')
@login_required
@requires_permission_level(2)
def search_books():
    """주차 도서 교체용 - 기존 도서 제목/저자로 검색(신규 도서 생성은 도서 관리에서)"""
    q = (request.args.get('q') or '').strip()
    if len(q) < 1:
        return jsonify({'items': []})

    books = Book.query.filter(
        db.or_(Book.title.contains(q), Book.author.contains(q))
    ).order_by(Book.title).limit(15).all()

    return jsonify({'items': [
        {
            'book_id': b.book_id,
            'title': b.title,
            'author': b.author or '',
            'publisher': b.publisher or '',
            'cover_image_url': b.cover_image_url or '',
        } for b in books
    ]})


@curriculum_bp.route('/weeks/<week_id>/book', methods=['POST'])
@login_required
@requires_permission_level(2)
def set_week_book(week_id):
    """주차 1건에 연결된 도서만 교체(주차 추가/삭제, 학년/분기 구조 변경은 지원하지 않음)"""
    week = CurriculumWeek.query.get(week_id)
    if not week:
        return jsonify({'error': '주차를 찾을 수 없습니다.'}), 404
    if week.is_holiday:
        return jsonify({'error': '휴강 주차는 도서를 연결할 수 없습니다.'}), 400

    body = request.get_json(silent=True) or {}
    book_id = (body.get('book_id') or '').strip()
    book = Book.query.get(book_id) if book_id else None
    if not book:
        return jsonify({'error': '도서를 찾을 수 없습니다.'}), 404

    week.book_id = book.book_id
    week.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'ok': True,
        'book': {
            'book_id': book.book_id, 'title': book.title,
            'author': book.author or '', 'publisher': book.publisher or '',
        },
    })
