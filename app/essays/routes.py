# -*- coding: utf-8 -*-
"""첨삭 관리 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory, send_file
from flask_login import login_required, current_user
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import uuid
import threading

from app.essays import essays_bp
from app.essays.forms import NewEssayForm, RevisionRequestForm
from app.essays.momoai_service import MOMOAIService
from app.essays.ocr_service import OCRService
from app.essays.gemini_ocr_service import GeminiOCRService
from app.models import db, Student, Essay, EssayVersion, Notification, OCRHistory
from config import Config


def _can_access_essay(essay):
    """
    현재 로그인 유저가 해당 essay에 접근 가능한지 확인.
    - admin: 항상 허용
    - essay.user_id 일치: 허용 (직접 생성한 강사)
    - 담당 강사 (student.teacher_id): 허용
    - 수강 담당 강사 (CourseEnrollment): 허용
    """
    if current_user.role == 'admin':
        return True
    if essay.user_id == current_user.user_id:
        return True
    if current_user.role == 'teacher' and essay.student:
        if essay.student.teacher_id == current_user.user_id:
            return True
        from app.models import CourseEnrollment, Course
        teacher_course_ids = [
            c.course_id for c in
            Course.query.filter_by(teacher_id=current_user.user_id).all()
        ]
        if teacher_course_ids:
            enrolled = CourseEnrollment.query.filter(
                CourseEnrollment.student_id == essay.student.student_id,
                CourseEnrollment.course_id.in_(teacher_course_ids),
                CourseEnrollment.status == 'active'
            ).first()
            if enrolled:
                return True
    return False


@essays_bp.route('/')
@login_required
def index():
    """첨삭 목록 (필터링, 검색, 정렬 지원)"""
    from app.models import EssayResult

    # 기본 쿼리 - 관리자/매니저는 모든 첨삭 조회, 강사는 본인이 생성하거나 담당 학생의 첨삭 조회
    if current_user.role in ('admin', 'manager') or (
            current_user.role_level and current_user.role_level <= 2):
        query = Essay.query
    else:
        from app.models.course import Course, CourseEnrollment
        # 강사 수업에 등록된 학생 ID 서브쿼리
        course_student_ids = db.session.query(CourseEnrollment.student_id).join(
            Course, CourseEnrollment.course_id == Course.course_id
        ).filter(Course.teacher_id == current_user.user_id).subquery()

        query = Essay.query.outerjoin(Student).filter(
            db.or_(
                Essay.user_id == current_user.user_id,
                Student.teacher_id == current_user.user_id,
                Student.student_id.in_(course_student_ids)
            )
        )

    # Phase 2: 필터링
    # 1. 학생별 필터
    student_filter = request.args.get('student_id', '').strip()
    if student_filter:
        query = query.filter_by(student_id=student_filter)

    # 2. 상태별 필터
    status_filter = request.args.get('status', '').strip()
    if status_filter:
        query = query.filter_by(status=status_filter)

    # 3. 등급별 필터
    grade_filter = request.args.get('grade', '').strip()
    if grade_filter:
        query = query.join(EssayResult).filter(EssayResult.final_grade == grade_filter)

    # 4. 검색 (제목 또는 원문)
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            db.or_(
                Essay.title.contains(search),
                Essay.original_text.contains(search)
            )
        )

    # Phase 2: 정렬
    sort_by = request.args.get('sort', 'date_desc')

    if sort_by == 'date_asc':
        query = query.order_by(Essay.created_at.asc())
    elif sort_by == 'date_desc':
        query = query.order_by(Essay.created_at.desc())
    elif sort_by == 'score_desc':
        query = query.join(EssayResult).order_by(EssayResult.total_score.desc())
    elif sort_by == 'score_asc':
        query = query.join(EssayResult).order_by(EssayResult.total_score.asc())
    elif sort_by == 'student':
        query = query.join(Student).order_by(Student.name.asc())
    else:
        query = query.order_by(Essay.created_at.desc())

    essays = query.all()

    # 필터 옵션용 데이터 - 관리자/매니저는 모든 학생, 강사는 본인 학생만
    if current_user.role in ('admin', 'manager') or (
            current_user.role_level and current_user.role_level <= 2):
        students = Student.query.filter_by(is_temp=False).order_by(Student.name).all()
    else:
        students = Student.query.filter_by(teacher_id=current_user.user_id, is_temp=False)\
            .order_by(Student.name).all()

    # 대시보드 통계 (관리자/매니저 전용)
    dashboard_stats = None
    if current_user.role in ('admin', 'manager') or (
            current_user.role_level and current_user.role_level <= 2):
        from datetime import datetime, timedelta
        now = datetime.utcnow()

        # 이번 주 월요일 00:00
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        # 이번 달 1일 00:00
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        week_all = Essay.query.filter(Essay.created_at >= week_start).all()
        month_all = Essay.query.filter(Essay.created_at >= month_start).all()

        dashboard_stats = {
            'week': {
                'total': len(week_all),
                'completed': sum(1 for e in week_all if e.status == 'completed'),
                'pending': sum(1 for e in week_all if e.status == 'draft'),
            },
            'month': {
                'total': len(month_all),
                'completed': sum(1 for e in month_all if e.status == 'completed'),
                'pending': sum(1 for e in month_all if e.status == 'draft'),
            },
        }

        # 강사 목록
        from app.models.user import User as UserModel
        teachers = UserModel.query.filter_by(role='teacher', is_active=True).order_by(UserModel.name).all()
        dashboard_stats['teachers'] = teachers

        # 선택된 강사별 통계
        selected_teacher_id = request.args.get('dashboard_teacher_id', '').strip()
        dashboard_stats['selected_teacher_id'] = selected_teacher_id
        dashboard_stats['teacher_stats'] = None

        if selected_teacher_id:
            from app.models.course import Course, CourseEnrollment
            course_student_ids = db.session.query(CourseEnrollment.student_id).join(
                Course, CourseEnrollment.course_id == Course.course_id
            ).filter(Course.teacher_id == selected_teacher_id).subquery()

            def _teacher_essays(since):
                return Essay.query.outerjoin(Student).filter(
                    Essay.created_at >= since,
                    db.or_(
                        Essay.user_id == selected_teacher_id,
                        Student.teacher_id == selected_teacher_id,
                        Student.student_id.in_(course_student_ids)
                    )
                ).all()

            t_week = _teacher_essays(week_start)
            t_month = _teacher_essays(month_start)
            dashboard_stats['teacher_stats'] = {
                'week': {
                    'total': len(t_week),
                    'completed': sum(1 for e in t_week if e.status == 'completed'),
                    'pending': sum(1 for e in t_week if e.status == 'draft'),
                },
                'month': {
                    'total': len(t_month),
                    'completed': sum(1 for e in t_month if e.status == 'completed'),
                    'pending': sum(1 for e in t_month if e.status == 'draft'),
                },
            }

    return render_template('essays/index.html',
                         essays=essays,
                         students=students,
                         student_filter=student_filter,
                         status_filter=status_filter,
                         grade_filter=grade_filter,
                         search=search,
                         sort_by=sort_by,
                         dashboard_stats=dashboard_stats)


@essays_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """새 첨삭 시작"""
    from app.models import Book, EssayBook

    form = NewEssayForm()

    # 학생 목록 로드 (임시 학생 제외)
    students = Student.query.filter_by(teacher_id=current_user.user_id, is_temp=False)\
        .order_by(Student.name).all()

    if not students:
        flash('먼저 학생을 등록해주세요.', 'warning')
        return redirect(url_for('students.new'))

    # 학생 선택 옵션 설정
    form.student_id.choices = [
        (s.student_id, f"{s.name} ({s.grade})")
        for s in students
    ]

    # 도서 목록 로드
    books = Book.query.order_by(Book.title).all()
    form.book_ids.choices = [
        (b.book_id, f"{b.title}" + (f" - {b.author}" if b.author else ""))
        for b in books
    ]

    if form.validate_on_submit():
        student = Student.query.get(form.student_id.data)

        if not student or student.teacher_id != current_user.user_id:
            flash('잘못된 학생 선택입니다.', 'error')
            return redirect(url_for('essays.new'))

        # MOMOAI 서비스 초기화
        service = MOMOAIService(Config.ANTHROPIC_API_KEY)

        # Essay 생성
        essay = service.create_essay(
            student_id=student.student_id,
            user_id=current_user.user_id,
            title=form.title.data,
            original_text=form.essay_text.data,
            grade=student.grade,
            notes=form.notes.data
        )

        # 파일 첨부 처리
        if form.attachment.data:
            file = form.attachment.data
            if file and file.filename:
                # 업로드 폴더 생성
                upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'essays')
                os.makedirs(upload_folder, exist_ok=True)

                # 안전한 파일명 생성
                original_filename = secure_filename(file.filename)
                file_ext = os.path.splitext(original_filename)[1]
                stored_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(upload_folder, stored_filename)

                # 파일 저장
                file.save(file_path)

                # DB에 정보 저장
                essay.attachment_filename = original_filename
                essay.attachment_path = os.path.join('essays', stored_filename)
                db.session.commit()

        # Phase 3: 참고 도서 연결
        if form.book_ids.data:
            for book_id in form.book_ids.data:
                essay_book = EssayBook(
                    essay_id=essay.essay_id,
                    book_id=book_id,
                    relation_type='reference'
                )
                db.session.add(essay_book)
            db.session.commit()

        # 백그라운드 스레드로 첨삭 처리
        essay_id_val = essay.essay_id
        student_name = student.name
        teacher_name = current_user.name
        api_key = Config.ANTHROPIC_API_KEY
        app = current_app._get_current_object()

        essay.status = 'processing'
        db.session.commit()

        def do_correction():
            with app.app_context():
                from app.models import db as _db, Essay as _Essay
                from app.essays.momoai_service import MOMOAIService as _Service
                essay_obj = _Essay.query.get(essay_id_val)
                if not essay_obj:
                    return
                try:
                    svc = _Service(api_key)
                    svc.process_essay(essay_obj, student_name, teacher_name)
                except Exception as e:
                    print(f'[첨삭 오류] {e}')
                    essay_obj.status = 'failed'
                    _db.session.commit()

        t = threading.Thread(target=do_correction, daemon=True)
        t.start()

        return redirect(url_for('essays.processing', essay_id=essay_id_val))

    return render_template('essays/new.html', form=form)


@essays_bp.route('/quick', methods=['GET', 'POST'])
@login_required
def quick():
    """학생 등록 없이 이름/학년만 입력하는 임시 첨삭"""
    GRADES = ['초1', '초2', '초3', '초4', '초5', '초6',
              '중1', '중2', '중3', '고1', '고2', '고3']

    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        grade        = request.form.get('grade', '').strip()
        title        = request.form.get('title', '').strip() or None
        essay_text   = request.form.get('essay_text', '').strip()
        notes        = request.form.get('notes', '').strip() or None

        # 유효성 검사
        if not student_name:
            flash('학생 이름을 입력해주세요.', 'error')
            return redirect(url_for('essays.quick'))
        if grade not in GRADES:
            flash('학년을 선택해주세요.', 'error')
            return redirect(url_for('essays.quick'))

        # 파일 첨부 처리
        attachment_filename = None
        attachment_path = None
        file = request.files.get('attachment')
        if file and file.filename:
            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'essays')
            os.makedirs(upload_folder, exist_ok=True)
            original_filename = secure_filename(file.filename)
            stored_filename = f"{uuid.uuid4().hex}{os.path.splitext(original_filename)[1]}"
            file.save(os.path.join(upload_folder, stored_filename))
            attachment_filename = original_filename
            attachment_path = os.path.join('essays', stored_filename)

        if not essay_text and not attachment_path:
            flash('글쓰기 내용을 입력하거나 파일을 첨부해주세요.', 'error')
            return redirect(url_for('essays.quick'))

        # 임시 학생 자동 생성
        temp_student = Student(
            teacher_id=current_user.user_id,
            name=student_name,
            grade=grade,
            is_temp=True
        )
        db.session.add(temp_student)
        db.session.flush()  # student_id 확보

        # Essay 생성
        from app.models import EssayNote
        import uuid as _uuid
        essay = Essay(
            student_id=temp_student.student_id,
            user_id=current_user.user_id,
            title=title,
            original_text=essay_text or '',
            grade=grade,
            status='processing'
        )
        db.session.add(essay)

        if notes:
            db.session.flush()
            db.session.add(EssayNote(
                essay_id=essay.essay_id,
                note_type='주의사항',
                content=notes
            ))

        if attachment_filename:
            essay.attachment_filename = attachment_filename
            essay.attachment_path = attachment_path

        db.session.commit()

        # 백그라운드 스레드로 첨삭 처리
        essay_id_val = essay.essay_id
        api_key = Config.ANTHROPIC_API_KEY
        app = current_app._get_current_object()

        def do_quick_correction():
            with app.app_context():
                from app.models import db as _db, Essay as _Essay
                from app.essays.momoai_service import MOMOAIService as _Service
                essay_obj = _Essay.query.get(essay_id_val)
                if not essay_obj:
                    return
                try:
                    service = _Service(api_key)
                    service.process_essay(essay_obj, student_name, current_user.name)
                except Exception as e:
                    print(f'[임시 첨삭 오류] {e}')
                    essay_obj.status = 'failed'
                    _db.session.commit()

        t = threading.Thread(target=do_quick_correction, daemon=True)
        t.start()

        return redirect(url_for('essays.processing', essay_id=essay.essay_id))

    return render_template('essays/quick.html', grades=[
        '초1', '초2', '초3', '초4', '초5', '초6',
        '중1', '중2', '중3', '고1', '고2', '고3'
    ])


@essays_bp.route('/processing/<essay_id>')
@login_required
def processing(essay_id):
    """첨삭 진행 중"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 완료되었으면 결과 페이지로 리다이렉트
    if essay.status in ['reviewing', 'completed']:
        return redirect(url_for('essays.result', essay_id=essay.essay_id))

    return render_template('essays/processing.html',
                         essay=essay,
                         student=essay.student)


