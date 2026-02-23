# -*- coding: utf-8 -*-
"""학생 포털 라우트"""
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import desc, and_
from werkzeug.utils import secure_filename
import os
import uuid

from app.student_portal import student_bp
from app.models import db, Student, Course, CourseEnrollment, CourseSession, Attendance
from app.models.essay import Essay
from app.models.teacher_feedback import TeacherFeedback
from app.models.announcement import Announcement, AnnouncementRead
from app.models.notification import Notification
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.material import Material, MaterialDownload
from app.models.makeup_request import MakeupClassRequest
from app.models.teaching_material import TeachingMaterial, TeachingMaterialDownload
from app.models.class_board import ClassBoardPost
from app.models.video import Video, VideoView
from app.models.class_board import ClassBoardPost, ClassBoardComment
from app.utils.progress_tracker import ProgressTracker
from app.utils.decorators import requires_role
from app.utils.content_access import can_access_content, format_file_size, extract_youtube_video_id


@student_bp.route('/')
@login_required
@requires_role('student', 'admin')
def index():
    """학생 대시보드"""
    # 학생 정보 조회
    if current_user.role == 'student':
        # student 계정인 경우 user_id로 student 정보 찾기
        student = Student.query.filter_by(email=current_user.email).first()
        if not student:
            flash('학생 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('student.index'))
    else:
        # admin인 경우 첫 번째 학생으로 테스트
        student = Student.query.first()
        if not student:
            flash('등록된 학생이 없습니다.', 'error')
            return redirect(url_for('student.index'))

    # 수강 중인 수업 목록
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()

    # 최근 첨삭 기록
    recent_essays = Essay.query.filter_by(
        student_id=student.student_id
    ).order_by(desc(Essay.created_at)).limit(5).all()

    # 읽지 않은 공지사항 수
    all_announcements = Announcement.query.filter(
        Announcement.is_published == True
    ).all()

    # is_active는 property이므로 DB 쿼리 후 Python에서 필터링
    all_announcements = [a for a in all_announcements if a.is_active]

    # 학생이 읽은 공지사항 ID 목록
    read_announcement_ids = [r.announcement_id for r in AnnouncementRead.query.filter_by(
        user_id=current_user.user_id
    ).all()]

    # 읽지 않은 공지사항 필터링
    unread_announcements = [a for a in all_announcements if a.announcement_id not in read_announcement_ids]

    # 이번 주 출석 현황
    from datetime import timedelta
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    this_week_sessions = []
    for enrollment in enrollments:
        sessions = CourseSession.query.filter(
            and_(
                CourseSession.course_id == enrollment.course_id,
                CourseSession.session_date >= week_start,
                CourseSession.session_date <= week_end
            )
        ).all()

        for session in sessions:
            attendance = Attendance.query.filter_by(
                enrollment_id=enrollment.enrollment_id,
                session_id=session.session_id
            ).first()

            if attendance:
                this_week_sessions.append({
                    'session': session,
                    'attendance': attendance,
                    'course': enrollment.course
                })

    # 통계 계산
    total_essays = Essay.query.filter_by(student_id=student.student_id).count()
    completed_essays = Essay.query.filter_by(
        student_id=student.student_id,
        is_finalized=True
    ).count()

    # ===== 차트 데이터 생성 =====
    from sqlalchemy import func, extract
    from app.models.essay import EssayResult
    import json

    # 1. 월별 내 첨삭 수 추이 (최근 6개월)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    monthly_essays = db.session.query(
        extract('year', Essay.created_at).label('year'),
        extract('month', Essay.created_at).label('month'),
        func.count(Essay.essay_id).label('count')
    ).filter(
        Essay.student_id == student.student_id,
        Essay.created_at >= six_months_ago
    ).group_by('year', 'month')\
     .order_by('year', 'month').all()

    essay_labels = [f"{int(row.year)}-{int(row.month):02d}" for row in monthly_essays]
    essay_data = [row.count for row in monthly_essays]

    # 2. 내 평균 점수 추이 (최근 10개 완료된 첨삭)
    recent_scores = db.session.query(Essay, EssayResult)\
        .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
        .filter(
            Essay.student_id == student.student_id,
            EssayResult.total_score.isnot(None)
        ).order_by(Essay.completed_at.desc())\
        .limit(10).all()

    score_labels = [f"v{essay.current_version}" for essay, _ in reversed(recent_scores)]
    score_data = [float(result.total_score) for _, result in reversed(recent_scores)]

    # 3. 수업별 출석률 비교
    attendance_by_course = []
    for enrollment in enrollments:
        total = enrollment.attended_sessions + enrollment.absent_sessions + enrollment.late_sessions
        if total > 0:
            attendance_by_course.append({
                'course_name': enrollment.course.course_name,
                'rate': enrollment.attendance_rate
            })

    course_names = [item['course_name'] for item in attendance_by_course]
    attendance_rates = [item['rate'] for item in attendance_by_course]

    return render_template('student/index.html',
                         student=student,
                         enrollments=enrollments,
                         recent_essays=recent_essays,
                         unread_count=len(unread_announcements),
                         this_week_sessions=this_week_sessions,
                         total_essays=total_essays,
                         completed_essays=completed_essays,
                         essay_labels=json.dumps(essay_labels),
                         essay_data=json.dumps(essay_data),
                         score_labels=json.dumps(score_labels),
                         score_data=json.dumps(score_data),
                         course_names=json.dumps(course_names),
                         attendance_rates=json.dumps(attendance_rates))


@student_bp.route('/courses')
@login_required
@requires_role('student', 'admin')
def courses():
    """내 수업 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()

    return render_template('student/courses.html',
                         student=student,
                         enrollments=enrollments)


@student_bp.route('/courses/<course_id>')
@login_required
@requires_role('student', 'admin')
def course_detail(course_id):
    """수업 상세 정보"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)

    # 수강 확인
    enrollment = CourseEnrollment.query.filter_by(
        course_id=course_id,
        student_id=student.student_id,
        status='active'
    ).first()

    if not enrollment and current_user.role != 'admin':
        flash('수강하지 않는 수업입니다.', 'error')
        return redirect(url_for('student.courses'))

    # 출석 기록 조회
    attendances = Attendance.query.filter_by(
        enrollment_id=enrollment.enrollment_id
    ).join(CourseSession).order_by(desc(CourseSession.session_date)).all()

    # 클래스 게시판 글 조회 (고정글 우선, 최신순)
    board_posts = ClassBoardPost.query.filter_by(
        course_id=course_id
    ).order_by(
        ClassBoardPost.is_pinned.desc(),
        ClassBoardPost.created_at.desc()
    ).limit(10).all()

    return render_template('student/course_detail.html',
                         student=student,
                         course=course,
                         enrollment=enrollment,
                         attendances=attendances,
                         board_posts=board_posts)


