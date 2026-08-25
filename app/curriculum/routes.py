# -*- coding: utf-8 -*-
"""모모의 책장 커리큘럼 관리 라우트"""
import io
import os
import uuid
from datetime import datetime, date

from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import distinct

from app.curriculum import curriculum_bp
from app.curriculum.importer import parse_workbook, apply_import
from app.models import db
from app.models.book import Book
from app.models.curriculum import CurriculumWeek
from app.models.teaching_material import TeachingMaterial, TeachingMaterialFile
from app.utils.decorators import requires_permission_level
from app.utils.curriculum_targeting import compute_week_sequence
from app.utils.file_utils import safe_original_filename

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

    for w in weeks:
        w.sequence = None
        w.student_material = None
        w.teacher_material = None
        if not w.is_holiday and w.book_id:
            w.sequence = compute_week_sequence(w)
            if w.sequence:
                w.student_material = TeachingMaterial.query.filter_by(
                    book_id=w.book_id, curriculum_sequence=w.sequence, audience_role='student'
                ).first()
                w.teacher_material = TeachingMaterial.query.filter_by(
                    book_id=w.book_id, curriculum_sequence=w.sequence, audience_role='teacher'
                ).first()

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


@curriculum_bp.route('/weeks/<week_id>/material', methods=['POST'])
@login_required
@requires_permission_level(2)
def upload_week_material(week_id):
    """주차 1건에 학생용/교사용 자료를 새로 만들어 파일 업로드.
    이미 그 주차(도서+차시+구분)에 자료가 있으면 새로 만들지 않고 기존 자료 위치를 안내함
    (중복 생성 방지 - 파일 추가/삭제는 기존 "교재 관리" 편집 화면에서)."""
    from config import ALLOWED_MATERIAL_EXTENSIONS

    week = CurriculumWeek.query.get(week_id)
    if not week:
        return jsonify({'error': '주차를 찾을 수 없습니다.'}), 404
    if week.is_holiday or not week.book_id:
        return jsonify({'error': '도서가 연결된 주차만 자료를 올릴 수 있습니다.'}), 400

    audience_role = request.form.get('audience_role')
    if audience_role not in ('student', 'teacher'):
        return jsonify({'error': 'audience_role은 student 또는 teacher여야 합니다.'}), 400

    sequence = compute_week_sequence(week)
    if not sequence:
        return jsonify({'error': '차시를 계산할 수 없습니다.'}), 400

    existing = TeachingMaterial.query.filter_by(
        book_id=week.book_id, curriculum_sequence=sequence, audience_role=audience_role
    ).first()
    if existing:
        return jsonify({
            'error': '이미 이 주차에 등록된 자료가 있습니다. "교재 관리"에서 파일을 추가/삭제하세요.',
            'material_id': existing.material_id,
        }), 409

    uploaded_files = [f for f in request.files.getlist('files') if f and f.filename]
    if not uploaded_files:
        return jsonify({'error': '파일을 하나 이상 선택하세요.'}), 400
    if len(uploaded_files) > 10:
        return jsonify({'error': '파일은 최대 10개까지 업로드할 수 있습니다.'}), 400

    for f in uploaded_files:
        ext = os.path.splitext(f.filename)[1].lstrip('.').lower()
        if ext not in ALLOWED_MATERIAL_EXTENSIONS:
            return jsonify({'error': f'허용되지 않는 파일 형식: {f.filename}'}), 400

    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'materials')
    os.makedirs(upload_folder, exist_ok=True)

    book = Book.query.get(week.book_id)
    audience_label = '학생용' if audience_role == 'student' else '교사용'

    first_file = uploaded_files[0]
    first_raw_ext = os.path.splitext(first_file.filename)[1]
    first_name = safe_original_filename(first_file.filename) or f'file{first_raw_ext}'
    first_stored = f'{uuid.uuid4().hex}{first_raw_ext}'

    material = TeachingMaterial(
        title=f'{book.title} {sequence}주차 {audience_label} 자료',
        grade='커리큘럼연동',
        original_filename=first_name,
        storage_path=os.path.join('materials', first_stored),
        file_size=0,
        file_type=first_raw_ext.lstrip('.').lower(),
        publish_date=date.today(),
        is_public=True,
        audience_role=audience_role,
        target_audience='{"type": "curriculum"}',
        book_id=week.book_id,
        curriculum_sequence=sequence,
        created_by=current_user.user_id,
    )
    db.session.add(material)
    db.session.flush()

    total_size = 0
    for idx, f in enumerate(uploaded_files):
        raw_ext = os.path.splitext(f.filename)[1]
        orig_name = safe_original_filename(f.filename) or f'file{raw_ext}'
        stored_name = first_stored if idx == 0 else f'{uuid.uuid4().hex}{raw_ext}'
        file_path = os.path.join(upload_folder, stored_name)
        f.save(file_path)
        size = os.path.getsize(file_path)
        total_size += size
        db.session.add(TeachingMaterialFile(
            material_id=material.material_id,
            original_filename=orig_name,
            storage_path=os.path.join('materials', stored_name),
            file_size=size,
            file_type=raw_ext.lstrip('.').lower(),
            sort_order=idx,
        ))

    material.file_size = total_size
    db.session.commit()

    return jsonify({'ok': True, 'material_id': material.material_id, 'file_count': len(uploaded_files)})