@essays_bp.route('/result/<essay_id>')
@login_required
def result(essay_id):
    """첨삭 결과"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 처리 중이면 processing 페이지로
    if essay.status == 'processing':
        return redirect(url_for('essays.processing', essay_id=essay.essay_id))

    # 실패 처리
    if essay.status == 'failed':
        flash('첨삭 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
        return redirect(url_for('essays.index'))

    # 최신 버전 가져오기
    version = essay.latest_version

    if not version:
        flash('첨삭 결과를 찾을 수 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # HTML 내용 읽기
    try:
        with open(version.html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        flash(f'HTML 파일을 읽을 수 없습니다: {e}', 'error')
        return redirect(url_for('essays.index'))

    # 수정 요청 폼
    revision_form = RevisionRequestForm()

    # Phase 3: 참고 도서 가져오기
    from app.models import Book, EssayBook
    reference_books = db.session.query(Book)\
        .join(EssayBook, EssayBook.book_id == Book.book_id)\
        .filter(EssayBook.essay_id == essay.essay_id)\
        .order_by(Book.title)\
        .all()

    return render_template('essays/result.html',
                         essay=essay,
                         student=essay.student,
                         version=version,
                         html_content=html_content,
                         revision_form=revision_form,
                         reference_books=reference_books)


@essays_bp.route('/<essay_id>/regenerate', methods=['POST'])
@login_required
def regenerate(essay_id):
    """첨삭 재생성 초기화"""
    from flask import session

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    form = RevisionRequestForm()

    if form.validate_on_submit():
        revision_note = form.revision_note.data

        # 세션에 revision_note 저장
        session[f'revision_note_{essay_id}'] = revision_note

        # 상태를 processing으로 변경
        essay.status = 'processing'
        db.session.commit()

        # processing 페이지로 리다이렉트 (재생성 플래그 추가)
        return redirect(url_for('essays.processing', essay_id=essay.essay_id, regenerate='true'))

    flash('수정 요청 내용을 입력해주세요.', 'error')
    return redirect(url_for('essays.result', essay_id=essay.essay_id))


@essays_bp.route('/api/cancel/<essay_id>', methods=['POST'])
@login_required
def api_cancel(essay_id):
    """첨삭 취소 API (진행 중인 첨삭을 강제로 중단)"""
    essay = Essay.query.get_or_404(essay_id)

    if not _can_access_essay(essay):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    if essay.status != 'processing':
        return jsonify({'error': '진행 중인 첨삭이 아닙니다.'}), 400

    essay.status = 'failed'
    db.session.commit()

    return jsonify({'success': True})


@essays_bp.route('/api/regenerate/<essay_id>', methods=['POST'])
@login_required
def api_regenerate(essay_id):
    """첨삭 재생성 API (AJAX용)"""
    from flask import session

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    # 세션에서 revision_note 가져오기
    revision_note = session.get(f'revision_note_{essay_id}')
    if not revision_note:
        return jsonify({'error': '수정 요청 내용을 찾을 수 없습니다.'}), 400

    # 세션에서 미리 값 추출 (스레드는 요청 컨텍스트 없음)
    session.pop(f'revision_note_{essay_id}', None)

    student_name = essay.student.name
    teacher_name = current_user.name
    essay_id_val = essay.essay_id
    api_key = Config.ANTHROPIC_API_KEY
    app = current_app._get_current_object()

    def do_regenerate():
        with app.app_context():
            from app.models import db as _db, Essay as _Essay
            from app.essays.momoai_service import MOMOAIService as _Service
            essay_obj = _Essay.query.get(essay_id_val)
            if not essay_obj:
                return
            try:
                service = _Service(api_key)
                service.regenerate_essay(essay_obj, student_name, revision_note, teacher_name)
            except Exception as e:
                print(f'[재생성 오류] {e}')
                essay_obj.status = 'failed'
                _db.session.commit()

    t = threading.Thread(target=do_regenerate, daemon=True)
    t.start()

    return jsonify({'success': True, 'message': '재생성을 시작했습니다.'})


@essays_bp.route('/<essay_id>/finalize', methods=['POST'])
@login_required
def finalize(essay_id):
    """첨삭 완료"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # MOMOAI 서비스 초기화
    service = MOMOAIService(Config.ANTHROPIC_API_KEY)
    service.finalize_essay(essay)

    # 알림 생성
    Notification.create_notification(
        user_id=current_user.user_id,
        notification_type='essay_complete',
        title=f"첨삭이 완료되었습니다",
        message=f'{essay.student.name} 학생의 "{essay.title or "논술"}" 첨삭이 최종 완료되었습니다',
        link_url=url_for('essays.result', essay_id=essay.essay_id),
        related_entity_type='essay',
        related_entity_id=essay.essay_id
    )

    flash(f'{essay.student.name} 학생의 첨삭이 완료되었습니다.', 'success')
    return redirect(url_for('essays.result', essay_id=essay.essay_id))