@student_bp.route('/essays/new', methods=['GET', 'POST'])
@login_required
@requires_role('student', 'admin')
def submit_essay():
    """새 과제 제출"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 수강 중인 강사 목록 조회
    from app.models.course import Course, CourseEnrollment
    from app.models import User as UserModel
    enrolled_teachers = db.session.query(UserModel).join(
        Course, Course.teacher_id == UserModel.user_id
    ).join(
        CourseEnrollment, CourseEnrollment.course_id == Course.course_id
    ).filter(
        CourseEnrollment.student_id == student.student_id,
        CourseEnrollment.status == 'active'
    ).order_by(CourseEnrollment.enrolled_at.asc()).distinct().all()

    # 기본 강사: student.teacher_id 또는 가장 오래된 수강 강사
    default_teacher_id = student.teacher_id
    if not default_teacher_id and enrolled_teachers:
        oldest = db.session.query(CourseEnrollment).join(
            Course, Course.course_id == CourseEnrollment.course_id
        ).filter(
            CourseEnrollment.student_id == student.student_id,
            CourseEnrollment.status == 'active'
        ).order_by(CourseEnrollment.enrolled_at.asc()).first()
        if oldest:
            default_teacher_id = oldest.course.teacher_id

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content', '').strip()
        selected_teacher_id = request.form.get('teacher_id') or default_teacher_id

        # 제목은 필수
        if not title:
            flash('제목을 입력해주세요.', 'error')
            return redirect(url_for('student.submit_essay'))

        # 본문 또는 첨부파일 중 하나는 있어야 함
        has_attachments = 'attachments' in request.files and any(
            f.filename for f in request.files.getlist('attachments')
        )
        if not content and not has_attachments:
            flash('본문 내용을 입력하거나 파일을 첨부해주세요.', 'error')
            return redirect(url_for('student.submit_essay'))

        # 첨삭 생성
        essay = Essay(
            student_id=student.student_id,
            user_id=selected_teacher_id,
            title=title,
            original_text=content,
            grade=student.grade
        )
        db.session.add(essay)
        db.session.flush()  # essay_id 생성을 위해 flush

        # 다중 파일 첨부 처리
        if 'attachments' in request.files:
            import json
            files = request.files.getlist('attachments')
            uploaded_filenames = []
            uploaded_paths = []

            # 최대 10개 파일 제한
            if len(files) > 10:
                flash('최대 10개의 파일만 업로드할 수 있습니다.', 'error')
                return redirect(url_for('student.submit_essay'))

            for file in files:
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

                    # 리스트에 추가
                    uploaded_filenames.append(original_filename)
                    uploaded_paths.append(os.path.join('essays', stored_filename))

            # DB에 정보 저장 (JSON 형식)
            if uploaded_filenames:
                essay.attachment_filename = json.dumps(uploaded_filenames, ensure_ascii=False)
                essay.attachment_path = json.dumps(uploaded_paths)

        # 선택된 강사에게 알림 생성
        if selected_teacher_id:
            notification = Notification(
                user_id=selected_teacher_id,
                notification_type='essay_submitted',
                title='새 글쓰기 제출',
                message=f'{student.name} 학생이 "{title}" 글쓰기를 제출했습니다.',
                link_url=url_for('essays.index')
            )
            db.session.add(notification)

        db.session.commit()

        flash('첨삭이 성공적으로 제출되었습니다. 담당 강사에게 알림이 전송되었습니다.', 'success')
        return redirect(url_for('student.my_essays'))

    # 이전 제출 이력
    recent_essays = Essay.query.filter_by(
        student_id=student.student_id
    ).order_by(desc(Essay.created_at)).limit(10).all()

    return render_template('student/submit_essay.html',
                           student=student,
                           recent_essays=recent_essays,
                           enrolled_teachers=enrolled_teachers,
                           default_teacher_id=default_teacher_id)


@student_bp.route('/essays')
@login_required
@requires_role('student', 'admin')
def my_essays():
    """내 첨삭 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    essays = Essay.query.filter_by(
        student_id=student.student_id
    ).order_by(desc(Essay.created_at)).all()

    return render_template('student/my_essays.html',
                         student=student,
                         essays=essays)


@student_bp.route('/essays/<essay_id>')
@login_required
@requires_role('student', 'admin')
def view_essay(essay_id):
    """첨삭 보기"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    essay = Essay.query.get_or_404(essay_id)

    # 본인 첨삭인지 확인
    if essay.student_id != student.student_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.my_essays'))

    # 첨삭 결과가 완료된 경우 HTML 내용 읽기
    html_content = None
    version = None
    if essay.status in ['reviewing', 'completed'] and essay.is_finalized:
        version = essay.latest_version
        if version and version.html_path:
            try:
                with open(version.html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception as e:
                flash(f'첨삭 결과를 불러올 수 없습니다: {e}', 'error')

    # 참고 도서 가져오기
    from app.models import Book, EssayBook
    reference_books = []
    if essay.is_finalized:
        reference_books = db.session.query(Book)\
            .join(EssayBook, EssayBook.book_id == Book.book_id)\
            .filter(EssayBook.essay_id == essay.essay_id)\
            .order_by(Book.title)\
            .all()

    return render_template('student/view_essay.html',
                         student=student,
                         essay=essay,
                         version=version,
                         html_content=html_content,
                         reference_books=reference_books)


@student_bp.route('/attendance')
@login_required
@requires_role('student', 'admin')
def attendance():
    """학생 출결 현황"""
    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 학생의 모든 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id
    ).order_by(CourseEnrollment.enrolled_at.desc()).all()

    # 수업별 출결 정보
    course_attendance_data = []
    for enrollment in enrollments:
        course = enrollment.course

        # 이 enrollment의 모든 출석 기록
        attendance_records = Attendance.query.filter_by(
            enrollment_id=enrollment.enrollment_id
        ).join(CourseSession).order_by(CourseSession.session_date.desc()).all()

        # 출석 통계 계산
        total_sessions = len(attendance_records)
        present_count = sum(1 for a in attendance_records if a.status == 'present')
        late_count = sum(1 for a in attendance_records if a.status == 'late')
        absent_count = sum(1 for a in attendance_records if a.status == 'absent')
        excused_count = sum(1 for a in attendance_records if a.status == 'excused')

        # 출석률 계산
        if total_sessions > 0:
            attendance_rate = (present_count + late_count * 0.5) / total_sessions * 100
        else:
            attendance_rate = 0

        course_attendance_data.append({
            'enrollment': enrollment,
            'course': course,
            'attendance_records': attendance_records,
            'stats': {
                'total': total_sessions,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'rate': round(attendance_rate, 1)
            }
        })

    return render_template('student/attendance.html',
                         student=student,
                         course_attendance_data=course_attendance_data)


@student_bp.route('/announcements')
@login_required
@requires_role('student', 'admin')
def announcements():
    """공지사항 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 전체 공지사항
    all_announcements = Announcement.query.filter(
        Announcement.is_published == True
    ).order_by(desc(Announcement.created_at)).all()

    # is_active는 property이므로 DB 쿼리 후 Python에서 필터링
    all_announcements = [a for a in all_announcements if a.is_active]

    # 학생이 읽은 공지사항 ID 목록
    read_announcement_ids = [r.announcement_id for r in AnnouncementRead.query.filter_by(
        user_id=current_user.user_id
    ).all()]

    # 공지사항 분류
    announcements_with_status = []
    for announcement in all_announcements:
        # Tier 필터링
        if announcement.target_tiers and student.tier not in announcement.target_tiers.split(','):
            continue

        announcements_with_status.append({
            'announcement': announcement,
            'is_read': announcement.announcement_id in read_announcement_ids
        })

    return render_template('student/announcements.html',
                         student=student,
                         announcements=announcements_with_status)


@student_bp.route('/announcements/<announcement_id>')
@login_required
@requires_role('student', 'admin')
def view_announcement(announcement_id):
    """공지사항 상세"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    announcement = Announcement.query.get_or_404(announcement_id)

    # Tier 접근 권한 확인
    if announcement.target_tiers and student.tier not in announcement.target_tiers.split(','):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.announcements'))

    # 읽음 표시
    existing_read = AnnouncementRead.query.filter_by(
        announcement_id=announcement_id,
        user_id=current_user.user_id
    ).first()

    if not existing_read:
        announcement_read = AnnouncementRead(
            announcement_id=announcement_id,
            user_id=current_user.user_id
        )
        db.session.add(announcement_read)
        db.session.commit()

    return render_template('student/view_announcement.html',
                         student=student,
                         announcement=announcement)


@student_bp.route('/materials')
@login_required
@requires_role('student', 'admin')
def materials():
    """학습 자료 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 접근 가능한 자료 조회
    all_materials = Material.query.filter_by(is_published=True)\
        .order_by(Material.created_at.desc()).all()

    # 접근 가능 여부 필터링
    accessible_materials = []
    for material in all_materials:
        if material.can_access(current_user, student):
            accessible_materials.append(material)

    # 카테고리별 분류
    categories = {}
    for material in accessible_materials:
        category = material.category or 'general'
        if category not in categories:
            categories[category] = []
        categories[category].append(material)

    # 수강 중인 수업 목록
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()

    return render_template('student/materials.html',
                         student=student,
                         materials=accessible_materials,
                         categories=categories,
                         enrollments=enrollments)


@student_bp.route('/materials/<material_id>/download')
@login_required
@requires_role('student', 'admin')
def download_material(material_id):
    """학습 자료 다운로드"""
    from flask import current_app, send_from_directory
    import os

    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    material = Material.query.get_or_404(material_id)

    # 접근 권한 확인
    if not material.can_access(current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.materials'))

    # 다운로드 기록 저장
    download = MaterialDownload(
        material_id=material_id,
        user_id=current_user.user_id,
        student_id=student.student_id
    )
    db.session.add(download)

    # 다운로드 카운트 증가
    material.download_count += 1
    db.session.commit()

    # 파일 전송
    return send_from_directory(
        current_app.config['MATERIALS_FOLDER'],
        material.file_path,
        as_attachment=True,
        download_name=material.file_name
    )


# ==================== 과제 ====================

@student_bp.route('/assignments')
@login_required
@requires_role('student', 'admin')
def assignments():
    """과제 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 내 수업의 과제 목록
    my_enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()
    my_course_ids = [e.course_id for e in my_enrollments]

    # 수업별 과제: 전체 대상(target_student_id==None) 또는 나에게 지정된 과제
    assignments = Assignment.query.filter(
        db.or_(
            Assignment.course_id.in_(my_course_ids),
            Assignment.course_id == None
        ),
        db.or_(
            Assignment.target_student_id == None,
            Assignment.target_student_id == student.student_id
        ),
        Assignment.is_published == True
    ).order_by(Assignment.due_date.asc()).all()

    # 각 과제의 제출 상태 확인
    assignment_data = []
    for assignment in assignments:
        submission = assignment.get_submission_by_student(student.student_id)
        assignment_data.append({
            'assignment': assignment,
            'submission': submission,
            'status': submission.status if submission else 'not_started'
        })

    return render_template('student/assignments.html',
                         student=student,
                         assignment_data=assignment_data)


@student_bp.route('/assignments/<assignment_id>')
@login_required
@requires_role('student', 'admin')
def assignment_detail(assignment_id):
    """과제 상세"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    assignment = Assignment.query.get_or_404(assignment_id)

    # 내 제출물
    submission = assignment.get_submission_by_student(student.student_id)

    # 제출물이 없으면 생성
    if not submission:
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.student_id,
            status='draft'
        )
        db.session.add(submission)
        db.session.commit()

    return render_template('student/assignment_detail.html',
                         student=student,
                         assignment=assignment,
                         submission=submission)


@student_bp.route('/assignments/<assignment_id>/submit', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def submit_assignment(assignment_id):
    """과제 제출"""
    from flask import current_app
    from werkzeug.utils import secure_filename
    import os
    import uuid

    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    assignment = Assignment.query.get_or_404(assignment_id)
    submission = assignment.get_submission_by_student(student.student_id)

    if not submission:
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.student_id
        )
        db.session.add(submission)
        db.session.flush()

    # 제출 내용 업데이트
    submission.content = request.form.get('content', '')

    # 파일 처리
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            # 파일 저장 폴더 확인
            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'assignments')
            os.makedirs(upload_folder, exist_ok=True)

            # 안전한 파일명 생성
            original_filename = secure_filename(file.filename)
            file_ext = os.path.splitext(original_filename)[1]
            stored_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(upload_folder, stored_filename)

            # 파일 저장
            file.save(file_path)

            # DB에 파일 정보 저장
            submission.file_name = original_filename
            submission.file_path = os.path.join('assignments', stored_filename)

    # 제출 처리
    submission.submit()

    # 강사에게 알림
    if assignment.teacher:
        notification = Notification(
            user_id=assignment.teacher_id,
            notification_type='assignment_submitted',
            title=f'과제 제출: {student.name}',
            message=f'{student.name} 학생이 "{assignment.title}" 과제를 제출했습니다.',
            link_url=f'/teacher/assignments/{assignment_id}/submissions/{submission.submission_id}/grade',
            related_entity_type='assignment',
            related_entity_id=assignment_id
        )
        db.session.add(notification)

    db.session.commit()

    flash('과제가 제출되었습니다.', 'success')
    return redirect(url_for('student.assignment_detail', assignment_id=assignment_id))


@student_bp.route('/assignments/submissions/<submission_id>/download')
@login_required
@requires_role('student', 'admin')
def download_assignment_file(submission_id):
    """과제 제출 파일 다운로드"""
    from flask import current_app, send_from_directory
    import os

    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    submission = AssignmentSubmission.query.get_or_404(submission_id)

    # 권한 확인 (본인 제출물만)
    if submission.student_id != student.student_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.assignments'))

    if not submission.file_path:
        flash('첨부된 파일이 없습니다.', 'error')
        return redirect(url_for('student.assignment_detail', assignment_id=submission.assignment_id))

    # 파일 전송
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_directory = os.path.dirname(os.path.join(upload_folder, submission.file_path))
    file_name = os.path.basename(submission.file_path)

    return send_from_directory(
        file_directory,
        file_name,
        as_attachment=True,
        download_name=submission.file_name
    )


@student_bp.route('/progress')
@login_required
@requires_role('student', 'admin')
def progress():
    """학습 진도 추적"""
    import json

    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 진도 추적기 생성
    tracker = ProgressTracker(student.student_id)

    # 전체 진도
    overall_progress = tracker.get_overall_progress()

    # 수업별 진도
    course_progress = tracker.get_course_progress()

    # 주간 활동
    weekly_activity = tracker.get_weekly_activity(weeks=4)

    # 과제 현황
    assignment_status = tracker.get_assignment_status()

    # 학습 성과
    performance = tracker.get_performance_summary()

    # 차트 데이터: 수업별 진도율
    course_labels = [cp['course'].course_name for cp in course_progress]
    course_attendance = [cp['attendance_rate'] for cp in course_progress]
    course_assignments = [cp['assignment_completion'] for cp in course_progress]

    # 차트 데이터: 주간 활동
    sorted_weeks = sorted(weekly_activity.keys())
    weekly_labels = sorted_weeks
    weekly_attendance = [weekly_activity[w]['attendance'] for w in sorted_weeks]
    weekly_assignments = [weekly_activity[w]['assignments'] for w in sorted_weeks]
    weekly_essays = [weekly_activity[w]['essays'] for w in sorted_weeks]

    return render_template('student/progress.html',
                         student=student,
                         overall_progress=overall_progress,
                         course_progress=course_progress,
                         assignment_status=assignment_status,
                         performance=performance,
                         course_labels=json.dumps(course_labels),
                         course_attendance=json.dumps(course_attendance),
                         course_assignments=json.dumps(course_assignments),
                         weekly_labels=json.dumps(weekly_labels),
                         weekly_attendance=json.dumps(weekly_attendance),
                         weekly_assignments=json.dumps(weekly_assignments),
                         weekly_essays=json.dumps(weekly_essays))