@essays_bp.route('/<essay_id>/manual-correction', methods=['GET', 'POST'])
@login_required
def manual_correction(essay_id):
    """수동 첨삭 - 강사가 직접 첨삭 내용을 작성"""
    from app.models import EssayResult
    from datetime import datetime as _dt

    essay = Essay.query.get_or_404(essay_id)

    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    if request.method == 'POST':
        correction_content = request.form.get('correction_content', '').strip()
        total_score_str = request.form.get('total_score', '').strip()
        final_grade = request.form.get('final_grade', '').strip()
        action = request.form.get('action', 'save')  # 'save' or 'finalize'

        if not correction_content:
            flash('첨삭 내용을 입력해주세요.', 'error')
            return redirect(url_for('essays.manual_correction', essay_id=essay_id))

        # 첨부파일 검증 (이미지 + PDF, 최대 10개)
        uploaded_files = request.files.getlist('correction_attachments')
        allowed_exts = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf'}
        valid_files = []
        for f in uploaded_files[:10]:
            if f and f.filename:
                ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
                if ext in allowed_exts:
                    valid_files.append((f, ext))

        # 입력이 HTML이면 그대로, 아니면 whitespace-pre-wrap div로 래핑
        if correction_content.strip().startswith('<'):
            html_content = correction_content
        else:
            safe_content = correction_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_content = (
                '<div style="white-space: pre-wrap; font-family: \'Noto Sans KR\', sans-serif; '
                'line-height: 1.9; font-size: 15px; color: #222;">'
                + safe_content + '</div>'
            )

        # HTML 파일 저장
        html_folder = Path(current_app.config['HTML_FOLDER'])
        html_folder.mkdir(parents=True, exist_ok=True)

        if essay.versions:
            essay.current_version += 1
        new_version_num = essay.current_version

        filename = f"manual_{essay.essay_id}_v{new_version_num}.html"
        html_path = str(html_folder / filename)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # EssayVersion 생성
        version = EssayVersion(
            essay_id=essay.essay_id,
            version_number=new_version_num,
            html_content=html_content,
            html_path=html_path,
            revision_note='수동 첨삭'
        )
        db.session.add(version)
        db.session.flush()

        # 점수 파싱
        total_score = None
        if total_score_str:
            try:
                total_score = float(total_score_str)
            except ValueError:
                pass

        # EssayResult 생성 또는 업데이트
        if essay.result:
            essay.result.version_id = version.version_id
            essay.result.html_path = html_path
            if total_score is not None:
                essay.result.total_score = total_score
            if final_grade:
                essay.result.final_grade = final_grade
        else:
            result = EssayResult(
                essay_id=essay.essay_id,
                version_id=version.version_id,
                html_path=html_path,
                total_score=total_score,
                final_grade=final_grade or None
            )
            db.session.add(result)

        essay.status = 'reviewing'

        if action == 'finalize':
            essay.status = 'completed'
            essay.is_finalized = True
            essay.finalized_at = _dt.utcnow()
            essay.completed_at = _dt.utcnow()

        # 첨부파일 저장
        if valid_files:
            from app.models.essay import CorrectionAttachment
            attach_folder = Path(current_app.config['CORRECTION_ATTACHMENTS_FOLDER'])
            attach_folder.mkdir(parents=True, exist_ok=True)
            import uuid as _uuid
            for f, ext in valid_files:
                stored_name = f"{essay.essay_id}_{_uuid.uuid4().hex[:8]}_{secure_filename(f.filename)}"
                save_path = attach_folder / stored_name
                f.save(str(save_path))
                file_type = 'pdf' if ext == 'pdf' else 'image'
                attach = CorrectionAttachment(
                    essay_id=essay.essay_id,
                    version_id=version.version_id,
                    original_filename=f.filename,
                    stored_filename=stored_name,
                    file_path=str(save_path),
                    file_type=file_type,
                    file_size=save_path.stat().st_size
                )
                db.session.add(attach)

        db.session.commit()

        if action == 'finalize':
            flash(f'{essay.student.name} 학생의 수동 첨삭이 완료되었습니다.', 'success')
        else:
            flash('수동 첨삭이 저장되었습니다. 결과 페이지에서 최종 완료할 수 있습니다.', 'success')
        return redirect(url_for('essays.result', essay_id=essay.essay_id))

    # GET - 기존 최신 버전 내용 불러오기
    existing_content = ''
    if essay.latest_version:
        try:
            with open(essay.latest_version.html_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except Exception:
            existing_content = essay.latest_version.html_content or ''

    existing_score = ''
    existing_grade = ''
    if essay.result:
        existing_score = str(essay.result.total_score) if essay.result.total_score else ''
        existing_grade = essay.result.final_grade or ''

    return render_template('essays/manual_correction.html',
                           essay=essay,
                           student=essay.student,
                           existing_content=existing_content,
                           existing_score=existing_score,
                           existing_grade=existing_grade)


@essays_bp.route('/<essay_id>/start', methods=['POST'])
@login_required
def start_correction(essay_id):
    """학생이 제출한 글 첨삭 시작"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 상태 확인 - 완료/검토 중은 재생성 기능 사용
    if essay.status in ('reviewing', 'completed'):
        flash('이미 완료된 첨삭입니다. 결과 페이지에서 재생성 기능을 이용하세요.', 'warning')
        return redirect(url_for('essays.result', essay_id=essay.essay_id))

    # 백그라운드 스레드로 처리 시작
    essay.status = 'processing'
    db.session.commit()

    student_name = essay.student.name
    teacher_name = current_user.name
    essay_id_val = essay.essay_id
    api_key = Config.ANTHROPIC_API_KEY
    app = current_app._get_current_object()

    def do_correction():
        with app.app_context():
            from app.models import db as _db, Essay as _Essay
            from app.essays.momoai_service import MOMOAIService as _Service
            essay_obj = _Essay.query.get(essay_id_val)
            if not essay_obj:
                return
            try:
                service = _Service(api_key)
                service.process_essay(essay_obj, student_name, teacher_name)
            except Exception as e:
                print(f'[첨삭 오류] {e}')
                essay_obj.status = 'failed'
                _db.session.commit()

    t = threading.Thread(target=do_correction, daemon=True)
    t.start()

    return redirect(url_for('essays.processing', essay_id=essay.essay_id))


@essays_bp.route('/<essay_id>/version/<int:version_number>')
@login_required
def view_version(essay_id, version_number):
    """특정 버전 보기"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 버전 찾기
    version = EssayVersion.query.filter_by(
        essay_id=essay.essay_id,
        version_number=version_number
    ).first_or_404()

    # HTML 내용 읽기
    try:
        with open(version.html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        flash(f'HTML 파일을 읽을 수 없습니다: {e}', 'error')
        return redirect(url_for('essays.result', essay_id=essay.essay_id))

    # Phase 3: 참고 도서 가져오기
    from app.models import Book, EssayBook
    reference_books = db.session.query(Book)\
        .join(EssayBook, EssayBook.book_id == Book.book_id)\
        .filter(EssayBook.essay_id == essay.essay_id)\
        .order_by(Book.title)\
        .all()

    return render_template('essays/version.html',
                         essay=essay,
                         student=essay.student,
                         version=version,
                         html_content=html_content,
                         reference_books=reference_books)


# API 라우트 (AJAX 폴링용)
@essays_bp.route('/api/status/<essay_id>')
@login_required
def api_status(essay_id):
    """첨삭 상태 조회 API"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    return jsonify({
        'essay_id': essay.essay_id,
        'status': essay.status,
        'current_version': essay.current_version,
        'is_finalized': essay.is_finalized
    })


@essays_bp.route('/correction-attachment/<attachment_id>')
@login_required
def serve_correction_attachment(attachment_id):
    """강사 첨삭 첨부파일 서빙"""
    from app.models.essay import CorrectionAttachment
    attach = CorrectionAttachment.query.get_or_404(attachment_id)
    essay = attach.essay

    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    file_path = Path(attach.file_path)
    if not file_path.exists():
        flash('파일을 찾을 수 없습니다.', 'error')
        return redirect(url_for('essays.result', essay_id=essay.essay_id))

    return send_file(str(file_path), download_name=attach.original_filename, as_attachment=False)


@essays_bp.route('/download/<essay_id>')
@login_required
def download_attachment(essay_id):
    """첨삭 첨부 파일 다운로드"""
    import json

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    if not essay.attachment_path:
        flash('첨부 파일이 없습니다.', 'error')
        return redirect(url_for('essays.result', essay_id=essay_id))

    # 다중 파일 지원
    file_index = request.args.get('file_index', type=int)

    try:
        # JSON 배열인 경우 (다중 파일)
        if essay.attachment_path.startswith('['):
            paths = json.loads(essay.attachment_path)
            filenames = json.loads(essay.attachment_filename)

            if file_index is not None and 0 <= file_index < len(paths):
                file_path = paths[file_index]
                filename = filenames[file_index]
            else:
                flash('파일을 찾을 수 없습니다.', 'error')
                return redirect(url_for('essays.result', essay_id=essay_id))
        else:
            # 단일 파일 (하위 호환성)
            file_path = essay.attachment_path
            filename = essay.attachment_filename

        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_directory = os.path.dirname(os.path.join(upload_folder, file_path))
        file_name = os.path.basename(file_path)

        return send_from_directory(
            file_directory,
            file_name,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'파일 다운로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('essays.result', essay_id=essay_id))


@essays_bp.route('/print/<essay_id>')
@login_required
def print_essay(essay_id):
    """첨삭 결과 인쇄 전용 페이지"""
    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인 - 학생, 강사, 학부모, 관리자 모두 접근 가능
    has_permission = False

    if current_user.role == 'admin':
        has_permission = True
    elif current_user.role == 'teacher':
        has_permission = (essay.user_id == current_user.user_id)
    elif current_user.role == 'student':
        from app.models import Student
        student = Student.query.filter_by(email=current_user.email).first()
        if student:
            has_permission = (essay.student_id == student.student_id)
    elif current_user.role == 'parent':
        from app.models import ParentStudent
        linked_students = ParentStudent.query.filter_by(
            parent_id=current_user.user_id
        ).all()
        student_ids = [link.student_id for link in linked_students]
        has_permission = (essay.student_id in student_ids)

    if not has_permission:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 최신 버전 가져오기
    version = essay.latest_version

    if not version or not version.html_path:
        flash('첨삭 결과를 찾을 수 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # HTML 내용 읽기
    try:
        with open(version.html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        flash(f'첨삭 결과를 불러올 수 없습니다: {e}', 'error')
        return redirect(url_for('essays.index'))

    # 인쇄 전용 템플릿 렌더링
    return render_template('essays/print.html',
                         essay=essay,
                         student=essay.student,
                         html_content=html_content)


@essays_bp.route('/download-pdf/<essay_id>')
@login_required
def download_pdf(essay_id):
    """첨삭 결과 PDF 다운로드 (HTML을 PDF로 변환)"""
    from xhtml2pdf import pisa
    from pathlib import Path
    import io

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인 - 학생, 강사, 학부모, 관리자 모두 접근 가능
    has_permission = False

    if current_user.role == 'admin':
        has_permission = True
    elif current_user.role == 'teacher':
        # 강사는 자신이 담당한 첨삭만
        has_permission = (essay.user_id == current_user.user_id)
    elif current_user.role == 'student':
        # 학생은 자신의 첨삭만
        from app.models import Student
        student = Student.query.filter_by(email=current_user.email).first()
        if student:
            has_permission = (essay.student_id == student.student_id)
    elif current_user.role == 'parent':
        # 학부모는 자녀의 첨삭만
        from app.models import ParentStudent
        linked_students = ParentStudent.query.filter_by(
            parent_id=current_user.user_id
        ).all()
        student_ids = [link.student_id for link in linked_students]
        has_permission = (essay.student_id in student_ids)

    if not has_permission:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 최신 버전 가져오기
    version = essay.latest_version

    if not version or not version.html_path:
        flash('첨삭 결과를 찾을 수 없습니다.', 'error')
        return redirect(url_for('essays.result', essay_id=essay_id))

    try:
        # PDF 파일명 생성
        html_path = Path(version.html_path)
        pdf_filename = html_path.stem + '.pdf'
        pdf_folder = Path(current_app.config['PDF_FOLDER'])
        pdf_folder.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_folder / pdf_filename

        # HTML 파일이 존재하지 않으면 에러
        if not html_path.exists():
            flash('HTML 파일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('essays.result', essay_id=essay_id))

        # PDF가 이미 존재하고 HTML보다 최신이면 재사용
        if pdf_path.exists() and pdf_path.stat().st_mtime > html_path.stat().st_mtime:
            return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)

        # HTML 내용 읽기
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # HTML을 PDF로 변환
        with open(pdf_path, 'wb') as pdf_file:
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_file,
                encoding='utf-8'
            )

        if pisa_status.err:
            raise Exception('PDF 생성 중 오류가 발생했습니다.')

        # EssayResult에 PDF 경로 저장 (있으면)
        if essay.result:
            essay.result.pdf_path = str(pdf_path)
            db.session.commit()

        return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)

    except Exception as e:
        current_app.logger.error(f'PDF 생성 오류: {str(e)}')
        flash(f'PDF 생성 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('essays.result', essay_id=essay_id))


@essays_bp.route('/<essay_id>/view_submission')
@login_required
def view_submission(essay_id):
    """학생이 제출한 과제 원문 보기"""
    import json

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 첨부 파일 처리 (JSON 배열 또는 단일 파일)
    attachments = []
    if essay.attachment_filename:
        if essay.attachment_filename.startswith('['):
            # 다중 파일
            filenames = json.loads(essay.attachment_filename)
            attachments = [(idx, name) for idx, name in enumerate(filenames)]
        else:
            # 단일 파일 (하위 호환성)
            attachments = [(None, essay.attachment_filename)]

    # 이 과제의 OCR 기록 조회
    ocr_records = OCRHistory.query\
        .filter_by(essay_id=essay_id)\
        .order_by(OCRHistory.created_at.desc())\
        .all()

    return render_template('essays/view_submission.html',
                         essay=essay,
                         student=essay.student,
                         attachments=attachments,
                         ocr_records=ocr_records)


@essays_bp.route('/ocr')
@login_required
def ocr_index():
    """OCR 인식 메인 페이지"""
    # 최근 OCR 히스토리 조회
    recent_history = OCRHistory.query\
        .filter_by(user_id=current_user.user_id)\
        .order_by(OCRHistory.created_at.desc())\
        .limit(10)\
        .all()

    return render_template('essays/ocr_index.html',
                         recent_history=recent_history)


@essays_bp.route('/ocr/upload', methods=['GET', 'POST'])
@login_required
def ocr_upload():
    """직접 이미지 업로드하여 OCR 인식 (최대 10장)"""
    if request.method == 'POST':
        files = request.files.getlist('images')
        files = [f for f in files if f and f.filename]

        if not files:
            flash('이미지 파일을 선택해주세요.', 'error')
            return redirect(url_for('essays.ocr_upload'))

        if len(files) > 10:
            flash('최대 10장까지만 업로드할 수 있습니다.', 'error')
            return redirect(url_for('essays.ocr_upload'))

        ocr_service = OCRService()
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'ocr')
        os.makedirs(upload_folder, exist_ok=True)

        ocr_records = []
        error_files = []
        total_time = 0

        for file in files:
            # 파일 형식 확인 (이미지 + PDF)
            if not ocr_service.is_supported_image(file.filename) and \
               not file.filename.lower().endswith('.pdf'):
                error_files.append(f'{file.filename}: 지원되지 않는 형식')
                continue

            try:
                original_filename = secure_filename(file.filename)
                file_ext = os.path.splitext(original_filename)[1]
                stored_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(upload_folder, stored_filename)
                file.save(file_path)

                gemini_service = GeminiOCRService()
                extracted_text, summary, corrected_text, processing_time = \
                    gemini_service.extract_and_analyze(file_path)
                total_time += processing_time

                ocr_record = OCRHistory(
                    user_id=current_user.user_id,
                    original_filename=original_filename,
                    image_path=os.path.join('ocr', stored_filename),
                    extracted_text=extracted_text,
                    summary=summary,
                    corrected_text=corrected_text,
                    ocr_method='gemini',
                    processing_time=processing_time,
                    character_count=len(extracted_text)
                )
                db.session.add(ocr_record)
                ocr_records.append(ocr_record)

            except Exception as e:
                error_files.append(f'{file.filename}: {str(e)}')

        if ocr_records:
            db.session.commit()

        if error_files:
            flash(f'⚠️ 실패한 파일: {", ".join(error_files)}', 'warning')

        if not ocr_records:
            flash('모든 파일 처리에 실패했습니다.', 'error')
            return redirect(url_for('essays.ocr_upload'))

        if len(ocr_records) == 1:
            flash(f'✨ OCR 완료! (처리 시간: {total_time:.2f}초)', 'success')
            return redirect(url_for('essays.ocr_result', ocr_id=ocr_records[0].ocr_id))
        else:
            flash(f'✨ {len(ocr_records)}장 OCR 완료! (총 처리 시간: {total_time:.2f}초)', 'success')
            return redirect(url_for('essays.ocr_history'))

    return render_template('essays/ocr_upload.html')


@essays_bp.route('/ocr/<essay_id>/from_essay', methods=['GET', 'POST'])
@login_required
def ocr_from_essay(essay_id):
    """학생 과제의 첨부 파일에서 OCR 인식"""
    import json

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인
    if not _can_access_essay(essay):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.index'))

    # 첨부 파일 확인
    if not essay.attachment_path:
        flash('첨부 파일이 없습니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    # 첨부 파일 목록 가져오기
    attachments = []
    if essay.attachment_filename.startswith('['):
        filenames = json.loads(essay.attachment_filename)
        paths = json.loads(essay.attachment_path)
        attachments = [(idx, name, path) for idx, (name, path) in enumerate(zip(filenames, paths))]
    else:
        attachments = [(None, essay.attachment_filename, essay.attachment_path)]

    # 이미지 + PDF 파일 필터링 (Gemini는 PDF도 처리 가능)
    ocr_service = OCRService()
    image_attachments = [
        (idx, name, path) for idx, name, path in attachments
        if ocr_service.is_supported_image(name) or name.lower().endswith('.pdf')
    ]

    if not image_attachments:
        flash('OCR 가능한 파일이 없습니다. 이미지 또는 PDF 파일이 필요합니다.', 'error')
        return redirect(url_for('essays.view_submission', essay_id=essay_id))

    if request.method == 'POST':
        # 여러 파일 선택 지원
        file_indices_str = request.form.getlist('file_indices')

        if not file_indices_str:
            flash('파일을 선택해주세요.', 'error')
            return redirect(url_for('essays.ocr_from_essay', essay_id=essay_id))

        # 문자열을 정수로 변환 (빈 문자열은 None으로)
        file_indices = []
        for idx_str in file_indices_str:
            if idx_str == '':
                file_indices.append(None)
            else:
                file_indices.append(int(idx_str))

        # 선택된 파일들 찾기
        selected_files = []
        for idx, name, path in image_attachments:
            if idx in file_indices or (None in file_indices and idx is None):
                selected_files.append((name, path))

        if not selected_files:
            flash('선택한 파일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('essays.ocr_from_essay', essay_id=essay_id))

        try:
            ocr_records = []
            total_processing_time = 0
            success_count = 0
            error_files = []

            # 각 파일을 순차적으로 Gemini OCR 처리
            for idx, (filename, file_path) in enumerate(selected_files):
                try:
                    # 전체 파일 경로
                    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)

                    # Gemini OCR 사용 (각 이미지마다 새 인스턴스)
                    ocr_method = 'gemini'
                    summary = None
                    corrected_text = None

                    gemini_service = GeminiOCRService()
                    extracted_text, summary, corrected_text, processing_time = gemini_service.extract_and_analyze(full_path)
                    total_processing_time += processing_time

                    # 히스토리 저장
                    ocr_record = OCRHistory(
                        user_id=current_user.user_id,
                        essay_id=essay.essay_id,
                        original_filename=filename,
                        image_path=file_path,
                        extracted_text=extracted_text,
                        summary=summary,
                        corrected_text=corrected_text,
                        ocr_method=ocr_method,
                        processing_time=processing_time,
                        character_count=len(extracted_text)
                    )
                    db.session.add(ocr_record)
                    ocr_records.append(ocr_record)
                    success_count += 1

                except Exception as e:
                    error_msg = f"{filename}: {str(e)}"
                    error_files.append(error_msg)
                    # 첫 번째 에러는 즉시 사용자에게 표시
                    if len(error_files) == 1:
                        flash(f'🚨 Gemini OCR 에러 발생:\n{error_msg}', 'error')

            # 모든 성공한 레코드 커밋
            if success_count > 0:
                db.session.commit()

            # 결과 메시지
            if success_count > 0:
                if success_count == 1:
                    flash(f'✅ OCR 인식 완료! (처리 시간: {total_processing_time:.2f}초)', 'success')
                    return redirect(url_for('essays.ocr_result', ocr_id=ocr_records[0].ocr_id))
                else:
                    flash(f'✅ {success_count}개 파일 OCR 완료! (총 시간: {total_processing_time:.2f}초)', 'success')
                    if error_files:
                        flash(f'⚠️ 실패한 파일:\n' + '\n'.join(error_files), 'warning')
                    return redirect(url_for('essays.ocr_history'))
            else:
                # 모든 파일 실패 시
                flash(f'❌ 모든 파일 처리 실패:\n' + '\n'.join(error_files[:3]), 'error')  # 최대 3개만 표시
                return redirect(url_for('essays.ocr_from_essay', essay_id=essay_id))

        except Exception as e:
            flash(f'OCR 처리 중 오류가 발생했습니다: {str(e)}', 'error')
            return redirect(url_for('essays.ocr_from_essay', essay_id=essay_id))

    return render_template('essays/ocr_from_essay.html',
                         essay=essay,
                         student=essay.student,
                         image_attachments=image_attachments)


@essays_bp.route('/ocr/result/<int:ocr_id>')
@login_required
def ocr_result(ocr_id):
    """OCR 결과 보기"""
    ocr_record = OCRHistory.query.get_or_404(ocr_id)

    # 권한 확인
    if ocr_record.user_id != current_user.user_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('essays.ocr_index'))

    return render_template('essays/ocr_result.html',
                         ocr_record=ocr_record)


@essays_bp.route('/ocr/history')
@login_required
def ocr_history():
    """OCR 히스토리 전체 보기"""
    # 관리자는 모든 히스토리, 강사는 본인 히스토리만
    if current_user.role == 'admin':
        history = OCRHistory.query.order_by(OCRHistory.created_at.desc()).all()
    else:
        history = OCRHistory.query\
            .filter_by(user_id=current_user.user_id)\
            .order_by(OCRHistory.created_at.desc())\
            .all()

    return render_template('essays/ocr_history.html',
                         history=history)


@essays_bp.route('/ocr/<int:ocr_id>/add-to-essay', methods=['POST'])
@login_required
def add_ocr_to_essay(ocr_id):
    """OCR 텍스트를 과제에 추가"""
    ocr_record = OCRHistory.query.get_or_404(ocr_id)

    # 권한 확인
    if ocr_record.user_id != current_user.user_id and current_user.role != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    # OCR이 과제와 연결되어 있는지 확인
    if not ocr_record.essay_id:
        return jsonify({'success': False, 'message': '과제와 연결되지 않은 OCR입니다.'}), 400

    essay = Essay.query.get_or_404(ocr_record.essay_id)

    # 추가할 텍스트 (corrected_text 우선, 없으면 original_text)
    text_to_add = request.json.get('text') or ocr_record.corrected_text or ocr_record.extracted_text

    if not text_to_add:
        return jsonify({'success': False, 'message': '추가할 텍스트가 없습니다.'}), 400

    # 기존 내용에 추가
    if essay.original_text:
        essay.original_text += '\n\n--- OCR 추가 ---\n\n' + text_to_add
    else:
        essay.original_text = text_to_add

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'OCR 텍스트가 과제에 추가되었습니다.',
        'essay_id': essay.essay_id
    })