@student_bp.route('/essays/<essay_id>/download')
@login_required
@requires_role('student', 'admin')
def download_essay_attachment(essay_id):
    """첨삭 첨부 파일 다운로드"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    essay = Essay.query.get_or_404(essay_id)

    # 권한 확인 (본인 글만)
    if essay.student_id != student.student_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.my_essays'))

    if not essay.attachment_path:
        flash('첨부된 파일이 없습니다.', 'error')
        return redirect(url_for('student.view_essay', essay_id=essay_id))

    try:
        import json
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_index = request.args.get('file_index', type=int)

        # 다중 파일 처리
        if essay.attachment_path.startswith('['):
            paths = json.loads(essay.attachment_path)
            filenames = json.loads(essay.attachment_filename)

            if file_index is not None and 0 <= file_index < len(paths):
                file_path = paths[file_index]
                filename = filenames[file_index]
            else:
                flash('잘못된 파일 인덱스입니다.', 'error')
                return redirect(url_for('student.view_essay', essay_id=essay_id))
        else:
            # 단일 파일 (하위 호환성)
            file_path = essay.attachment_path
            filename = essay.attachment_filename

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
        return redirect(url_for('student.view_essay', essay_id=essay_id))


# ==================== 보강수업 신청 ====================

@student_bp.route('/makeup-classes')
@login_required
@requires_role('student', 'admin')
def makeup_classes():
    """보강수업 신청 가능한 수업 목록"""
    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 보강신청 가능한 수업 조회 (같은 학년, makeup_class_allowed=True, 진행 중)
    available_courses = Course.query.filter(
        Course.grade == student.grade,
        Course.makeup_class_allowed == True,
        Course.status == 'active'
    ).order_by(Course.weekday, Course.start_time).all()

    # 본인의 신청 내역 조회 (최근 5건만)
    my_requests = MakeupClassRequest.query.filter_by(
        student_id=student.student_id
    ).order_by(MakeupClassRequest.request_date.desc()).limit(5).all()

    return render_template('student/makeup_classes.html',
                         student=student,
                         available_courses=available_courses,
                         my_requests=my_requests)


@student_bp.route('/makeup-classes/request/<course_id>', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def request_makeup_class(course_id):
    """보강수업 신청"""
    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)

    # 보강신청 가능 여부 확인
    if not course.makeup_class_allowed:
        flash('이 수업은 보강신청이 불가능합니다.', 'error')
        return redirect(url_for('student.makeup_classes'))

    # 학년 확인
    if course.grade != student.grade:
        flash('자신의 학년 수업만 신청할 수 있습니다.', 'error')
        return redirect(url_for('student.makeup_classes'))

    # 중복 신청 확인 (같은 수업에 대한 pending 신청이 있는지)
    existing_request = MakeupClassRequest.query.filter_by(
        student_id=student.student_id,
        requested_course_id=course_id,
        status='pending'
    ).first()

    if existing_request:
        flash('이미 해당 수업에 대한 보강신청이 진행 중입니다.', 'warning')
        return redirect(url_for('student.makeup_classes'))

    # 신청 사유
    reason = request.form.get('reason', '').strip()

    # 보강수업 신청 생성
    makeup_request = MakeupClassRequest(
        student_id=student.student_id,
        requested_course_id=course_id,
        reason=reason,
        requested_by=current_user.user_id,
        status='pending'
    )

    db.session.add(makeup_request)

    # 관리자에게 알림 생성
    from app.models import User
    from flask import url_for
    admins = User.query.filter(User.role_level <= 2).all()  # 관리자/매니저
    for admin in admins:
        notification = Notification(
            user_id=admin.user_id,
            notification_type='makeup_request',
            title='새로운 보강수업 신청',
            message=f'{student.name} 학생이 "{course.course_name}" 보강수업을 신청했습니다.',
            related_entity_type='makeup_request',
            related_entity_id=makeup_request.request_id,
            link_url=url_for('admin.makeup_requests', _external=False)
        )
        db.session.add(notification)

    db.session.commit()

    flash('보강수업 신청이 완료되었습니다. 관리자 승인을 기다려주세요.', 'success')
    return redirect(url_for('student.makeup_classes'))


@student_bp.route('/makeup-classes/cancel/<request_id>', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def cancel_makeup_request(request_id):
    """보강수업 신청 취소"""
    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    makeup_request = MakeupClassRequest.query.get_or_404(request_id)

    # 권한 확인
    if makeup_request.student_id != student.student_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.makeup_classes'))

    # pending 상태만 취소 가능
    if makeup_request.status != 'pending':
        flash('대기 중인 신청만 취소할 수 있습니다.', 'warning')
        return redirect(url_for('student.makeup_classes'))

    # 신청 삭제
    db.session.delete(makeup_request)
    db.session.commit()

    flash('보강수업 신청이 취소되었습니다.', 'info')
    return redirect(url_for('student.makeup_classes'))


@student_bp.route('/makeup-classes/history')
@login_required
@requires_role('student', 'admin')
def makeup_classes_history():
    """보강수업 신청 전체 이력"""
    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 전체 신청 내역 조회
    from app.models.makeup_request import MakeupClassRequest
    all_requests = MakeupClassRequest.query.filter_by(
        student_id=student.student_id
    ).order_by(MakeupClassRequest.request_date.desc()).all()

    # 상태별 통계
    pending_count = sum(1 for r in all_requests if r.status == 'pending')
    approved_count = sum(1 for r in all_requests if r.status == 'approved')
    rejected_count = sum(1 for r in all_requests if r.status == 'rejected')

    return render_template('student/makeup_classes_history.html',
                         student=student,
                         all_requests=all_requests,
                         pending_count=pending_count,
                         approved_count=approved_count,
                         rejected_count=rejected_count)


# ==================== 학습 교재 (Teaching Materials) ====================

@student_bp.route('/teaching-materials')
@login_required
@requires_role('student', 'admin')
def teaching_materials():
    """학습 교재 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 모든 공개된 교재 조회
    from datetime import date
    today = date.today()
    all_materials = TeachingMaterial.query.filter(
        TeachingMaterial.is_public == True,
        TeachingMaterial.publish_date <= today,
        TeachingMaterial.end_date >= today
    ).order_by(TeachingMaterial.created_at.desc()).all()

    # 접근 가능한 교재 필터링
    accessible_materials = []
    for material in all_materials:
        if can_access_content(material, current_user, student):
            accessible_materials.append(material)

    # 검색 및 필터
    search = request.args.get('search', '').strip()
    grade_filter = request.args.get('grade', '').strip()

    if search:
        accessible_materials = [m for m in accessible_materials if search.lower() in m.title.lower()]

    if grade_filter:
        accessible_materials = [m for m in accessible_materials if m.grade == grade_filter]

    return render_template('student/teaching_materials.html',
                         student=student,
                         materials=accessible_materials,
                         search=search,
                         grade_filter=grade_filter)


@student_bp.route('/teaching-materials/<material_id>')
@login_required
@requires_role('student', 'admin')
def teaching_material_detail(material_id):
    """교재 상세 정보"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    material = TeachingMaterial.query.get_or_404(material_id)

    # 접근 권한 확인
    if not can_access_content(material, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.teaching_materials'))

    # 파일 크기 포맷팅
    file_size_formatted = format_file_size(material.file_size)

    return render_template('student/teaching_material_detail.html',
                         student=student,
                         material=material,
                         file_size_formatted=file_size_formatted)


@student_bp.route('/teaching-materials/<material_id>/download')
@login_required
@requires_role('student', 'admin')
def download_teaching_material(material_id):
    """교재 다운로드"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    material = TeachingMaterial.query.get_or_404(material_id)

    # 접근 권한 확인
    if not can_access_content(material, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.teaching_materials'))

    # 다운로드 기록 저장
    download = TeachingMaterialDownload(
        material_id=material_id,
        user_id=current_user.user_id,
        student_id=student.student_id
    )
    db.session.add(download)

    # 다운로드 카운트 증가
    material.download_count += 1
    db.session.commit()

    # 파일 전송
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    file_directory = os.path.dirname(os.path.join(upload_folder, material.storage_path))
    file_name = os.path.basename(material.storage_path)

    return send_from_directory(
        file_directory,
        file_name,
        as_attachment=True,
        download_name=material.original_filename
    )


# ==================== 학습 동영상 (Videos) ====================

@student_bp.route('/teaching-videos')
@login_required
@requires_role('student', 'admin')
def teaching_videos():
    """학습 동영상 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 모든 공개된 동영상 조회
    from datetime import date
    today = date.today()
    all_videos = Video.query.filter(
        Video.is_public == True,
        Video.publish_date <= today,
        Video.end_date >= today
    ).order_by(Video.created_at.desc()).all()

    # 접근 가능한 동영상 필터링
    accessible_videos = []
    for video in all_videos:
        if can_access_content(video, current_user, student):
            accessible_videos.append(video)

    # 검색 및 필터
    search = request.args.get('search', '').strip()
    grade_filter = request.args.get('grade', '').strip()

    if search:
        accessible_videos = [v for v in accessible_videos if search.lower() in v.title.lower()]

    if grade_filter:
        accessible_videos = [v for v in accessible_videos if v.grade == grade_filter]

    return render_template('student/teaching_videos.html',
                         student=student,
                         videos=accessible_videos,
                         search=search,
                         grade_filter=grade_filter)


@student_bp.route('/teaching-videos/<video_id>')
@login_required
@requires_role('student', 'admin')
def teaching_video_player(video_id):
    """동영상 플레이어"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    video = Video.query.get_or_404(video_id)

    # 접근 권한 확인
    if not can_access_content(video, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.teaching_videos'))

    # 조회 기록 저장
    view = VideoView(
        video_id=video_id,
        user_id=current_user.user_id,
        student_id=student.student_id
    )
    db.session.add(view)

    # 조회 카운트 증가
    video.view_count += 1
    db.session.commit()

    # YouTube 비디오 ID 추출
    youtube_video_id = video.youtube_video_id or extract_youtube_video_id(video.youtube_url)

    return render_template('student/teaching_video_player.html',
                         student=student,
                         video=video,
                         youtube_video_id=youtube_video_id)


# ==================== 과제 보기 ====================

@student_bp.route('/homework')
@login_required
@requires_role('student', 'admin')
def my_assignments():
    """과제 보기 — 정식 Assignment + 수업 공지/과제 알림 통합"""
    student = Student.query.filter_by(user_id=current_user.user_id).first()
    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # ── 정식 과제 (Assignment 모델) ────────────────────────────
    my_course_ids = [
        e.course_id for e in
        CourseEnrollment.query.filter_by(student_id=student.student_id, status='active').all()
    ]
    formal_assignments = Assignment.query.filter(
        db.or_(
            Assignment.course_id.in_(my_course_ids) if my_course_ids else db.false(),
            Assignment.target_student_id == student.student_id
        ),
        db.or_(
            Assignment.target_student_id == None,
            Assignment.target_student_id == student.student_id
        ),
        Assignment.is_published == True
    ).order_by(Assignment.due_date.asc()).all()

    # 각 과제의 제출 상태
    assignment_data = []
    for a in formal_assignments:
        sub = a.get_submission_by_student(student.student_id)
        assignment_data.append({
            'assignment': a,
            'submission': sub,
            'status': sub.status if sub else 'not_started'
        })

    # ── 수업 공지/과제 알림 ─────────────────────────────────────
    notifications = Notification.query.filter(
        Notification.user_id == current_user.user_id,
        Notification.notification_type.in_(['homework_assignment', 'class_announcement'])
    ).order_by(Notification.created_at.desc()).all()

    # 읽음 처리
    unread = [n for n in notifications if not n.is_read]
    for n in unread:
        n.is_read = True
        n.read_at = datetime.utcnow()
    if unread:
        db.session.commit()

    return render_template('student/my_assignments.html',
                           notifications=notifications,
                           assignment_data=assignment_data,
                           student=student)


# ==================== 클래스 게시판 ====================

@student_bp.route('/class-board')
@login_required
@requires_role('student', 'admin')
def class_board():
    """내 수업 목록 (클래스 게시판용)"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 내가 수강하는 수업 목록
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).order_by(CourseEnrollment.enrolled_at.desc()).all()

    # 각 수업별 최근 게시글 통계
    courses_with_stats = []
    for enrollment in enrollments:
        course = enrollment.course
        post_count = ClassBoardPost.query.filter_by(course_id=course.course_id).count()
        latest_post = ClassBoardPost.query.filter_by(
            course_id=course.course_id
        ).order_by(ClassBoardPost.created_at.desc()).first()

        courses_with_stats.append({
            'course': course,
            'post_count': post_count,
            'latest_post': latest_post
        })

    return render_template('student/class_board.html',
                         student=student,
                         courses_with_stats=courses_with_stats)


@student_bp.route('/class-board/<course_id>')
@login_required
@requires_role('student', 'admin')
def class_board_posts(course_id):
    """수업 게시판 게시글 목록"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)

    # 수업 수강 여부 확인
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        course_id=course_id,
        status='active'
    ).first()

    if not enrollment and current_user.role != 'admin':
        flash('이 수업의 수강생만 접근할 수 있습니다.', 'error')
        return redirect(url_for('student.class_board'))

    # 게시글 목록 조회 (공지사항 고정 후 최신순)
    posts = ClassBoardPost.query.filter_by(
        course_id=course_id
    ).order_by(
        ClassBoardPost.is_pinned.desc(),
        ClassBoardPost.created_at.desc()
    ).all()

    return render_template('student/class_board_posts.html',
                         student=student,
                         course=course,
                         posts=posts)


@student_bp.route('/class-board/<course_id>/new', methods=['GET', 'POST'])
@login_required
@requires_role('student', 'admin')
def create_class_board_post(course_id):
    """게시글 작성"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)

    # 수업 수강 여부 확인
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        course_id=course_id,
        status='active'
    ).first()

    if not enrollment and current_user.role != 'admin':
        flash('이 수업의 수강생만 게시글을 작성할 수 있습니다.', 'error')
        return redirect(url_for('student.class_board'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'question')

        if not title or not content:
            flash('제목과 내용을 입력하세요.', 'error')
            return render_template('student/class_board_form.html',
                                 student=student,
                                 course=course,
                                 is_edit=False)

        # 게시글 생성
        post = ClassBoardPost(
            course_id=course_id,
            author_id=current_user.user_id,
            title=title,
            content=content,
            post_type=post_type
        )
        db.session.add(post)
        db.session.commit()

        flash('게시글이 등록되었습니다.', 'success')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post.post_id))

    return render_template('student/class_board_form.html',
                         student=student,
                         course=course,
                         is_edit=False)


@student_bp.route('/class-board/<course_id>/<post_id>')
@login_required
@requires_role('student', 'admin')
def class_board_post_detail(course_id, post_id):
    """게시글 상세"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)
    post = ClassBoardPost.query.get_or_404(post_id)

    # 수업 수강 여부 확인
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        course_id=course_id,
        status='active'
    ).first()

    if not enrollment and current_user.role != 'admin':
        flash('이 수업의 수강생만 접근할 수 있습니다.', 'error')
        return redirect(url_for('student.class_board'))

    # 조회수 증가 (본인 글 제외)
    if post.author_id != current_user.user_id:
        post.view_count += 1
        db.session.commit()

    return render_template('student/class_board_post_detail.html',
                         student=student,
                         course=course,
                         post=post)


@student_bp.route('/class-board/<course_id>/<post_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('student', 'admin')
def edit_class_board_post(course_id, post_id):
    """게시글 수정"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    course = Course.query.get_or_404(course_id)
    post = ClassBoardPost.query.get_or_404(post_id)

    # 수정 권한 확인
    if not post.can_edit(current_user):
        flash('수정 권한이 없습니다.', 'error')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'question')

        if not title or not content:
            flash('제목과 내용을 입력하세요.', 'error')
            return render_template('student/class_board_form.html',
                                 student=student,
                                 course=course,
                                 post=post,
                                 is_edit=True)

        post.title = title
        post.content = content
        post.post_type = post_type
        post.updated_at = datetime.utcnow()
        db.session.commit()

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    return render_template('student/class_board_form.html',
                         student=student,
                         course=course,
                         post=post,
                         is_edit=True)


@student_bp.route('/class-board/<course_id>/<post_id>/delete', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def delete_class_board_post(course_id, post_id):
    """게시글 삭제"""
    post = ClassBoardPost.query.get_or_404(post_id)

    # 삭제 권한 확인
    if not post.can_delete(current_user):
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'info')
    return redirect(url_for('student.class_board_posts', course_id=course_id))


@student_bp.route('/class-board/<course_id>/<post_id>/comment', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def add_class_board_comment(course_id, post_id):
    """댓글 작성"""
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    post = ClassBoardPost.query.get_or_404(post_id)

    # 수업 수강 여부 확인
    enrollment = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        course_id=course_id,
        status='active'
    ).first()

    if not enrollment and current_user.role != 'admin':
        flash('이 수업의 수강생만 댓글을 작성할 수 있습니다.', 'error')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    content = request.form.get('content', '').strip()

    if not content:
        flash('댓글 내용을 입력하세요.', 'error')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    # 댓글 생성
    comment = ClassBoardComment(
        post_id=post_id,
        author_id=current_user.user_id,
        content=content
    )
    db.session.add(comment)

    # 댓글 수 증가
    post.comment_count += 1
    db.session.commit()

    flash('댓글이 등록되었습니다.', 'success')
    return redirect(url_for('student.class_board_post_detail',
                          course_id=course_id,
                          post_id=post_id))


@student_bp.route('/class-board/comment/<comment_id>/delete', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def delete_class_board_comment(comment_id):
    """댓글 삭제"""
    comment = ClassBoardComment.query.get_or_404(comment_id)
    post = comment.post
    course_id = post.course_id

    # 삭제 권한 확인
    if not comment.can_delete(current_user):
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('student.class_board_post_detail',
                              course_id=course_id,
                              post_id=post.post_id))

    db.session.delete(comment)

    # 댓글 수 감소
    post.comment_count = max(0, post.comment_count - 1)
    db.session.commit()

    flash('댓글이 삭제되었습니다.', 'info')
    return redirect(url_for('student.class_board_post_detail',
                          course_id=course_id,
                          post_id=post.post_id))


# ==================== 데이터 내보내기 ====================

@student_bp.route('/export/my-attendance')
@login_required
@requires_role('student', 'admin')
def export_my_attendance():
    """내 출석 내역 Excel 내보내기"""
    from app.utils.export_utils import export_attendance_to_excel

    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 출석 데이터 조회
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id
    ).all()

    attendance_data = []
    for enrollment in enrollments:
        attendances = Attendance.query.filter_by(
            enrollment_id=enrollment.enrollment_id
        ).join(CourseSession).order_by(CourseSession.session_date.desc()).all()

        for attendance in attendances:
            session = CourseSession.query.get(attendance.session_id)
            attendance_data.append({
                'date': session.session_date.strftime('%Y-%m-%d'),
                'course_name': enrollment.course.course_name,
                'student_name': student.name,
                'status': attendance.status,
                'late_minutes': attendance.late_minutes if attendance.late_minutes else '-',
                'notes': attendance.notes or '-',
                'checked_at': attendance.checked_at.strftime('%Y-%m-%d %H:%M') if attendance.checked_at else '-'
            })

    return export_attendance_to_excel(attendance_data, course_name=f"{student.name} 학생")


@student_bp.route('/export/my-report')
@login_required
@requires_role('student', 'admin')
def export_my_report():
    """내 종합 리포트 Excel 내보내기"""
    from app.utils.export_utils import export_student_report_to_excel
    from app.models.essay import Essay

    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student.student_id
    ).order_by(Essay.created_at.desc()).all()

    # 출석 통계
    total_sessions = sum(e.total_sessions for e in enrollments)
    attended = sum(e.attended_sessions for e in enrollments)
    late = sum(e.late_sessions for e in enrollments)
    absent = sum(e.absent_sessions for e in enrollments)
    attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 0

    attendance_stats = {
        'total_sessions': total_sessions,
        'present': attended,
        'late': late,
        'absent': absent,
        'attendance_rate': attendance_rate
    }

    return export_student_report_to_excel(student, enrollments, essays, attendance_stats)


# ==================== PDF 내보내기 ====================

@student_bp.route('/export/my-report-pdf')
@login_required
@requires_role('student', 'admin')
def export_my_report_pdf():
    """내 성적표 PDF 내보내기"""
    from app.utils.pdf_utils import generate_student_report_card_pdf
    from app.models.essay import Essay

    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student.student_id
    ).order_by(Essay.created_at.desc()).all()

    # 출석 통계
    total_sessions = sum(e.total_sessions for e in enrollments)
    attended = sum(e.attended_sessions for e in enrollments)
    late = sum(e.late_sessions for e in enrollments)
    absent = sum(e.absent_sessions for e in enrollments)
    attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 0

    attendance_stats = {
        'total_sessions': total_sessions,
        'present': attended,
        'late': late,
        'absent': absent,
        'attendance_rate': attendance_rate
    }

    return generate_student_report_card_pdf(student, enrollments, essays, attendance_stats)

# ============================================================================
# 독서 논술 MBTI 테스트
# ============================================================================

@student_bp.route('/reading-mbti')
@login_required
@requires_role('student', 'admin')
def reading_mbti():
    """독서 논술 MBTI 테스트 메인 페이지"""
    from app.models.reading_mbti import ReadingMBTITest, ReadingMBTIResult

    student = Student.query.filter_by(user_id=current_user.user_id).first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 학년에 따라 적합한 테스트 선택 (초등: elementary, 그 외: standard)
    grade = student.grade or ''
    version = 'elementary' if grade.startswith('초') else 'standard'
    test = ReadingMBTITest.query.filter_by(is_active=True, version=version).first()

    if not test:
        flash('현재 진행 중인 테스트가 없습니다.', 'warning')
        return redirect(url_for('student.index'))

    # 학생의 최근 결과 가져오기
    latest_result = ReadingMBTIResult.query.filter_by(
        student_id=student.student_id
    ).order_by(desc(ReadingMBTIResult.created_at)).first()

    # 전체 결과 기록
    all_results = ReadingMBTIResult.query.filter_by(
        student_id=student.student_id
    ).order_by(desc(ReadingMBTIResult.created_at)).all()

    return render_template('student/reading_mbti/index.html',
                           test=test,
                           latest_result=latest_result,
                           all_results=all_results,
                           student=student)


@student_bp.route('/reading-mbti/take/<int:test_id>')
@login_required
@requires_role('student', 'admin')
def take_reading_mbti(test_id):
    """독서 논술 MBTI 테스트 응시 페이지"""
    from app.models.reading_mbti import ReadingMBTITest, ReadingMBTIQuestion

    student = Student.query.filter_by(user_id=current_user.user_id).first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 테스트 가져오기
    test = ReadingMBTITest.query.get_or_404(test_id)

    if not test.is_active:
        flash('이 테스트는 현재 비활성화 상태입니다.', 'warning')
        return redirect(url_for('student.reading_mbti'))

    # 질문 가져오기 (순서대로)
    questions = ReadingMBTIQuestion.query.filter_by(
        test_id=test_id
    ).order_by(ReadingMBTIQuestion.order).all()

    # 절대평가 질문과 비교 질문 분리
    absolute_questions = [q for q in questions if q.question_type == 'absolute']
    comparison_questions = [q for q in questions if q.question_type == 'comparison']

    return render_template('student/reading_mbti/take_test.html',
                           test=test,
                           absolute_questions=absolute_questions,
                           comparison_questions=comparison_questions,
                           student=student)


@student_bp.route('/reading-mbti/submit/<int:test_id>', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def submit_reading_mbti(test_id):
    """독서 논술 MBTI 테스트 제출 및 결과 계산"""
    from app.models.reading_mbti import (
        ReadingMBTITest,
        ReadingMBTIResponse,
        ReadingMBTIResult,
        ReadingMBTIType
    )
    from app.utils.mbti_calculator import (
        calculate_mbti_scores,
        determine_mbti_type,
        validate_responses
    )

    student = Student.query.filter_by(user_id=current_user.user_id).first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 테스트 가져오기
    test = ReadingMBTITest.query.get_or_404(test_id)

    # 응답 데이터 수집
    responses = {}

    # 45개 절대평가 문항
    for i in range(1, 46):
        key = f'q{i}'
        value = request.form.get(key)
        responses[key] = value

    # 5개 비교 문항
    for i in range(1, 6):
        key = f'comp{i}'
        value = request.form.get(key)
        responses[key] = value

    # 유효성 검증
    is_valid, error_message = validate_responses(responses)
    if not is_valid:
        flash(error_message, 'error')
        return redirect(url_for('student.take_reading_mbti', test_id=test_id))

    try:
        # 점수 계산
        scores = calculate_mbti_scores(responses)

        # 유형 결정
        read_type, speech_type, write_type, type_key = determine_mbti_type(scores)

        # 유형 정보 가져오기
        mbti_type = ReadingMBTIType.query.filter_by(type_key=type_key).first()

        if not mbti_type:
            flash(f'유형 정보를 찾을 수 없습니다: {type_key}', 'error')
            return redirect(url_for('student.reading_mbti'))

        # 응답 저장
        response_record = ReadingMBTIResponse(
            student_id=student.student_id,
            test_id=test_id,
            responses=responses
        )
        db.session.add(response_record)
        db.session.flush()  # response_id 생성

        # 결과 저장
        result = ReadingMBTIResult(
            response_id=response_record.response_id,
            student_id=student.student_id,
            test_id=test_id,
            type_id=mbti_type.type_id,
            scores=scores,
            read_type=read_type,
            speech_type=speech_type,
            write_type=write_type
        )
        db.session.add(result)
        db.session.commit()

        flash('테스트가 완료되었습니다! 결과를 확인하세요.', 'success')
        return redirect(url_for('student.view_mbti_result', result_id=result.result_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"MBTI 테스트 제출 오류: {e}")
        flash('테스트 제출 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
        return redirect(url_for('student.take_reading_mbti', test_id=test_id))


@student_bp.route('/reading-mbti/result/<int:result_id>')
@login_required
@requires_role('student', 'admin')
def view_mbti_result(result_id):
    """독서 논술 MBTI 테스트 결과 보기"""
    from app.models.reading_mbti import ReadingMBTIResult

    student = Student.query.filter_by(user_id=current_user.user_id).first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 결과 가져오기
    result = ReadingMBTIResult.query.get_or_404(result_id)

    # 본인의 결과인지 확인
    if result.student_id != student.student_id:
        flash('본인의 결과만 확인할 수 있습니다.', 'error')
        return redirect(url_for('student.reading_mbti'))

    return render_template('student/reading_mbti/result.html',
                           result=result,
                           student=student)

# ==================== 어휘퀴즈 ====================

@student_bp.route('/vocabulary-quiz')
@login_required
@requires_role('student', 'admin')
def vocabulary_quiz():
    """어휘퀴즈 메인 페이지"""
    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    return render_template('student/vocabulary_quiz/index.html',
                           student=student)


# ==================== 스키마퀴즈 ====================

@student_bp.route('/schema-quiz')
@login_required
@requires_role('student', 'admin')
def schema_quiz():
    """스키마퀴즈 메인 페이지"""
    from app.models.schema_quiz import SchemaQuizSession

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 최근 테스트 히스토리 가져오기 (최근 10개)
    recent_sessions = SchemaQuizSession.query.filter_by(
        student_id=student.student_id
    ).filter(
        SchemaQuizSession.completed_at.isnot(None)
    ).order_by(
        SchemaQuizSession.completed_at.desc()
    ).limit(10).all()

    return render_template('student/schema_quiz/index.html',
                           student=student,
                           recent_sessions=recent_sessions)

@student_bp.route('/vocabulary-quiz/start/<int:level>')
@login_required
@requires_role('student', 'admin')
def vocabulary_quiz_start(level):
    """어휘퀴즈 시작"""
    from app.models.vocabulary_quiz import VocabularyQuiz, VocabularyQuizSession

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 세션 생성
    session = VocabularyQuizSession(
        student_id=student.student_id,
        level=level,
        grade=student.grade
    )
    db.session.add(session)
    db.session.commit()

    return redirect(url_for('student.vocabulary_quiz_take', session_id=session.session_id))


@student_bp.route('/vocabulary-quiz/take/<session_id>')
@login_required
@requires_role('student', 'admin')
def vocabulary_quiz_take(session_id):
    """어휘퀴즈 풀이"""
    from app.models.vocabulary_quiz import VocabularyQuiz, VocabularyQuizSession, VocabularyQuizResult
    import json
    import random

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    session = VocabularyQuizSession.query.get_or_404(session_id)

    # 본인의 세션인지 확인
    if session.student_id != student.student_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('student.vocabulary_quiz'))

    # 해당 레벨의 문제 가져오기 (10문제)
    all_quizzes = VocabularyQuiz.query.filter_by(level=session.level).all()

    if not all_quizzes:
        flash('문제가 없습니다.', 'error')
        return redirect(url_for('student.vocabulary_quiz'))

    # 랜덤하게 10문제 선택 (문제가 10개 미만이면 전체)
    quiz_count = min(10, len(all_quizzes))
    selected_quizzes = random.sample(all_quizzes, quiz_count)

    # 현재 문제 인덱스 (쿼리 파라미터)
    current_index = int(request.args.get('q', 0))

    if current_index >= len(selected_quizzes):
        # 퀴즈 완료
        return redirect(url_for('student.vocabulary_quiz_result', session_id=session_id))

    current_quiz = selected_quizzes[current_index]

    # 선택지 파싱
    try:
        options = json.loads(current_quiz.options)
    except:
        options = [current_quiz.correct_answer, "오답1", "오답2", "오답3"]

    # 선택지 섞기
    random.shuffle(options)

    return render_template('student/vocabulary_quiz/take.html',
                           student=student,
                           session=session,
                           quiz=current_quiz,
                           options=options,
                           current_index=current_index,
                           total_count=len(selected_quizzes),
                           quiz_ids=[q.quiz_id for q in selected_quizzes])


@student_bp.route('/vocabulary-quiz/submit/<session_id>', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def vocabulary_quiz_submit(session_id):
    """어휘퀴즈 답안 제출"""
    from app.models.vocabulary_quiz import VocabularyQuiz, VocabularyQuizSession, VocabularyQuizResult
    from datetime import datetime

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        return jsonify({'success': False, 'message': '학생 정보를 찾을 수 없습니다.'})

    session = VocabularyQuizSession.query.get_or_404(session_id)

    quiz_id = request.form.get('quiz_id')
    answer = request.form.get('answer', '').strip()

    quiz = VocabularyQuiz.query.get_or_404(quiz_id)

    # 정답 확인
    is_correct = (answer == quiz.correct_answer)

    # 결과 저장
    result = VocabularyQuizResult(
        student_id=student.student_id,
        quiz_id=quiz_id,
        student_answer=answer,
        is_correct=is_correct
    )
    db.session.add(result)

    # 세션 통계 업데이트
    session.total_questions = (session.total_questions or 0) + 1
    if is_correct:
        session.correct_count = (session.correct_count or 0) + 1

    db.session.commit()

    return jsonify({'success': True, 'is_correct': is_correct})


@student_bp.route('/vocabulary-quiz/result/<session_id>')
@login_required
@requires_role('student', 'admin')
def vocabulary_quiz_result(session_id):
    """어휘퀴즈 결과"""
    from app.models.vocabulary_quiz import VocabularyQuizSession
    from datetime import datetime

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    session = VocabularyQuizSession.query.get_or_404(session_id)

    # 본인의 세션인지 확인
    if session.student_id != student.student_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('student.vocabulary_quiz'))

    # 점수 계산
    if session.total_questions and session.total_questions > 0:
        session.score = (session.correct_count / session.total_questions) * 100
        session.completed_at = datetime.utcnow()
        db.session.commit()

    return render_template('student/vocabulary_quiz/result.html',
                           student=student,
                           session=session)


# ==================== 스키마퀴즈 라우트 ====================

@student_bp.route('/schema-quiz/start/<subject>')
@login_required
@requires_role('student', 'admin')
def schema_quiz_start(subject):
    """스키마퀴즈 시작"""
    from app.models.schema_quiz import SchemaQuiz, SchemaQuizSession

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    # 세션 생성
    session = SchemaQuizSession(
        student_id=student.student_id,
        subject=subject,
        grade=student.grade
    )
    db.session.add(session)
    db.session.commit()

    return redirect(url_for('student.schema_quiz_take', session_id=session.session_id))


@student_bp.route('/schema-quiz/take/<session_id>')
@login_required
@requires_role('student', 'admin')
def schema_quiz_take(session_id):
    """스키마퀴즈 풀이"""
    from app.models.schema_quiz import SchemaQuiz, SchemaQuizSession, SchemaQuizResult
    from app.utils.korean_utils import get_chosung
    import random

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    session = SchemaQuizSession.query.get_or_404(session_id)

    # 본인의 세션인지 확인
    if session.student_id != student.student_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('student.schema_quiz'))

    # 해당 주제의 문제 가져오기 (10문제)
    all_quizzes = SchemaQuiz.query.filter_by(subject=session.subject).all()

    if not all_quizzes:
        flash('문제가 없습니다.', 'error')
        return redirect(url_for('student.schema_quiz'))

    # 랜덤하게 10문제 선택
    quiz_count = min(10, len(all_quizzes))
    selected_quizzes = random.sample(all_quizzes, quiz_count)

    # 현재 문제 인덱스
    current_index = int(request.args.get('q', 0))

    if current_index >= len(selected_quizzes):
        # 퀴즈 완료
        return redirect(url_for('student.schema_quiz_result', session_id=session_id))

    current_quiz = selected_quizzes[current_index]

    # 초성 힌트 생성 (정답 용어의 초성)
    chosung_hint = get_chosung(current_quiz.term)

    return render_template('student/schema_quiz/take.html',
                           student=student,
                           session=session,
                           quiz=current_quiz,
                           chosung_hint=chosung_hint,
                           current_index=current_index,
                           total_count=len(selected_quizzes),
                           quiz_ids=[q.quiz_id for q in selected_quizzes])


@student_bp.route('/schema-quiz/submit/<session_id>', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def schema_quiz_submit(session_id):
    """스키마퀴즈 답안 제출"""
    from app.models.schema_quiz import SchemaQuiz, SchemaQuizSession, SchemaQuizResult
    from app.utils.korean_utils import check_answer_similarity
    from datetime import datetime

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        return jsonify({'success': False, 'message': '학생 정보를 찾을 수 없습니다.'})

    session = SchemaQuizSession.query.get_or_404(session_id)

    quiz_id = request.form.get('quiz_id')
    answer = request.form.get('answer', '').strip()

    quiz = SchemaQuiz.query.get_or_404(quiz_id)

    # 정답 확인 (용어와 비교)
    is_correct = check_answer_similarity(answer, quiz.term)

    # 결과 저장
    result = SchemaQuizResult(
        student_id=student.student_id,
        quiz_id=quiz_id,
        session_id=session_id,
        student_answer=answer,
        is_correct=is_correct
    )
    db.session.add(result)

    # 세션 통계 업데이트
    session.total_questions = (session.total_questions or 0) + 1
    if is_correct:
        session.correct_count = (session.correct_count or 0) + 1

    db.session.commit()

    return jsonify({'success': True, 'is_correct': is_correct})


@student_bp.route('/schema-quiz/result/<session_id>')
@login_required
@requires_role('student', 'admin')
def schema_quiz_result(session_id):
    """스키마퀴즈 결과"""
    from app.models.schema_quiz import SchemaQuizSession, SchemaQuizResult
    from datetime import datetime

    if current_user.role == 'student':
        student = Student.query.filter_by(user_id=current_user.user_id).first()
    else:
        student = Student.query.first()

    if not student:
        flash('학생 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('student.index'))

    session = SchemaQuizSession.query.get_or_404(session_id)

    # 본인의 세션인지 확인
    if session.student_id != student.student_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('student.schema_quiz'))

    # 점수 계산
    if session.total_questions and session.total_questions > 0:
        session.score = (session.correct_count / session.total_questions) * 100
        session.completed_at = datetime.utcnow()
        db.session.commit()

    # 이 세션의 모든 결과 가져오기 (답안 비교용)
    results = SchemaQuizResult.query.filter_by(
        session_id=session_id
    ).order_by(SchemaQuizResult.attempted_at).all()

    return render_template('student/schema_quiz/result.html',
                           student=student,
                           session=session,
                           results=results)


@student_bp.route('/weekly-evaluation')
@login_required
@requires_role('student', 'admin')
def weekly_evaluation():
    """학생 본인의 주간평가 리포트"""
    from app.models.ace_evaluation import WeeklyEvaluation
    from datetime import date, timedelta

    # 학생 정보 조회
    if current_user.role == 'student':
        student = Student.query.filter_by(email=current_user.email).first_or_404()
    else:
        # 관리자의 경우 student_id 파라미터 필요
        student_id = request.args.get('student_id')
        if not student_id:
            flash('학생 ID가 필요합니다.', 'error')
            return redirect(url_for('student.index'))
        student = Student.query.get_or_404(student_id)

    # 기간 필터링
    period = request.args.get('period', 'all')

    query = WeeklyEvaluation.query.filter_by(student_id=student.student_id)

    if period == '3months':
        start_date = date.today() - timedelta(days=90)
        query = query.filter(WeeklyEvaluation.eval_date >= start_date)
    elif period == '6months':
        start_date = date.today() - timedelta(days=180)
        query = query.filter(WeeklyEvaluation.eval_date >= start_date)
    elif period == '1year':
        start_date = date.today() - timedelta(days=365)
        query = query.filter(WeeklyEvaluation.eval_date >= start_date)

    # 모든 평가 데이터 (날짜순)
    evaluations = query.order_by(WeeklyEvaluation.eval_date.asc()).all()

    # 통계 계산
    total_count = len(evaluations)
    avg_score = round(sum(e.score for e in evaluations) / total_count, 1) if total_count > 0 else 0
    avg_participation = round(sum(e.participation_score for e in evaluations) / total_count, 1) if total_count > 0 else 0
    avg_understanding = round(sum(e.understanding_score for e in evaluations) / total_count, 1) if total_count > 0 else 0

    # 최근 성장률 계산
    growth_rate = 0
    if total_count >= 10:
        recent_5 = evaluations[-5:]
        previous_5 = evaluations[-10:-5]
        recent_avg = sum(e.score for e in recent_5) / 5
        previous_avg = sum(e.score for e in previous_5) / 5
        growth_rate = round(((recent_avg - previous_avg) / previous_avg) * 100, 1) if previous_avg > 0 else 0
    elif total_count >= 2:
        recent_avg = evaluations[-1].score
        first_avg = evaluations[0].score
        growth_rate = round(((recent_avg - first_avg) / first_avg) * 100, 1) if first_avg > 0 else 0

    # 최고/최저 점수
    max_score = max(e.score for e in evaluations) if evaluations else 0
    min_score = min(e.score for e in evaluations) if evaluations else 0

    return render_template('student/weekly_evaluation.html',
                         student=student,
                         evaluations=evaluations,
                         total_count=total_count,
                         avg_score=avg_score,
                         avg_participation=avg_participation,
                         avg_understanding=avg_understanding,
                         growth_rate=growth_rate,
                         max_score=max_score,
                         min_score=min_score,
                         period=period)


# ==================== 과제/공지 답글 ====================

@student_bp.route('/homework/<notification_id>/reply', methods=['POST'])
@login_required
@requires_role('student', 'admin')
def reply_to_homework(notification_id):
    """과제/공지에 답글 달기"""
    from app.models.notification import Notification
    from app.models.notification_reply import NotificationReply

    notification = Notification.query.get_or_404(notification_id)

    # 본인 알림인지 확인
    if notification.user_id != current_user.user_id and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('student.my_assignments'))

    content = request.form.get('content', '').strip()
    if not content:
        flash('답글 내용을 입력해주세요.', 'error')
        return redirect(url_for('student.my_assignments'))

    # 답글 저장
    reply = NotificationReply(
        notification_id=notification_id,
        author_id=current_user.user_id,
        content=content
    )
    db.session.add(reply)

    # 강사에게 알림 발송
    teacher_user_id = notification.related_user_id
    if teacher_user_id:
        teacher_notification = Notification(
            user_id=teacher_user_id,
            notification_type='homework_reply',
            title=f'[답글] {notification.title}',
            message=f'{current_user.name} 학생이 과제에 답글을 달았습니다: {content[:50]}{"..." if len(content) > 50 else ""}',
            related_user_id=current_user.user_id,
            related_entity_type='notification',
            related_entity_id=notification_id,
            link_url=url_for('teacher.class_message_detail', notification_id=notification_id, _external=False)
        )
        db.session.add(teacher_notification)

    db.session.commit()
    flash('답글이 등록되었습니다.', 'success')
    return redirect(url_for('student.my_assignments'))


# ==================== 내가 만든 질문 (하크니스) ====================

@student_bp.route('/my-questions')
@login_required
@requires_role('student', 'admin')
def my_harkness_questions():
    """내가 작성한 하크니스 게시글 목록"""
    from app.models.harkness_board import HarknessPost
    posts = HarknessPost.query\
        .filter_by(author_id=current_user.user_id)\
        .order_by(HarknessPost.created_at.desc()).all()
    return render_template('student/my_harkness_questions.html', posts=posts)
