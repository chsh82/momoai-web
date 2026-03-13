# -*- coding: utf-8 -*-
"""관리자 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func, case
from werkzeug.utils import secure_filename
import os
import uuid
import json

from app.admin import admin_bp
from app.admin.forms import CourseForm, EnrollmentForm, PaymentForm, AnnouncementForm, TeachingMaterialForm, VideoForm
from app.models import db, User, Student, Course, CourseEnrollment, CourseSession, Attendance, Payment, ParentStudent
from app.models.announcement import Announcement, AnnouncementRead
from app.models.notification import Notification
from app.models.teaching_material import TeachingMaterial, TeachingMaterialDownload, TeachingMaterialFile
from app.models.book import Book
from app.models.video import Video, VideoView
from app.models.parent_link_request import ParentLinkRequest
from app.utils.decorators import requires_permission_level
from app.utils.content_access import extract_youtube_video_id, format_file_size
from app.utils.course_utils import (
    generate_course_sessions,
    enroll_student_to_course,
    calculate_tuition_amount,
    get_course_statistics,
    update_enrollment_attendance_stats
)


@admin_bp.route('/')
@login_required
@requires_permission_level(2)  # 매니저 이상
def index():
    """관리자 대시보드 - 주간/월간"""
    from app.models.essay import Essay
    from app.models.parent_link_request import ParentLinkRequest
    from app.models.parent_student import ParentStudent
    from app.models.makeup_request import MakeupClassRequest
    from sqlalchemy import func, extract, case
    from datetime import timedelta, date
    import json

    today = date.today()

    # 이번 주 시작/끝 (월요일 시작)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # 이번 달 시작/끝
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # === KPI 카드 데이터 ===

    # 1. 진행 중인 수업
    total_courses = Course.query.filter(
        Course.end_date >= today,
        Course.status != 'cancelled'
    ).count()

    # 2. 전체 학생
    total_students = Student.query.count()

    # 3. 강사 수
    total_teachers = User.query.filter_by(role='teacher').count()

    # 4. 이번 주 수업 (세션 수)
    weekly_sessions = CourseSession.query.filter(
        CourseSession.session_date >= week_start,
        CourseSession.session_date <= week_end
    ).count()

    # 5. 평균 출석률 (이번 달)
    monthly_attendance = db.session.query(
        func.count(Attendance.attendance_id).label('total'),
        func.sum(case((Attendance.status == 'present', 1), else_=0)).label('present')
    ).join(CourseSession).filter(
        CourseSession.session_date >= month_start,
        CourseSession.session_date <= month_end
    ).first()

    attendance_rate = 0
    if monthly_attendance and monthly_attendance.total > 0:
        attendance_rate = round((monthly_attendance.present / monthly_attendance.total) * 100, 1)

    # 6. 대기 중 알림
    pending_parent_links = ParentLinkRequest.query.filter_by(status='pending').count()
    pending_makeup_requests = MakeupClassRequest.query.filter_by(status='pending').count()
    pending_notifications = pending_parent_links + pending_makeup_requests

    # 7. 학부모 연결
    total_parent_links = ParentStudent.query.count()

    # 8. 첨삭 현황
    essays_pending = Essay.query.filter_by(status='draft').count()
    essays_processing = Essay.query.filter_by(status='processing').count()
    essays_completed = Essay.query.filter(Essay.status.in_(['reviewing', 'completed'])).count()

    # === 차트 데이터 ===

    # 차트 1: 학생 수 증감 추이 (최근 6개월)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    monthly_students = db.session.query(
        extract('year', Student.created_at).label('year'),
        extract('month', Student.created_at).label('month'),
        func.count(Student.student_id).label('count')
    ).filter(Student.created_at >= six_months_ago)\
     .group_by('year', 'month')\
     .order_by('year', 'month').all()

    student_labels = [f"{int(row.year)}-{int(row.month):02d}" for row in monthly_students]
    student_data = [row.count for row in monthly_students]

    # 차트 2: 수업별 수강생 분포 (TOP 10)
    course_enrollments = db.session.query(
        Course.course_name,
        func.count(CourseEnrollment.enrollment_id).label('count')
    ).join(CourseEnrollment, Course.course_id == CourseEnrollment.course_id)\
     .filter(CourseEnrollment.status == 'active')\
     .group_by(Course.course_id, Course.course_name)\
     .order_by(func.count(CourseEnrollment.enrollment_id).desc())\
     .limit(10).all()

    enrollment_labels = [row.course_name[:20] + '...' if len(row.course_name) > 20 else row.course_name
                        for row in course_enrollments]
    enrollment_data = [row.count for row in course_enrollments]

    # 차트 3: 첨삭 현황 (상태별)
    essay_status_data = {
        '대기': essays_pending,
        '처리중': essays_processing,
        '완료': essays_completed
    }

    # 최근 중요 알림/활동
    recent_parent_requests = ParentLinkRequest.query.filter_by(status='pending')\
        .order_by(ParentLinkRequest.created_at.desc()).limit(5).all()
    recent_makeup_requests = MakeupClassRequest.query.filter_by(status='pending')\
        .order_by(MakeupClassRequest.created_at.desc()).limit(5).all()

    # === 주간 추가 통계 ===
    from app.models.consultation import ConsultationRecord

    # 신규문의: 이번 주 신규상담 기록 수
    weekly_new_consultations = ConsultationRecord.query.filter(
        ConsultationRecord.major_category == '신규상담',
        ConsultationRecord.consultation_date >= week_start,
        ConsultationRecord.consultation_date <= week_end
    ).count()

    # 신규생: 이번 주 새로 가입한 학생 수
    weekly_new_students = Student.query.filter(
        Student.created_at >= datetime.combine(week_start, datetime.min.time()),
        Student.created_at <= datetime.combine(week_end, datetime.max.time())
    ).count()

    # 휴퇴원생: 이번 주 상태가 leave/withdrawn으로 변경된 학생 수
    try:
        weekly_withdrawn = Student.query.filter(
            Student.status.in_(['leave', 'withdrawn']),
            Student.status_changed_at >= datetime.combine(week_start, datetime.min.time()),
            Student.status_changed_at <= datetime.combine(week_end, datetime.max.time())
        ).count()
    except Exception:
        weekly_withdrawn = 0

    # 전체강좌: 취소되지 않은 전체 강좌 수
    total_all_courses = Course.query.filter(Course.status != 'cancelled').count()

    return render_template('admin/index.html',
                         # KPI 카드
                         total_courses=total_courses,
                         total_students=total_students,
                         total_teachers=total_teachers,
                         weekly_sessions=weekly_sessions,
                         attendance_rate=attendance_rate,
                         pending_notifications=pending_notifications,
                         total_parent_links=total_parent_links,
                         pending_parent_links=pending_parent_links,
                         essays_pending=essays_pending,
                         essays_processing=essays_processing,
                         essays_completed=essays_completed,
                         # 주간 추가 통계
                         weekly_new_consultations=weekly_new_consultations,
                         weekly_new_students=weekly_new_students,
                         weekly_withdrawn=weekly_withdrawn,
                         total_all_courses=total_all_courses,
                         # 차트 데이터
                         student_labels=json.dumps(student_labels),
                         student_data=json.dumps(student_data),
                         enrollment_labels=json.dumps(enrollment_labels),
                         enrollment_data=json.dumps(enrollment_data),
                         essay_status_labels=json.dumps(list(essay_status_data.keys())),
                         essay_status_data=json.dumps(list(essay_status_data.values())),
                         # 최근 활동
                         recent_parent_requests=recent_parent_requests,
                         recent_makeup_requests=recent_makeup_requests)


# ==================== 수업 관리 ====================

@admin_bp.route('/courses')
@login_required
@requires_permission_level(2)
def courses():
    """수업 목록"""
    # 필터
    status_filter = request.args.get('status', '').strip()
    teacher_filter = request.args.get('teacher', '').strip()
    grade_filter = request.args.get('grade', '').strip()
    weekday_filter = request.args.get('weekday', '').strip()
    search_filter = request.args.get('search', '').strip()
    sort_order = request.args.get('sort', 'newest')  # newest | weekday

    query = Course.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if teacher_filter:
        query = query.filter_by(teacher_id=teacher_filter)
    if grade_filter:
        query = query.filter_by(grade=grade_filter)
    if weekday_filter != '':
        try:
            query = query.filter_by(weekday=int(weekday_filter))
        except ValueError:
            pass

    # 통합 검색: 반이름, 강사명, 학년, 요일, 반형태
    if search_filter:
        weekday_map = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
        wd_num = weekday_map.get(search_filter.replace('요일', ''))
        teacher_ids = [t.user_id for t in
                       User.query.filter(User.name.ilike(f'%{search_filter}%'),
                                         User.role == 'teacher').all()]
        student_course_ids = [e.course_id for e in
                              CourseEnrollment.query
                              .join(Student, Student.student_id == CourseEnrollment.student_id)
                              .filter(Student.name.ilike(f'%{search_filter}%')).all()]
        conditions = [
            Course.course_name.ilike(f'%{search_filter}%'),
            Course.grade.ilike(f'%{search_filter}%'),
            Course.course_type.ilike(f'%{search_filter}%'),
        ]
        if teacher_ids:
            conditions.append(Course.teacher_id.in_(teacher_ids))
        if student_course_ids:
            conditions.append(Course.course_id.in_(student_course_ids))
        if wd_num is not None:
            conditions.append(Course.weekday == wd_num)
        query = query.filter(db.or_(*conditions)).distinct()

    if sort_order == 'weekday':
        courses = query.order_by(
            db.case({None: 99}, value=Course.weekday, else_=Course.weekday),
            Course.start_time
        ).all()
    else:  # newest
        courses = query.order_by(Course.created_at.desc()).all()

    # 강사 목록 (필터용, 가나다 순)
    teachers = User.query.filter_by(role='teacher').order_by(User.name).all()

    return render_template('admin/courses.html',
                         courses=courses,
                         teachers=teachers,
                         status_filter=status_filter,
                         teacher_filter=teacher_filter,
                         grade_filter=grade_filter,
                         weekday_filter=weekday_filter,
                         search_filter=search_filter,
                         sort_order=sort_order)


@admin_bp.route('/courses/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def create_course():
    """수업 생성 (새 버전)"""
    form = CourseForm()

    # 강사 목록 로드 (가나다 순)
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()
    form.teacher_id.choices = [('', '-- 강사 선택 --')] + [(t.user_id, t.name) for t in teachers]

    # GET 요청 시 시작일 기본값: 오늘
    if request.method == 'GET' and not form.start_date.data:
        form.start_date.data = datetime.utcnow().date()

    if form.validate_on_submit():
        # 강사 정보
        teacher = User.query.get(form.teacher_id.data)

        # 요일 자동 계산 (폼에서 제공되지 않은 경우 시작일 기준으로 계산)
        weekday_value = form.weekday.data
        if weekday_value is None and form.start_date.data:
            # 시작일로부터 요일 계산 (0=월요일, 6=일요일)
            python_weekday = form.start_date.data.weekday()  # Python: 0=월요일, 6=일요일
            weekday_value = python_weekday

        # 요일 한글 변환
        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        weekday_text = weekday_names[weekday_value] if weekday_value is not None else ''

        # 시작 시간
        start_time_text = form.start_time.data.strftime('%H:%M') if form.start_time.data else ''

        # 1. 수업명: 사용자가 입력한 값 우선, 없으면 자동 생성
        submitted_name = (form.course_name.data or '').strip()
        if submitted_name:
            course_name = submitted_name
        else:
            course_name = f"{form.grade.data} {form.course_type.data}"
            if weekday_text:
                course_name += f" {weekday_text}"
            if start_time_text:
                course_name += f" {start_time_text}"
            course_name += f" - {teacher.name}"

        # 2. 수업 코드 자동 생성: [학년][수업타입 첫 글자][날짜YYMMDD]
        date_code = form.start_date.data.strftime('%y%m%d')
        type_code = form.course_type.data[0] if form.course_type.data else 'X'
        base_code = f"{form.grade.data}{type_code}{date_code}"
        course_code = base_code
        suffix = 2
        while Course.query.filter_by(course_code=course_code).first():
            course_code = f"{base_code}-{suffix}"
            suffix += 1

        # 3. is_terminated 처리
        is_terminated = (form.is_terminated.data == 'Y')

        # 4. 수업 타입별 회당 수업료
        price_map = {
            '베이직': 50000,
            '프리미엄': 65000,
            '정규반': 65000,
            '하크니스': 70000,
            '시그니처': 75000,
            '모의고사': 10000,
        }
        price_per_session = price_map.get(form.course_type.data, 0)

        # 5. duration_minutes 계산 (시작~종료 시간 차이)
        duration_minutes = 60  # 기본값
        if form.start_time.data and form.end_time.data:
            start_total = form.start_time.data.hour * 60 + form.start_time.data.minute
            end_total = form.end_time.data.hour * 60 + form.end_time.data.minute
            diff = end_total - start_total
            if diff > 0:
                duration_minutes = diff

        # 수업 생성
        course = Course(
            course_name=course_name,
            course_code=course_code,
            grade=form.grade.data,
            course_type=form.course_type.data,
            teacher_id=form.teacher_id.data,
            is_terminated=is_terminated,
            weekday=weekday_value,  # 자동 계산된 요일 사용
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,  # 폼에서 입력한 종료일 사용
            availability_status=form.availability_status.data,
            makeup_class_allowed=form.makeup_class_allowed.data,
            schedule_type='weekly',
            duration_minutes=duration_minutes,
            max_students=15,
            price_per_session=price_per_session,
            status='active' if not is_terminated else 'completed',
            created_by=current_user.user_id
        )

        db.session.add(course)
        db.session.flush()

        # 세션 자동 생성 (종료 여부 관계없이 항상 생성)
        sessions = generate_course_sessions(course)

        db.session.commit()

        # 담당 강사에게 수업 배정 알림
        if teacher:
            from app.models.notification import Notification
            Notification.create_notification(
                user_id=teacher.user_id,
                notification_type='course_created',
                title='새 수업이 배정되었습니다',
                message=f'"{course.course_name}" 수업이 개설되어 배정되었습니다.',
                link_url=url_for('teacher.index'),
                related_entity_type='course',
                related_entity_id=str(course.course_id)
            )

        flash(f'수업 "{course.course_name}"이(가) 생성되었습니다. (총 {len(sessions)}개 세션)', 'success')
        return redirect(url_for('admin.course_detail', course_id=course.course_id))

    return render_template('admin/create_course_new.html',
                         form=form,
                         title='새 수업 생성')


@admin_bp.route('/courses/<course_id>')
@login_required
@requires_permission_level(2)
def course_detail(course_id):
    """수업 상세"""
    course = Course.query.get_or_404(course_id)

    # 통계 정보
    stats = get_course_statistics(course_id)

    # 수강생 목록
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id).all()

    # 진행 완료된 세션 목록 (오늘 이전, 최근 5개)
    today = datetime.utcnow().date()
    recent_sessions = CourseSession.query.filter_by(course_id=course_id)\
        .filter(CourseSession.session_date <= today)\
        .order_by(CourseSession.session_date.desc()).limit(5).all()

    return render_template('admin/course_detail.html',
                         course=course,
                         stats=stats,
                         enrollments=enrollments,
                         recent_sessions=recent_sessions)


@admin_bp.route('/courses/<course_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def edit_course(course_id):
    """수업 수정"""
    course = Course.query.get_or_404(course_id)
    form = CourseForm(obj=course)

    # 강사 목록 로드 (가나다 순)
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()
    form.teacher_id.choices = [('', '-- 강사 선택 --')] + [(t.user_id, t.name) for t in teachers]

    # GET 요청 시 is_terminated Boolean → 'Y'/'N' 변환
    if request.method == 'GET':
        form.is_terminated.data = 'Y' if course.is_terminated else 'N'

    if form.validate_on_submit():
        old_end_date = course.end_date
        old_schedule_type = course.schedule_type
        old_weekday = course.weekday
        old_start_time = course.start_time
        old_end_time = course.end_time

        course.course_name = form.course_name.data
        course.course_code = form.course_code.data
        course.description = form.description.data
        course.tier = form.tier.data if form.tier.data else None
        course.teacher_id = form.teacher_id.data
        course.max_students = form.max_students.data
        course.schedule_type = form.schedule_type.data
        course.weekday = form.weekday.data
        course.start_time = form.start_time.data
        course.end_time = form.end_time.data
        course.duration_minutes = form.duration_minutes.data
        course.start_date = form.start_date.data
        course.end_date = form.end_date.data
        course.price_per_session = form.price_per_session.data
        course.status = form.status.data
        course.makeup_class_allowed = form.makeup_class_allowed.data
        course.is_terminated = (form.is_terminated.data == 'Y')

        # 시작/종료 시간이 변경된 경우: 미래 예정 세션들 시간도 일괄 업데이트
        from datetime import date as _date, timedelta as _td
        time_changed = (old_start_time != course.start_time or old_end_time != course.end_time)
        weekday_changed = (old_weekday != course.weekday and
                           course.schedule_type == 'weekly' and
                           course.weekday is not None and
                           old_weekday is not None)

        if time_changed or weekday_changed:
            future_sessions = CourseSession.query.filter(
                CourseSession.course_id == course.course_id,
                CourseSession.status == 'scheduled',
                CourseSession.session_date >= _date.today()
            ).all()
            for s in future_sessions:
                if time_changed:
                    s.start_time = course.start_time
                    s.end_time = course.end_time
                if weekday_changed:
                    # 같은 주 내에서 새 요일로 날짜 이동
                    day_shift = course.weekday - old_weekday
                    s.session_date = s.session_date + _td(days=day_shift)

        # 종료일이 연장된 weekly 수업: 새 세션 자동 생성
        if (course.schedule_type == 'weekly' and course.weekday is not None
                and course.end_date and old_end_date
                and course.end_date > old_end_date):
            from app.utils.course_utils import create_attendance_records_for_session
            from datetime import timedelta

            # 마지막 기존 세션 날짜 찾기
            last_session = (CourseSession.query
                            .filter_by(course_id=course.course_id)
                            .order_by(CourseSession.session_date.desc())
                            .first())

            if last_session:
                next_date = last_session.session_date + timedelta(days=7)
                next_number = last_session.session_number + 1
            else:
                # 세션이 없으면 start_date부터 지정 요일 찾기
                next_date = course.start_date
                while next_date.weekday() != course.weekday:
                    next_date += timedelta(days=1)
                next_number = 1

            new_sessions = []
            while next_date <= course.end_date:
                session = CourseSession(
                    course_id=course.course_id,
                    session_number=next_number,
                    session_date=next_date,
                    start_time=course.start_time,
                    end_time=course.end_time,
                    status='scheduled'
                )
                db.session.add(session)
                db.session.flush()
                create_attendance_records_for_session(session)
                new_sessions.append(session)
                next_date += timedelta(days=7)
                next_number += 1

            course.total_sessions = (CourseSession.query
                                     .filter_by(course_id=course.course_id)
                                     .count())

        db.session.commit()

        flash('수업 정보가 수정되었습니다.', 'success')
        return redirect(url_for('admin.course_detail', course_id=course_id))

    return render_template('admin/course_form.html',
                         form=form,
                         title='수업 수정',
                         is_edit=True,
                         course=course)


@admin_bp.route('/courses/<course_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(1)  # 마스터 관리자만
def delete_course(course_id):
    """수업 삭제"""
    course = Course.query.get_or_404(course_id)

    db.session.delete(course)
    db.session.commit()

    flash('수업이 삭제되었습니다.', 'info')
    return redirect(url_for('admin.courses'))


@admin_bp.route('/courses/<course_id>/toggle-makeup', methods=['POST'])
@login_required
@requires_permission_level(2)
def toggle_makeup_allowed(course_id):
    """보강신청 가능여부 토글"""
    course = Course.query.get_or_404(course_id)

    # 체크박스 값 가져오기 (체크되면 '1', 안되면 None)
    makeup_allowed = request.form.get('makeup_class_allowed') == '1'

    course.makeup_class_allowed = makeup_allowed
    db.session.commit()

    status_text = '가능' if makeup_allowed else '불가능'
    flash(f'보강신청 가능여부가 "{status_text}"으로 변경되었습니다.', 'success')
    return redirect(url_for('admin.course_detail', course_id=course_id))


# ==================== 학생 관리 ====================

@admin_bp.route('/courses/<course_id>/students-data')
@login_required
@requires_permission_level(2)
def get_students_data(course_id):
    """수강생 데이터 조회 (JSON)"""
    course = Course.query.get_or_404(course_id)

    # 수강생 목록
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id)\
        .order_by(CourseEnrollment.enrolled_at.desc()).all()

    # 통계 계산
    total_students = len(enrollments)
    active_students = len([e for e in enrollments if e.status == 'active'])
    avg_attendance = sum([e.attendance_rate for e in enrollments]) / total_students if total_students > 0 else 0

    # 학생 데이터
    students_data = []
    for enrollment in enrollments:
        student = enrollment.student
        students_data.append({
            'name': student.name,
            'grade': student.grade if student.grade else None,
            'tier': student.tier if student.tier else None,
            'phone': student.phone if student.phone else None,
            'attendance_rate': enrollment.attendance_rate,
            'attended': enrollment.attended_sessions,
            'late': enrollment.late_sessions,
            'absent': enrollment.absent_sessions,
            'status': enrollment.status,
            'enrolled_at': enrollment.enrolled_at.strftime('%Y-%m-%d')
        })

    return jsonify({
        'course_name': course.course_name,
        'total_students': total_students,
        'active_students': active_students,
        'avg_attendance': avg_attendance,
        'max_students': course.max_students,
        'students': students_data
    })


@admin_bp.route('/courses/<course_id>/students')
@login_required
@requires_permission_level(2)
def manage_students(course_id):
    """수강생 관리"""
    course = Course.query.get_or_404(course_id)

    # 현재 수강생
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id)\
        .order_by(CourseEnrollment.enrolled_at.desc()).all()

    # 등록 가능한 학생 (아직 수강 신청하지 않은 학생, 임시학생 제외)
    enrolled_student_ids = [e.student_id for e in enrollments if e.status == 'active']
    available_students = Student.query.filter(
        ~Student.student_id.in_(enrolled_student_ids),
        Student.is_temp == False
    ).all()

    return render_template('admin/manage_students.html',
                         course=course,
                         enrollments=enrollments,
                         available_students=available_students)


@admin_bp.route('/courses/<course_id>/students/add', methods=['POST'])
@login_required
@requires_permission_level(2)
def add_student(course_id):
    """학생 추가"""
    course = Course.query.get_or_404(course_id)
    student_id = request.form.get('student_id')

    if not student_id:
        flash('학생을 선택하세요.', 'error')
        return redirect(url_for('admin.manage_students', course_id=course_id))

    # 정원 확인
    if course.is_full:
        flash('수업 정원이 초과되었습니다.', 'error')
        return redirect(url_for('admin.manage_students', course_id=course_id))

    # 수강 신청
    enrollment = enroll_student_to_course(course_id, student_id)

    if enrollment:
        db.session.commit()

        # 담당 강사에게 학생 등록 알림
        from app.models import Student as StudentModel
        from app.models.notification import Notification
        student = StudentModel.query.get(student_id)
        teacher = User.query.get(course.teacher_id)
        if teacher and student:
            Notification.create_notification(
                user_id=teacher.user_id,
                notification_type='student_enrolled',
                title='학생이 수업에 등록되었습니다',
                message=f'{student.name} 학생이 "{course.course_name}" 수업에 등록되었습니다.',
                link_url=url_for('teacher.course_detail', course_id=course.course_id),
                related_entity_type='course',
                related_entity_id=str(course.course_id)
            )

        flash('학생이 수업에 등록되었습니다.', 'success')
    else:
        flash('수강 신청에 실패했습니다.', 'error')

    return redirect(url_for('admin.manage_students', course_id=course_id))


@admin_bp.route('/enrollments/<enrollment_id>/remove', methods=['POST'])
@login_required
@requires_permission_level(2)
def remove_student(enrollment_id):
    """학생 제거"""
    enrollment = CourseEnrollment.query.get_or_404(enrollment_id)
    course_id = enrollment.course_id

    enrollment.status = 'dropped'
    db.session.commit()

    flash('학생이 수업에서 제외되었습니다.', 'info')
    return redirect(url_for('admin.manage_students', course_id=course_id))


@admin_bp.route('/api/students/<student_id>/grade', methods=['PATCH'])
@login_required
@requires_permission_level(2)
def update_student_grade(student_id):
    """학생 학년 변경 API"""
    student = Student.query.get_or_404(student_id)
    data = request.json or {}
    new_grade = data.get('grade', '').strip()

    valid_grades = [
        '초1', '초2', '초3', '초4', '초5', '초6',
        '중1', '중2', '중3',
        '고1', '고2', '고3',
        '무학년제', '기타'
    ]
    if new_grade not in valid_grades:
        return jsonify({'success': False, 'message': '유효하지 않은 학년입니다.'}), 400

    old_grade = student.grade
    student.grade = new_grade
    db.session.commit()

    return jsonify({'success': True, 'old_grade': old_grade, 'new_grade': new_grade})


# ==================== 세션 관리 ====================

@admin_bp.route('/courses/<course_id>/sessions')
@login_required
@requires_permission_level(2)
def course_sessions(course_id):
    """수업 세션 목록 (과거 이력만)"""
    course = Course.query.get_or_404(course_id)

    from datetime import date
    today = date.today()
    sessions = CourseSession.query.filter(
        CourseSession.course_id == course_id,
        CourseSession.session_date <= today
    ).order_by(CourseSession.session_number.asc()).all()

    return render_template('admin/course_sessions.html',
                         course=course,
                         sessions=sessions)


@admin_bp.route('/sessions/<session_id>/attendance')
@login_required
@requires_permission_level(2)
def session_attendance(session_id):
    """세션 출석 현황"""
    session = CourseSession.query.get_or_404(session_id)

    attendance_records = Attendance.query.filter_by(session_id=session_id).all()

    return render_template('admin/session_attendance.html',
                         session=session,
                         attendance_records=attendance_records)


# ==================== 결제 관리 ====================

@admin_bp.route('/courses/<course_id>/payments')
@login_required
@requires_permission_level(2)
def course_payments(course_id):
    """수업 결제 관리"""
    course = Course.query.get_or_404(course_id)

    # 모든 수강생의 결제 정보
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id).all()

    payment_data = []
    for enrollment in enrollments:
        calc = calculate_tuition_amount(enrollment)
        payment_data.append({
            'enrollment': enrollment,
            'calculation': calc
        })

    return render_template('admin/course_payments.html',
                         course=course,
                         payment_data=payment_data)


@admin_bp.route('/payments/register', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def register_payment_old():
    """결제 등록 (구버전 - 수동 등록)"""
    form = PaymentForm()

    # 수강 신청 목록 로드
    course_id = request.args.get('course_id')
    if course_id:
        enrollments = CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()
    else:
        enrollments = CourseEnrollment.query.all()

    form.enrollment_id.choices = [('', '-- 수강 신청 선택 --')] + [
        (e.enrollment_id, f"{e.student.name} - {e.course.course_name}")
        for e in enrollments
    ]

    if form.validate_on_submit():
        enrollment = CourseEnrollment.query.get(form.enrollment_id.data)

        payment = Payment(
            enrollment_id=form.enrollment_id.data,
            course_id=enrollment.course_id,
            student_id=enrollment.student_id,
            amount=form.amount.data,
            payment_type=form.payment_type.data,
            sessions_covered=form.sessions_covered.data,
            payment_method=form.payment_method.data,
            notes=form.notes.data,
            status='completed',
            paid_at=datetime.utcnow(),
            processed_by=current_user.user_id
        )

        # 결제 완료된 회차 수 업데이트
        enrollment.paid_sessions += form.sessions_covered.data

        db.session.add(payment)
        db.session.commit()

        flash('결제가 등록되었습니다.', 'success')

        if course_id:
            return redirect(url_for('admin.course_payments', course_id=course_id))
        else:
            return redirect(url_for('admin.payments'))

    return render_template('admin/payment_form.html',
                         form=form,
                         course_id=course_id)


@admin_bp.route('/payment-periods')
@login_required
@requires_permission_level(2)
def payment_periods():
    """결제 기간 캘린더 관리"""
    from app.models.payment_period import PaymentPeriod, HolidayWeek

    selected_year = request.args.get('year', datetime.now().year, type=int)
    period_type = request.args.get('type', 'quarterly')  # quarterly or monthly

    periods = PaymentPeriod.query.filter_by(
        year=selected_year, period_type=period_type
    ).order_by(PaymentPeriod.period_number).all()

    # 연도 범위: 작년 ~ 내후년
    current_year = datetime.now().year
    year_range = list(range(current_year - 1, current_year + 3))

    # 휴무 주 목록 (해당 연도)
    holiday_weeks = HolidayWeek.query.filter(
        HolidayWeek.week_start >= date(selected_year, 1, 1),
        HolidayWeek.week_start <= date(selected_year, 12, 31)
    ).order_by(HolidayWeek.week_start).all()

    # 기존 생성 여부 확인
    monthly_exists = PaymentPeriod.query.filter_by(year=selected_year, period_type='monthly').count() > 0
    quarterly_exists = PaymentPeriod.query.filter_by(year=selected_year, period_type='quarterly').count() > 0

    return render_template('admin/payment_periods.html',
                           periods=periods,
                           selected_year=selected_year,
                           period_type=period_type,
                           year_range=year_range,
                           holiday_weeks=holiday_weeks,
                           monthly_exists=monthly_exists,
                           quarterly_exists=quarterly_exists)


@admin_bp.route('/payment-periods/generate', methods=['POST'])
@login_required
@requires_permission_level(2)
def generate_payment_periods():
    """결제 기간 자동 생성"""
    from app.models.payment_period import PaymentPeriod

    year = request.form.get('year', type=int)
    period_type = request.form.get('period_type')

    if not year or period_type not in ('monthly', 'quarterly'):
        flash('올바른 연도와 유형을 입력해주세요.', 'error')
        return redirect(url_for('admin.payment_periods'))

    existing = PaymentPeriod.query.filter_by(year=year, period_type=period_type).count()
    if existing > 0:
        flash(f'{year}년 {"월별" if period_type == "monthly" else "분기별"} 기간이 이미 존재합니다. 기존 항목을 수정해주세요.', 'warning')
        return redirect(url_for('admin.payment_periods', year=year, type=period_type))

    if period_type == 'monthly':
        periods = PaymentPeriod.generate_monthly(year)
        label = '월별 12개'
    else:
        periods = PaymentPeriod.generate_quarterly(year)
        label = '분기별 4개'

    for p in periods:
        db.session.add(p)
    db.session.commit()

    flash(f'{year}년 {label} 결제 기간이 생성되었습니다.', 'success')
    return redirect(url_for('admin.payment_periods', year=year, type=period_type))


@admin_bp.route('/payment-periods/<period_id>/update', methods=['POST'])
@login_required
@requires_permission_level(2)
def update_payment_period(period_id):
    """결제 기간 수정 (날짜, 주차수, 레이블)"""
    from app.models.payment_period import PaymentPeriod

    period = PaymentPeriod.query.get_or_404(period_id)

    label = request.form.get('label', '').strip()
    start_date_str = request.form.get('start_date', '').strip()
    end_date_str = request.form.get('end_date', '').strip()
    weeks_count = request.form.get('weeks_count', type=int)
    adjusted_note = request.form.get('adjusted_note', '').strip()

    try:
        if label:
            period.label = label
        if start_date_str:
            period.start_date = date.fromisoformat(start_date_str)
        if end_date_str:
            period.end_date = date.fromisoformat(end_date_str)
        if weeks_count and weeks_count > 0:
            period.weeks_count = weeks_count
        period.is_adjusted = True
        period.adjusted_note = adjusted_note or None
        db.session.commit()
        flash(f'"{period.label}" 기간이 수정되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'수정 중 오류가 발생했습니다: {e}', 'error')

    return redirect(url_for('admin.payment_periods', year=period.year, type=period.period_type))


@admin_bp.route('/payment-periods/<period_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def delete_payment_period(period_id):
    """결제 기간 삭제"""
    from app.models.payment_period import PaymentPeriod

    period = PaymentPeriod.query.get_or_404(period_id)
    year, ptype = period.year, period.period_type

    if period.payments.count() > 0:
        flash('이미 결제 내역이 있는 기간은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin.payment_periods', year=year, type=ptype))

    db.session.delete(period)
    db.session.commit()
    flash('기간이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.payment_periods', year=year, type=ptype))


@admin_bp.route('/holiday-weeks/create', methods=['POST'])
@login_required
@requires_permission_level(2)
def create_holiday_week():
    """휴무 기간 등록"""
    from app.models.payment_period import HolidayWeek

    week_start_str = request.form.get('week_start', '').strip()
    week_end_str = request.form.get('week_end', '').strip()
    reason = request.form.get('reason', '').strip()

    if not week_start_str or not week_end_str or not reason:
        flash('시작일, 종료일, 사유를 모두 입력해주세요.', 'error')
        return redirect(url_for('admin.payment_periods'))

    try:
        week_start = date.fromisoformat(week_start_str)
        week_end = date.fromisoformat(week_end_str)

        if week_end < week_start:
            flash('종료일이 시작일보다 앞설 수 없습니다.', 'error')
            return redirect(url_for('admin.payment_periods', year=week_start.year))

        # 중복 확인 (시작일 기준)
        existing = HolidayWeek.query.filter_by(week_start=week_start).first()
        if existing:
            flash(f'{week_start.strftime("%Y-%m-%d")} 시작 휴무 기간이 이미 등록되어 있습니다.', 'warning')
            return redirect(url_for('admin.payment_periods', year=week_start.year))

        hw = HolidayWeek(
            week_start=week_start,
            week_end=week_end,
            reason=reason,
            created_by=current_user.user_id
        )
        db.session.add(hw)
        db.session.commit()
        flash(f'휴무 기간 {week_start.strftime("%Y.%m.%d")}~{week_end.strftime("%m.%d")}이 등록되었습니다.', 'success')
        return redirect(url_for('admin.payment_periods', year=week_start.year))
    except ValueError:
        flash('올바른 날짜 형식을 입력해주세요.', 'error')
        return redirect(url_for('admin.payment_periods'))


@admin_bp.route('/holiday-weeks/<holiday_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def delete_holiday_week(holiday_id):
    """휴무 주 삭제"""
    from app.models.payment_period import HolidayWeek

    hw = HolidayWeek.query.get_or_404(holiday_id)
    year = hw.week_start.year
    db.session.delete(hw)
    db.session.commit()
    flash('휴무 주가 삭제되었습니다.', 'success')
    return redirect(url_for('admin.payment_periods', year=year))


@admin_bp.route('/session-adjustments')
@login_required
@requires_permission_level(2)
def session_adjustments():
    """이월 및 차감 관리"""
    from app.models.session_adjustment import SessionAdjustment

    tab = request.args.get('tab', 'review')  # review, pending, done

    if tab == 'review':
        items = SessionAdjustment.query.filter_by(status='pending_review')\
            .order_by(SessionAdjustment.created_at.desc()).all()
    elif tab == 'pending':
        items = SessionAdjustment.query.filter_by(status='pending')\
            .order_by(SessionAdjustment.created_at.desc()).all()
    else:
        items = SessionAdjustment.query.filter(
            SessionAdjustment.status.in_(['applied', 'cancelled'])
        ).order_by(SessionAdjustment.updated_at.desc()).limit(100).all()

    # 직접 추가용: 학생 목록 (활성 enrollment 있는 학생)
    students = Student.query.join(
        CourseEnrollment, CourseEnrollment.student_id == Student.student_id
    ).filter(CourseEnrollment.status == 'active').distinct().order_by(Student.name).all()

    # 분류 대기 건수 (뱃지용)
    review_count = SessionAdjustment.query.filter_by(status='pending_review').count()
    pending_count = SessionAdjustment.query.filter_by(status='pending').count()

    return render_template('admin/session_adjustments.html',
                           items=items, tab=tab,
                           students=students,
                           review_count=review_count,
                           pending_count=pending_count)


@admin_bp.route('/session-adjustments/<adjustment_id>/classify', methods=['POST'])
@login_required
@requires_permission_level(2)
def classify_adjustment(adjustment_id):
    """인정결석 건을 이월/무료수업으로 분류"""
    from app.models.session_adjustment import SessionAdjustment
    from app.models.notification import Notification

    adj = SessionAdjustment.query.get_or_404(adjustment_id)
    adj_type = request.form.get('adjustment_type')  # 'rollover' or 'free_session'

    if adj_type not in ('rollover', 'free_session'):
        flash('유효하지 않은 유형입니다.', 'error')
        return redirect(url_for('admin.session_adjustments', tab='review'))

    adj.adjustment_type = adj_type
    adj.status = 'pending'
    adj.reviewed_by = current_user.user_id
    adj.reviewed_at = datetime.utcnow()
    db.session.commit()

    type_label = '이월' if adj_type == 'rollover' else '무료수업'
    flash(f'{adj.student.name} 학생 인정결석을 {type_label}로 분류했습니다.', 'success')
    return redirect(url_for('admin.session_adjustments', tab='review'))


@admin_bp.route('/session-adjustments/create', methods=['POST'])
@login_required
@requires_permission_level(2)
def create_adjustment():
    """관리자 직접 이월/무료수업 추가"""
    from app.models.session_adjustment import SessionAdjustment
    from app.models.notification import Notification

    student_id = request.form.get('student_id')
    enrollment_id = request.form.get('enrollment_id')
    adj_type = request.form.get('adjustment_type')
    sessions_count = int(request.form.get('sessions_count', 1))
    reason = request.form.get('reason', '').strip()

    if not all([student_id, enrollment_id, adj_type]) or adj_type not in ('rollover', 'free_session'):
        flash('필수 항목을 모두 입력해주세요.', 'error')
        return redirect(url_for('admin.session_adjustments'))

    sessions_count = max(1, min(4, sessions_count))  # 1~4 범위 제한

    adj = SessionAdjustment(
        student_id=student_id,
        enrollment_id=enrollment_id,
        adjustment_type=adj_type,
        sessions_count=sessions_count,
        reason=reason or None,
        source='admin_manual',
        status='pending',
        reviewed_by=current_user.user_id,
        reviewed_at=datetime.utcnow(),
        created_by=current_user.user_id
    )
    db.session.add(adj)

    # 담당 강사에게 알림 발송
    enrollment = CourseEnrollment.query.get(enrollment_id)
    student = Student.query.get(student_id)
    if enrollment and enrollment.course and enrollment.course.teacher_id and student:
        type_label = '이월' if adj_type == 'rollover' else '무료수업'
        Notification.create_notification(
            user_id=enrollment.course.teacher_id,
            notification_type='session_adjustment',
            title=f'인정결석 처리 알림',
            message=f'관리자가 {student.name} 학생의 인정결석을 {type_label} {sessions_count}회로 등록했습니다.'
                    + (f' (사유: {reason})' if reason else ''),
            link_url=url_for('teacher.course_detail', course_id=enrollment.course_id)
        )
        adj.notified_teacher_at = datetime.utcnow()

    db.session.commit()

    type_label = '이월' if adj_type == 'rollover' else '무료수업'
    flash(f'{student.name} 학생 {type_label} {sessions_count}회 등록되었습니다.', 'success')
    return redirect(url_for('admin.session_adjustments', tab='pending'))


@admin_bp.route('/session-adjustments/<adjustment_id>/cancel', methods=['POST'])
@login_required
@requires_permission_level(2)
def cancel_adjustment(adjustment_id):
    """조정 건 취소"""
    from app.models.session_adjustment import SessionAdjustment

    adj = SessionAdjustment.query.get_or_404(adjustment_id)
    if adj.status == 'applied':
        flash('이미 결제에 반영된 항목은 취소할 수 없습니다.', 'error')
        return redirect(url_for('admin.session_adjustments', tab='pending'))

    adj.status = 'cancelled'
    db.session.commit()
    flash('취소되었습니다.', 'success')
    return redirect(url_for('admin.session_adjustments', tab='pending'))


@admin_bp.route('/api/student-enrollments/<student_id>')
@login_required
@requires_permission_level(2)
def student_enrollments_api(student_id):
    """학생의 활성 enrollment 목록 (직접 추가 팝업용 AJAX)"""
    from flask import jsonify
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id, status='active'
    ).all()
    return jsonify([{
        'enrollment_id': e.enrollment_id,
        'course_name': e.course.course_name if e.course else '알 수 없음'
    } for e in enrollments])


@admin_bp.route('/api/enrollment/<enrollment_id>/calculate')
@login_required
@requires_permission_level(2)
def calculate_enrollment_payment(enrollment_id):
    """수강 결제 미리보기 API (계산 엔진 결과 반환)
    GET /admin/api/enrollment/<id>/calculate?period_id=xxx
    """
    from app.services.payment_calculator import PaymentCalculator
    from app.models.payment_period import PaymentPeriod

    enrollment = CourseEnrollment.query.get_or_404(enrollment_id)
    period_id = request.args.get('period_id')

    if not period_id:
        # period_id 미지정 시 현재 날짜에 해당하는 기간 자동 탐색
        today = date.today()
        period = PaymentPeriod.query.filter(
            PaymentPeriod.start_date <= today,
            PaymentPeriod.end_date >= today,
            PaymentPeriod.period_type == (enrollment.payment_cycle or 'monthly')
        ).first()
        if not period:
            return jsonify({'error': '해당 결제 기간을 찾을 수 없습니다.'}), 404
    else:
        period = PaymentPeriod.query.get_or_404(period_id)

    result = PaymentCalculator.calculate(enrollment, period)
    return jsonify(result.to_dict())


@admin_bp.route('/api/enrollment/<enrollment_id>/update-payment-info', methods=['POST'])
@login_required
@requires_permission_level(2)
def update_enrollment_payment_info(enrollment_id):
    """수강 결제 설정 업데이트 (payment_cycle, weekly_fee, discount_type)
    POST /admin/api/enrollment/<id>/update-payment-info
    Body: { payment_cycle, weekly_fee, discount_type }
    """
    enrollment = CourseEnrollment.query.get_or_404(enrollment_id)
    data = request.get_json() or {}

    if 'payment_cycle' in data:
        if data['payment_cycle'] in ('monthly', 'quarterly', ''):
            enrollment.payment_cycle = data['payment_cycle'] or None

    if 'weekly_fee' in data:
        try:
            fee = int(data['weekly_fee'])
            enrollment.weekly_fee = fee if fee >= 0 else None
        except (ValueError, TypeError):
            return jsonify({'error': 'weekly_fee는 숫자여야 합니다.'}), 400

    if 'discount_type' in data:
        from app.services.payment_calculator import PaymentCalculator
        valid = {k for k, _ in PaymentCalculator.get_discount_options()} | {''}
        if data['discount_type'] in valid:
            enrollment.discount_type = data['discount_type'] or None
        else:
            return jsonify({'error': '유효하지 않은 할인 유형입니다.'}), 400

    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/billing')
@login_required
@requires_permission_level(2)
def billing():
    """청구서 생성 메인 페이지"""
    from app.services.payment_calculator import PaymentCalculator
    from app.models.payment_period import PaymentPeriod

    period_id = request.args.get('period_id', '').strip()

    # 기간 선택 목록 (최근 2년치)
    periods = PaymentPeriod.query.order_by(
        PaymentPeriod.start_date.desc()
    ).limit(30).all()

    selected_period = None
    billing_rows = []
    setup_needed = []
    stats = {}

    if period_id:
        selected_period = PaymentPeriod.query.get(period_id)

    if selected_period:
        # 해당 주기 활성 enrollment 전체 조회
        all_enrollments = CourseEnrollment.query.filter_by(status='active').all()

        billed_count = 0
        ready_count = 0
        setup_count = 0

        for enrollment in sorted(all_enrollments, key=lambda e: e.student.name if e.student else ''):
            # 결제 주기가 기간 유형과 다르면 건너뜀
            if enrollment.payment_cycle and enrollment.payment_cycle != selected_period.period_type:
                continue

            # 설정 미완료 (주기 or 수업료 없음)
            if not enrollment.payment_cycle or not enrollment.weekly_fee:
                setup_needed.append(enrollment)
                setup_count += 1
                continue

            # 이미 청구된 건 확인
            existing = Payment.query.filter_by(
                enrollment_id=enrollment.enrollment_id,
                period_id=period_id
            ).first()

            if existing:
                billing_rows.append({
                    'enrollment': enrollment,
                    'result': None,
                    'existing_payment': existing,
                    'billed': True,
                })
                billed_count += 1
            else:
                result = PaymentCalculator.calculate(enrollment, selected_period)
                billing_rows.append({
                    'enrollment': enrollment,
                    'result': result,
                    'existing_payment': None,
                    'billed': False,
                })
                ready_count += 1

        stats = {
            'total': ready_count + billed_count + setup_count,
            'ready': ready_count,
            'billed': billed_count,
            'setup_needed': setup_count,
            'total_amount': sum(
                r['result'].final_amount for r in billing_rows
                if not r['billed'] and r['result']
            ),
        }

    return render_template('admin/billing.html',
                           periods=periods,
                           selected_period=selected_period,
                           period_id=period_id,
                           billing_rows=billing_rows,
                           setup_needed=setup_needed,
                           stats=stats)


@admin_bp.route('/billing/create-invoices', methods=['POST'])
@login_required
@requires_permission_level(2)
def create_invoices():
    """청구서 일괄 생성 (Payment 레코드 저장 + SessionAdjustment applied 처리)"""
    from app.services.payment_calculator import PaymentCalculator
    from app.models.payment_period import PaymentPeriod

    period_id = request.form.get('period_id', '').strip()
    enrollment_ids = request.form.getlist('enrollment_ids')

    if not period_id or not enrollment_ids:
        flash('기간과 수강생을 선택해주세요.', 'error')
        return redirect(url_for('admin.billing'))

    period = PaymentPeriod.query.get_or_404(period_id)

    created_count = 0
    skipped_count = 0
    error_count = 0

    for enrollment_id in enrollment_ids:
        enrollment = CourseEnrollment.query.get(enrollment_id)
        if not enrollment or not enrollment.weekly_fee or not enrollment.payment_cycle:
            error_count += 1
            continue

        # 이미 청구된 건 스킵
        existing = Payment.query.filter_by(
            enrollment_id=enrollment_id,
            period_id=period_id
        ).first()
        if existing:
            skipped_count += 1
            continue

        result = PaymentCalculator.calculate(enrollment, period)

        payment = Payment(
            enrollment_id=enrollment.enrollment_id,
            course_id=enrollment.course_id,
            student_id=enrollment.student_id,
            amount=result.final_amount,
            original_amount=result.base_amount,
            discount_type=result.discount_type,
            discount_rate=result.discount_rate,
            discount_amount=result.total_discount,
            payment_type='tuition',
            payment_period=enrollment.payment_cycle,
            period_id=period_id,
            period_start=period.start_date,
            period_end=period.end_date,
            weekly_fee=result.weekly_fee,
            weeks_count=result.weeks_charged,
            is_prorated=result.is_prorated,
            carried_over=result.rollover_sessions,
            free_used=result.free_sessions,
            status='pending',
            processed_by=current_user.user_id,
        )
        db.session.add(payment)
        db.session.flush()  # payment_id 확보

        # 이번 청구에 반영된 조정 항목 → applied 처리
        for adj in result.pending_adjustments:
            adj.status = 'applied'
            adj.applied_payment_id = payment.payment_id
            if not adj.reviewed_at:
                adj.reviewed_at = datetime.utcnow()

        created_count += 1

    db.session.commit()

    msg = f'청구서 {created_count}건 생성 완료'
    if skipped_count:
        msg += f', 이미 청구된 {skipped_count}건 제외'
    if error_count:
        msg += f', 설정 오류 {error_count}건 건너뜀'
    flash(msg, 'success')
    return redirect(url_for('admin.billing', period_id=period_id))


# ────────────────────────────────────────────────────────────────
# SMS 헬퍼
# ────────────────────────────────────────────────────────────────

def _build_sms_message(payment):
    """수강료 안내 문자 내용 생성"""
    student_name = payment.student.name if payment.student else '학생'
    course_name = payment.course.course_name if payment.course else '수강 과목'

    period_str = ''
    if payment.period_start and payment.period_end:
        period_str = (f"{payment.period_start.strftime('%Y년 %m월')} "
                      f"({payment.period_start.strftime('%m/%d')}"
                      f"~{payment.period_end.strftime('%m/%d')})")

    lines = ['[momoAI 수강료 안내]', f'학생: {student_name}']
    if period_str:
        lines.append(f'기간: {period_str}')
    lines.append(f'수업: {course_name}')
    lines.append(f'청구액: {payment.amount:,}원')

    if payment.discount_amount and payment.discount_amount > 0:
        disc_labels = {
            'sibling': '형제자매', 'acquaintance': '지인',
            'employee': '직원', 'scholarship': '장학'
        }
        label = disc_labels.get(payment.discount_type or '', '할인')
        lines.append(f'({label} {payment.discount_amount:,}원 할인 포함)')

    if (payment.carried_over or 0) + (payment.free_used or 0) > 0:
        parts = []
        if payment.carried_over:
            parts.append(f'이월{payment.carried_over}회')
        if payment.free_used:
            parts.append(f'무료{payment.free_used}회')
        lines.append(f'({" ".join(parts)} 차감 포함)')

    return '\n'.join(lines)


def _get_sms_recipient(payment):
    """수신자 전화번호·이름 반환 (학부모 우선, 없으면 학생)"""
    from app.models.parent_student import ParentStudent
    from app.models import User

    relation = ParentStudent.query.filter_by(
        student_id=payment.student_id,
        is_active=True
    ).first()
    if relation:
        parent = User.query.get(relation.parent_id)
        if parent and parent.phone:
            return parent.phone, parent.name or parent.username

    student = payment.student
    if student and student.phone:
        return student.phone, student.name

    return None, None


@admin_bp.route('/api/payment/<payment_id>/sms-preview')
@login_required
@requires_permission_level(2)
def payment_sms_preview(payment_id):
    """SMS 발송 미리보기 API (모달에서 AJAX로 호출)"""
    payment = Payment.query.get_or_404(payment_id)
    phone, name = _get_sms_recipient(payment)
    message = _build_sms_message(payment)

    return jsonify({
        'payment_id': payment_id,
        'student_name': payment.student.name if payment.student else '',
        'course_name': payment.course.course_name if payment.course else '',
        'amount': payment.amount,
        'recipient_phone': phone or '',
        'recipient_name': name or '',
        'message': message,
        'already_sent': payment.sms_sent_at is not None,
        'sent_at': payment.sms_sent_at.strftime('%Y-%m-%d %H:%M') if payment.sms_sent_at else None,
    })


@admin_bp.route('/billing/send-sms', methods=['POST'])
@login_required
@requires_permission_level(2)
def send_payment_sms():
    """청구서 1건 문자 발송 (AJAX)
    Body: { payment_id, phone (optional override), message (optional override) }
    """
    from app.utils.sms import send_sms_message

    data = request.get_json() or {}
    payment_id = data.get('payment_id', '').strip()
    if not payment_id:
        return jsonify({'success': False, 'reason': 'payment_id 필수'}), 400

    payment = Payment.query.get_or_404(payment_id)

    phone = (data.get('phone') or '').strip()
    if not phone:
        phone, _ = _get_sms_recipient(payment)
    if not phone:
        return jsonify({'success': False, 'reason': '수신자 전화번호 없음. 학부모 또는 학생 연락처를 등록해주세요.'})

    message = (data.get('message') or '').strip() or _build_sms_message(payment)

    success, reason = send_sms_message(phone, message)
    if success:
        payment.sms_sent_at = datetime.utcnow()
        db.session.commit()

    return jsonify({
        'success': success,
        'reason': reason,
        'sent_at': payment.sms_sent_at.strftime('%m/%d %H:%M') if payment.sms_sent_at else None,
    })


@admin_bp.route('/billing/send-sms-batch', methods=['POST'])
@login_required
@requires_permission_level(2)
def send_payment_sms_batch():
    """청구서 일괄 문자 발송 (AJAX)
    Body: { payment_ids: [...] }
    """
    from app.utils.sms import send_sms_message

    data = request.get_json() or {}
    payment_ids = data.get('payment_ids', [])
    if not payment_ids:
        return jsonify({'success': False, 'reason': 'payment_ids 필수'}), 400

    results = []
    for pid in payment_ids:
        payment = Payment.query.get(pid)
        if not payment:
            results.append({'payment_id': pid, 'success': False, 'reason': '청구서 없음'})
            continue
        if payment.sms_sent_at:
            results.append({'payment_id': pid, 'success': True, 'reason': '이미 발송됨', 'skipped': True})
            continue

        phone, _ = _get_sms_recipient(payment)
        if not phone:
            results.append({'payment_id': pid, 'success': False, 'reason': '수신자 번호 없음'})
            continue

        message = _build_sms_message(payment)
        success, reason = send_sms_message(phone, message)
        if success:
            payment.sms_sent_at = datetime.utcnow()
        results.append({'payment_id': pid, 'success': success, 'reason': reason})

    db.session.commit()

    sent = sum(1 for r in results if r.get('success') and not r.get('skipped'))
    skipped = sum(1 for r in results if r.get('skipped'))
    failed = sum(1 for r in results if not r.get('success'))

    return jsonify({
        'success': True,
        'sent': sent,
        'skipped': skipped,
        'failed': failed,
        'results': results,
    })


@admin_bp.route('/payments')
@login_required
@requires_permission_level(2)
def payments():
    """전체 결제 목록"""
    # 필터
    status_filter = request.args.get('status', '').strip()

    query = Payment.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    payments = query.order_by(Payment.created_at.desc()).all()

    return render_template('admin/payments.html',
                         payments=payments,
                         status_filter=status_filter)


@admin_bp.route('/api/students/search')
@login_required
@requires_permission_level(2)
def search_students():
    """학생 검색 API"""
    query = request.args.get('q', '').strip()
    grade = request.args.get('grade', '').strip()

    students_query = Student.query.filter_by(is_temp=False)

    if grade:
        students_query = students_query.filter_by(grade=grade)

    if query:
        students_query = students_query.filter(Student.name.ilike(f'%{query}%'))

    students = students_query.order_by(Student.name).limit(20).all()

    results = []
    for student in students:
        active_courses = CourseEnrollment.query.filter_by(
            student_id=student.student_id,
            status='active'
        ).count()

        parent_count = ParentStudent.query.filter_by(
            student_id=student.student_id,
            is_active=True
        ).count()

        results.append({
            'student_id': student.student_id,
            'name': student.name,
            'grade': student.grade or '',
            'school': student.school or '',
            'student_code': student.student_id[:8],
            'is_active': True,
            'active_course_count': active_courses,
            'course_count': active_courses,
            'parent_count': parent_count
        })

    return jsonify({'students': results})


@admin_bp.route('/api/students/<student_id>/courses')
@login_required
@requires_permission_level(2)
def get_student_courses(student_id):
    """학생의 수강 중인 수업 조회 API"""
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    courses = [e.course_id for e in enrollments]
    return jsonify({'courses': courses})


@admin_bp.route('/payments/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def create_payment():
    """결제 생성"""
    from app.admin.forms import CreatePaymentForm
    from calendar import monthrange

    form = CreatePaymentForm()

    # 수업 목록 로드
    courses = Course.query.order_by(Course.course_name).all()
    form.course_id.choices = [('', '-- 수업 선택 --')] + [(c.course_id, c.course_name) for c in courses]

    # 기본 납부 기한: 현재 월 말일
    if not form.due_date.data:
        today = datetime.utcnow().date()
        last_day = monthrange(today.year, today.month)[1]
        form.due_date.data = datetime(today.year, today.month, last_day).date()

    if form.validate_on_submit():
        # 수업료 결정 (선택지 또는 직접 입력)
        if form.price_option.data == 'custom':
            price_per_session = form.price_per_session.data
        else:
            price_per_session = int(form.price_option.data)

        # 기본 회차 수
        base_sessions = 4 if form.payment_period.data == 'monthly' else 12

        # 이월결석 처리
        if form.carryover_option.data == 'custom':
            carryover = form.carryover_absences.data or 0
        else:
            carryover = int(form.carryover_option.data)

        # 실제 결제 회차 (이월결석 차감)
        sessions_covered = max(0, base_sessions - carryover)

        # 원금액 계산 (할인 전)
        original_amount = price_per_session * sessions_covered

        # 할인율 계산
        discount_rate = 0.0
        discount_type = form.discount_type.data

        if discount_type == 'acquaintance':
            discount_rate = 0.20
        elif discount_type == 'sibling':
            discount_rate = 0.10
        elif discount_type == 'quarterly':
            discount_rate = 0.05

        # 할인 금액 계산
        discount_amount = int(original_amount * discount_rate)

        # 최종 결제 금액
        final_amount = original_amount - discount_amount

        # Enrollment 찾기 또는 생성
        enrollment = CourseEnrollment.query.filter_by(
            course_id=form.course_id.data,
            student_id=form.student_id.data
        ).first()

        if not enrollment:
            # 수강 신청이 없으면 생성
            enrollment = CourseEnrollment(
                course_id=form.course_id.data,
                student_id=form.student_id.data,
                status='active'
            )
            db.session.add(enrollment)
            db.session.flush()

        # 결제 생성
        payment = Payment(
            enrollment_id=enrollment.enrollment_id,
            course_id=form.course_id.data,
            student_id=form.student_id.data,
            amount=final_amount,
            original_amount=original_amount,
            discount_type=discount_type if discount_type != 'none' else None,
            discount_rate=discount_rate,
            discount_amount=discount_amount,
            payment_type='tuition',
            payment_period=form.payment_period.data,
            sessions_covered=sessions_covered,
            payment_method=form.payment_method.data if form.payment_method.data else None,
            due_date=form.due_date.data,
            status='pending',
            notes=form.notes.data,
            processed_by=current_user.user_id
        )

        db.session.add(payment)
        db.session.commit()

        flash(f'결제가 생성되었습니다. (금액: {final_amount:,}원)', 'success')
        return redirect(url_for('admin.payments'))

    return render_template('admin/create_payment.html', form=form)


# ==================== 결제 메시지 발송 API ====================

@admin_bp.route('/api/payments/<payment_id>/message-info')
@login_required
@requires_permission_level(2)
def get_payment_message_info(payment_id):
    """결제 메시지 발송을 위한 정보 조회"""
    payment = Payment.query.get_or_404(payment_id)
    student = payment.student
    course = payment.course

    # 결제 방법 텍스트
    payment_method_map = {
        'card': '카드',
        'cash': '현금',
        'transfer': '계좌이체'
    }
    payment_method_text = payment_method_map.get(payment.payment_method, payment.payment_method or '-')

    return jsonify({
        'success': True,
        'student_name': student.name,
        'phone': student.phone,
        'course_name': course.course_name,
        'amount': payment.amount,
        'original_amount': payment.original_amount,
        'discount_amount': payment.discount_amount or 0,
        'payment_period': payment.payment_period,
        'sessions_covered': payment.sessions_covered,
        'due_date': payment.due_date.strftime('%Y-%m-%d') if payment.due_date else None,
        'payment_method_text': payment_method_text
    })


@admin_bp.route('/api/payments/<payment_id>/send-message', methods=['POST'])
@login_required
@requires_permission_level(2)
def send_payment_message(payment_id):
    """결제 메시지 발송 (SMS 또는 카카오톡)"""
    data = request.get_json()
    message_type = data.get('message_type')  # 'sms' or 'kakao'
    message = data.get('message')
    phone = data.get('phone')

    if not message or not phone:
        return jsonify({
            'success': False,
            'message': '메시지 내용과 전화번호가 필요합니다.'
        }), 400

    # 전화번호 형식 정리 (하이픈 제거)
    phone = phone.replace('-', '').replace(' ', '')

    try:
        # ===== 여기에 실제 SMS/카카오톡 API 연동 코드를 추가하세요 =====

        if message_type == 'sms':
            # SMS 발송 로직
            success = send_sms_message(phone, message)
            type_name = 'SMS 문자'
        elif message_type == 'kakao':
            # 카카오톡 발송 로직
            success = send_kakao_message(phone, message)
            type_name = '카카오톡 메시지'
        else:
            return jsonify({
                'success': False,
                'message': '올바르지 않은 메시지 타입입니다.'
            }), 400

        if success:
            # 발송 성공 시 로그 기록 (선택사항)
            # MessageLog 모델이 있다면 여기에 기록

            return jsonify({
                'success': True,
                'message': f'{type_name}가 성공적으로 발송되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'{type_name} 발송에 실패했습니다. API 설정을 확인해주세요.'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'발송 중 오류가 발생했습니다: {str(e)}'
        }), 500


def send_sms_message(phone, message):
    """알리고 SMS API를 통한 문자 발송"""
    import requests
    from flask import current_app

    api_key = current_app.config.get('SMS_API_KEY')
    user_id = current_app.config.get('SMS_USER_ID')
    sender = current_app.config.get('SMS_SENDER')

    # API 설정 확인
    if not api_key:
        print("❌ SMS_API_KEY가 설정되지 않았습니다.")
        return False

    if not user_id:
        print("⚠️ SMS_USER_ID가 설정되지 않았습니다. 시뮬레이션 모드로 작동합니다.")
        print(f"[SMS 발송 시뮬레이션]")
        print(f"수신자: {phone}")
        print(f"내용:\n{message}")
        print("-" * 50)
        return True

    if not sender:
        print("⚠️ SMS_SENDER가 설정되지 않았습니다. 시뮬레이션 모드로 작동합니다.")
        print(f"[SMS 발송 시뮬레이션]")
        print(f"수신자: {phone}")
        print(f"내용:\n{message}")
        print("-" * 50)
        return True

    # 실제 SMS 발송
    url = 'https://apis.aligo.in/send/'

    # 메시지 길이에 따라 SMS/LMS 자동 선택
    msg_type = 'LMS' if len(message) > 90 else 'SMS'

    data = {
        'key': api_key,
        'user_id': user_id,
        'sender': sender,
        'receiver': phone,
        'msg': message,
        'msg_type': msg_type,
        'title': 'MOMOAI 결제 안내' if msg_type == 'LMS' else ''
    }

    try:
        print(f"📱 SMS 발송 중... (수신자: {phone}, 타입: {msg_type})")
        response = requests.post(url, data=data, timeout=10)
        result = response.json()

        print(f"API 응답: {result}")

        if result.get('result_code') == '1':
            print(f"✅ SMS 발송 성공: {phone}")
            return True
        else:
            error_msg = result.get('message', '알 수 없는 오류')
            print(f"❌ SMS 발송 실패: {error_msg}")
            return False
    except requests.exceptions.Timeout:
        print("❌ SMS 발송 타임아웃 (10초 초과)")
        return False
    except Exception as e:
        print(f"❌ SMS 발송 오류: {str(e)}")
        return False


def send_kakao_message(phone, message):
    """카카오톡 메시지 발송 함수

    실제 카카오톡 API를 연동하려면:
    1. 카카오 비즈니스 계정 생성
    2. config.py에 KAKAO_API_KEY, KAKAO_SENDER_KEY 등 설정 추가
    3. 카카오톡 채널 개설 및 템플릿 등록
    4. 아래 코드를 실제 API 호출 코드로 변경

    카카오톡 비즈니스 메시지 API:
    - 카카오톡 채널: https://business.kakao.com/
    - 알림톡/친구톡 API: https://developers.kakao.com/
    - 대행 서비스: 알리고, 비즈뿌리오 등
    """
    # 개발 모드: 콘솔에 출력만 하고 성공 반환
    print(f"[카카오톡 발송 시뮬레이션]")
    print(f"수신자: {phone}")
    print(f"내용:\n{message}")
    print("-" * 50)

    # TODO: 실제 카카오톡 API 연동
    # 예시 (알리고 카카오톡 API):
    # import requests
    # from flask import current_app
    #
    # api_key = current_app.config.get('KAKAO_API_KEY')
    # user_id = current_app.config.get('KAKAO_USER_ID')
    # sender_key = current_app.config.get('KAKAO_SENDER_KEY')
    #
    # url = 'https://kakaoapi.aligo.in/akv10/alimtalk/send/'
    # data = {
    #     'apikey': api_key,
    #     'userid': user_id,
    #     'senderkey': sender_key,
    #     'receiver': phone,
    #     'message': message,
    #     'template_code': 'YOUR_TEMPLATE_CODE'
    # }
    #
    # response = requests.post(url, data=data)
    # result = response.json()
    #
    # return result.get('code') == '0'

    return True  # 개발 모드: 항상 성공 반환


# ==================== 공지사항 관리 ====================

@admin_bp.route('/announcements')
@login_required
@requires_permission_level(3)  # 스태프 이상
def announcements():
    """공지사항 목록"""
    announcements = Announcement.query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc()
    ).all()

    return render_template('admin/announcements.html',
                         announcements=announcements)


@admin_bp.route('/announcements/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(3)
def create_announcement():
    """공지사항 작성"""
    form = AnnouncementForm()

    if form.validate_on_submit():
        # target_roles 처리
        target_roles_data = form.target_roles.data
        if 'all' in target_roles_data:
            target_roles_str = 'all'
        else:
            target_roles_str = ','.join(target_roles_data)

        # target_tiers 처리
        target_tiers_str = ','.join(form.target_tiers.data) if form.target_tiers.data else None

        announcement = Announcement(
            author_id=current_user.user_id,
            title=form.title.data,
            content=form.content.data,
            announcement_type=form.announcement_type.data,
            target_roles=target_roles_str,
            target_tiers=target_tiers_str,
            is_pinned=form.is_pinned.data,
            is_popup=form.is_popup.data,
            publish_start=form.publish_start.data,
            publish_end=form.publish_end.data,
            is_published=True
        )

        db.session.add(announcement)
        db.session.commit()

        flash(f'공지사항 "{announcement.title}"이(가) 등록되었습니다.', 'success')
        return redirect(url_for('admin.announcements'))

    return render_template('admin/announcement_form.html',
                         form=form,
                         title='새 공지사항 작성',
                         is_edit=False)


@admin_bp.route('/announcements/<announcement_id>')
@login_required
@requires_permission_level(3)
def announcement_detail(announcement_id):
    """공지사항 상세"""
    announcement = Announcement.query.get_or_404(announcement_id)

    # 읽음 통계
    total_reads = len(announcement.reads)

    # 대상자 수 계산
    target_users_count = 0
    if announcement.target_roles == 'all' or 'all' in announcement.target_roles_list:
        target_users_count = User.query.filter_by(is_active=True).count()
    else:
        for role in announcement.target_roles_list:
            target_users_count += User.query.filter_by(role=role, is_active=True).count()

    read_percentage = (total_reads / target_users_count * 100) if target_users_count > 0 else 0

    return render_template('admin/announcement_detail.html',
                         announcement=announcement,
                         total_reads=total_reads,
                         target_users_count=target_users_count,
                         read_percentage=read_percentage)


@admin_bp.route('/announcements/<announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(3)
def edit_announcement(announcement_id):
    """공지사항 수정"""
    announcement = Announcement.query.get_or_404(announcement_id)
    form = AnnouncementForm(obj=announcement)

    if request.method == 'GET':
        # 폼 초기값 설정
        if announcement.target_roles == 'all':
            form.target_roles.data = ['all']
        else:
            form.target_roles.data = announcement.target_roles_list

        if announcement.target_tiers:
            form.target_tiers.data = announcement.target_tiers_list

    if form.validate_on_submit():
        # target_roles 처리
        target_roles_data = form.target_roles.data
        if 'all' in target_roles_data:
            target_roles_str = 'all'
        else:
            target_roles_str = ','.join(target_roles_data)

        # target_tiers 처리
        target_tiers_str = ','.join(form.target_tiers.data) if form.target_tiers.data else None

        announcement.title = form.title.data
        announcement.content = form.content.data
        announcement.announcement_type = form.announcement_type.data
        announcement.target_roles = target_roles_str
        announcement.target_tiers = target_tiers_str
        announcement.is_pinned = form.is_pinned.data
        announcement.is_popup = form.is_popup.data
        announcement.publish_start = form.publish_start.data
        announcement.publish_end = form.publish_end.data

        db.session.commit()

        flash('공지사항이 수정되었습니다.', 'success')
        return redirect(url_for('admin.announcement_detail', announcement_id=announcement_id))

    return render_template('admin/announcement_form.html',
                         form=form,
                         title='공지사항 수정',
                         is_edit=True,
                         announcement=announcement)


@admin_bp.route('/announcements/<announcement_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def delete_announcement(announcement_id):
    """공지사항 삭제"""
    announcement = Announcement.query.get_or_404(announcement_id)

    db.session.delete(announcement)
    db.session.commit()

    flash('공지사항이 삭제되었습니다.', 'info')
    return redirect(url_for('admin.announcements'))


@admin_bp.route('/announcements/<announcement_id>/toggle-publish', methods=['POST'])
@login_required
@requires_permission_level(3)
def toggle_announcement_publish(announcement_id):
    """공지사항 게시/비게시 토글"""
    announcement = Announcement.query.get_or_404(announcement_id)

    announcement.is_published = not announcement.is_published
    db.session.commit()

    status = '게시' if announcement.is_published else '비게시'
    flash(f'공지사항이 {status} 상태로 변경되었습니다.', 'success')

    return redirect(url_for('admin.announcement_detail', announcement_id=announcement_id))


# ==================== 문자 발송 ====================

@admin_bp.route('/messages')
@login_required
@requires_permission_level(3)
def messages():
    """문자 발송 내역"""
    from app.models.message import Message

    # 필터
    status_filter = request.args.get('status', '').strip()
    type_filter = request.args.get('type', '').strip()
    sender_id_filter = request.args.get('sender_id', '').strip()
    search = request.args.get('search', '').strip()

    # 관리자(level 1-2)는 전체 조회, 강사(level 3)는 본인만
    if current_user.role_level <= 2:
        query = Message.query
        senders = User.query.filter(User.role.in_(['admin', 'teacher']), User.is_active == True).order_by(User.name).all()
    else:
        query = Message.query.filter_by(sender_id=current_user.user_id)
        senders = []

    if sender_id_filter and current_user.role_level <= 2:
        query = query.filter_by(sender_id=sender_id_filter)

    if status_filter:
        query = query.filter_by(status=status_filter)

    if type_filter:
        query = query.filter_by(message_type=type_filter)

    if search:
        query = query.filter(
            db.or_(
                Message.content.contains(search),
                Message.subject.contains(search)
            )
        )

    messages = query.order_by(Message.created_at.desc()).all()

    # 통계
    if current_user.role_level <= 2:
        stats_query = Message.query.filter_by(status='completed')
        if sender_id_filter:
            stats_query = stats_query.filter_by(sender_id=sender_id_filter)
        total_sent = stats_query.count()
        total_recipients = db.session.query(func.sum(Message.total_recipients)).filter(
            Message.status == 'completed'
        ).scalar() or 0
    else:
        total_sent = Message.query.filter_by(sender_id=current_user.user_id, status='completed').count()
        total_recipients = db.session.query(func.sum(Message.total_recipients))\
            .filter_by(sender_id=current_user.user_id, status='completed').scalar() or 0

    return render_template('admin/messages.html',
                         messages=messages,
                         total_sent=total_sent,
                         total_recipients=total_recipients,
                         status_filter=status_filter,
                         type_filter=type_filter,
                         sender_id_filter=sender_id_filter,
                         search=search,
                         senders=senders)


@admin_bp.route('/messages/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(3)
def send_message():
    """문자 발송"""
    from app.models.message import Message, MessageRecipient
    import json

    if request.method == 'POST':
        message_type = request.form.get('message_type')  # SMS or LMS
        subject = request.form.get('subject', '')  # LMS only
        content = request.form.get('content', '').strip()
        recipient_type = request.form.get('recipient_type')  # individual, group, all
        recipient_ids = request.form.getlist('recipients[]')  # student IDs
        is_scheduled = request.form.get('is_scheduled') == 'on'
        scheduled_at_str = request.form.get('scheduled_at')
        notes = request.form.get('notes', '').strip()

        # 유효성 검사
        if not content:
            flash('메시지 내용을 입력해주세요.', 'error')
            return redirect(url_for('admin.send_message'))

        if message_type == 'LMS' and not subject:
            flash('LMS는 제목이 필요합니다.', 'error')
            return redirect(url_for('admin.send_message'))

        # 글자 수 체크
        content_bytes = len(content.encode('utf-8'))
        if message_type == 'SMS' and content_bytes > 90:
            flash('SMS는 90바이트(한글 약 45자)까지 입력 가능합니다.', 'error')
            return redirect(url_for('admin.send_message'))
        elif message_type == 'LMS' and content_bytes > 2000:
            flash('LMS는 2000바이트(한글 약 1000자)까지 입력 가능합니다.', 'error')
            return redirect(url_for('admin.send_message'))

        # 수신자 정보 수집
        recipients_data = []
        if recipient_type == 'all':
            # 전체 학생 또는 학부모
            all_students = Student.query.filter(Student.phone.isnot(None)).all()
            for student in all_students:
                if student.phone:
                    recipients_data.append({
                        'student_id': student.student_id,
                        'name': student.name,
                        'phone': student.phone
                    })
        else:
            # 선택한 학생들
            for student_id in recipient_ids:
                student = Student.query.get(student_id)
                if student and student.phone:
                    recipients_data.append({
                        'student_id': student.student_id,
                        'name': student.name,
                        'phone': student.phone
                    })

        if not recipients_data:
            flash('수신자를 선택해주세요.', 'error')
            return redirect(url_for('admin.send_message'))

        # 예약 발송 시간 처리
        scheduled_at = None
        if is_scheduled and scheduled_at_str:
            try:
                scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
            except:
                flash('예약 시간 형식이 올바르지 않습니다.', 'error')
                return redirect(url_for('admin.send_message'))

        # 메시지 생성
        message = Message(
            sender_id=current_user.user_id,
            message_type=message_type,
            subject=subject if message_type == 'LMS' else None,
            content=content,
            recipient_type=recipient_type,
            recipients_json=json.dumps(recipients_data, ensure_ascii=False),
            total_recipients=len(recipients_data),
            is_scheduled=is_scheduled,
            scheduled_at=scheduled_at,
            notes=notes
        )

        # Message 먼저 추가하고 flush하여 message_id 생성
        db.session.add(message)
        db.session.flush()  # message_id 생성

        # 즉시 발송
        if not is_scheduled:
            from app.utils.sms import send_sms_message as _send_sms

            success_count = 0
            failed_count = 0
            failed_names = []

            for recipient_data in recipients_data:
                phone = recipient_data['phone']
                ok, reason = _send_sms(phone, content, title=subject if message_type == 'LMS' else None)

                if ok:
                    success_count += 1
                    r_status = 'sent'
                    r_fail_reason = None
                else:
                    failed_count += 1
                    r_status = 'failed'
                    r_fail_reason = reason
                    failed_names.append(f"{recipient_data['name']}({reason})")

                recipient = MessageRecipient(
                    message_id=message.message_id,
                    student_id=recipient_data.get('student_id'),
                    recipient_name=recipient_data['name'],
                    recipient_phone=phone,
                    status=r_status,
                    sent_at=datetime.utcnow() if ok else None,
                    error_message=r_fail_reason
                )
                db.session.add(recipient)

            message.status = 'completed'
            message.sent_at = datetime.utcnow()
            message.success_count = success_count
            message.failed_count = failed_count

        db.session.commit()

        if is_scheduled:
            flash(f'문자가 {scheduled_at.strftime("%Y-%m-%d %H:%M")}에 발송 예약되었습니다.', 'success')
        elif failed_count > 0 and success_count == 0:
            flash(f'문자 발송 실패: {", ".join(failed_names[:5])}', 'error')
        elif failed_count > 0:
            flash(f'{message_type} {success_count}건 발송 완료, {failed_count}건 실패: {", ".join(failed_names[:3])}', 'warning')
        else:
            flash(f'{message_type} 문자 {success_count}건이 발송되었습니다.', 'success')

        return redirect(url_for('admin.message_detail', message_id=message.message_id))

    # GET: 학생 목록 + 학부모 목록 (자녀 정보 포함)
    students = Student.query.order_by(Student.grade, Student.name).all()
    parents_list = User.query.filter_by(role='parent', is_active=True).order_by(User.name).all()
    parents_with_children = []
    for parent in parents_list:
        children = db.session.query(Student).join(
            ParentStudent, ParentStudent.student_id == Student.student_id
        ).filter(ParentStudent.parent_id == parent.user_id).order_by(Student.grade, Student.name).all()
        parents_with_children.append({'parent': parent, 'children': children})

    return render_template('admin/send_message.html',
                         students=students,
                         parents_with_children=parents_with_children)


@admin_bp.route('/messages/<message_id>')
@login_required
@requires_permission_level(3)
def message_detail(message_id):
    """문자 발송 상세"""
    from app.models.message import Message
    import json

    message = Message.query.get_or_404(message_id)

    # 수신자 목록
    recipients_data = json.loads(message.recipients_json)

    return render_template('admin/message_detail.html',
                         message=message,
                         recipients_data=recipients_data)


# ==================== 전체 수업현황 (강사별 시간표) ====================

@admin_bp.route('/attendance-status')
@login_required
@requires_permission_level(2)  # 매니저 이상
def attendance_status():
    """전체 출석 현황"""
    from datetime import timedelta
    from sqlalchemy import func

    # 필터 파라미터
    course_filter = request.args.get('course_id', '').strip()
    student_filter = request.args.get('student_id', '').strip()
    teacher_filter = request.args.get('teacher_id', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    status_filter = request.args.get('status', '').strip()

    # 기본 날짜 범위 (최근 30일)
    today = datetime.utcnow().date()
    if not date_from:
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    # 쿼리 빌드 (Student는 Attendance.student_id 기준으로 명시적 join)
    query = Attendance.query\
        .join(CourseSession, Attendance.session_id == CourseSession.session_id)\
        .join(Course, CourseSession.course_id == Course.course_id)\
        .join(Student, Attendance.student_id == Student.student_id)

    # 날짜 필터
    if date_from:
        query = query.filter(CourseSession.session_date >= date_from)
    if date_to:
        query = query.filter(CourseSession.session_date <= date_to)

    # 수업 필터
    if course_filter:
        query = query.filter(Course.course_id == course_filter)

    # 강사 필터
    if teacher_filter:
        query = query.filter(Course.teacher_id == teacher_filter)

    # 학생 필터
    if student_filter:
        query = query.filter(Student.student_id == student_filter)

    # 상태 필터
    if status_filter:
        query = query.filter(Attendance.status == status_filter)

    # 출석 레코드 조회
    attendances = query.order_by(
        CourseSession.session_date.desc(),
        CourseSession.start_time.desc()
    ).limit(100).all()

    # 전체 통계
    total_query = Attendance.query\
        .join(CourseSession, Attendance.session_id == CourseSession.session_id)\
        .join(Course, CourseSession.course_id == Course.course_id)\
        .join(Student, Attendance.student_id == Student.student_id)
    if date_from:
        total_query = total_query.filter(CourseSession.session_date >= date_from)
    if date_to:
        total_query = total_query.filter(CourseSession.session_date <= date_to)
    if course_filter:
        total_query = total_query.filter(Course.course_id == course_filter)
    if teacher_filter:
        total_query = total_query.filter(Course.teacher_id == teacher_filter)
    if student_filter:
        total_query = total_query.filter(Student.student_id == student_filter)

    total_count = total_query.count()
    present_count = total_query.filter(Attendance.status == 'present').count()
    late_count = total_query.filter(Attendance.status == 'late').count()
    absent_count = total_query.filter(Attendance.status == 'absent').count()
    excused_count = total_query.filter(Attendance.status == 'excused').count()

    attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0

    # 반별 통계 (course_filter가 없을 때만)
    course_stats = []
    if not course_filter and not student_filter:
        course_stats_query = db.session.query(
            Course.course_id,
            Course.course_name,
            func.count(Attendance.attendance_id).label('total'),
            func.sum(case((Attendance.status == 'present', 1), else_=0)).label('present'),
            func.sum(case((Attendance.status == 'late', 1), else_=0)).label('late'),
            func.sum(case((Attendance.status == 'absent', 1), else_=0)).label('absent')
        ).join(CourseSession, Course.course_id == CourseSession.course_id)\
         .join(Attendance, CourseSession.session_id == Attendance.session_id)

        if date_from:
            course_stats_query = course_stats_query.filter(CourseSession.session_date >= date_from)
        if date_to:
            course_stats_query = course_stats_query.filter(CourseSession.session_date <= date_to)

        course_stats = course_stats_query.group_by(Course.course_id, Course.course_name)\
                                         .order_by(func.count(Attendance.attendance_id).desc())\
                                         .limit(10).all()

    # 학생별 통계 (student_filter가 없을 때만, course_filter가 있으면 해당 수업의 학생만)
    student_stats = []
    if not student_filter:
        student_stats_query = db.session.query(
            Student.student_id,
            Student.name,
            Student.grade,
            func.count(Attendance.attendance_id).label('total'),
            func.sum(case((Attendance.status == 'present', 1), else_=0)).label('present'),
            func.sum(case((Attendance.status == 'late', 1), else_=0)).label('late'),
            func.sum(case((Attendance.status == 'absent', 1), else_=0)).label('absent')
        ).join(Attendance, Student.student_id == Attendance.student_id)\
         .join(CourseSession, Attendance.session_id == CourseSession.session_id)

        if date_from:
            student_stats_query = student_stats_query.filter(CourseSession.session_date >= date_from)
        if date_to:
            student_stats_query = student_stats_query.filter(CourseSession.session_date <= date_to)
        if course_filter:
            student_stats_query = student_stats_query.join(Course, CourseSession.course_id == Course.course_id)\
                                                     .filter(Course.course_id == course_filter)

        student_stats = student_stats_query.group_by(Student.student_id, Student.name, Student.grade)\
                                           .order_by(func.count(Attendance.attendance_id).desc())\
                                           .limit(20).all()

    # 전체 수업 목록 (필터용)
    courses = Course.query.order_by(Course.course_name).all()

    # 전체 학생 목록 (필터용)
    students = Student.query.order_by(Student.name).all()

    # 전체 강사 목록 (필터용)
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()

    return render_template('admin/attendance_status.html',
                         attendances=attendances,
                         courses=courses,
                         students=students,
                         teachers=teachers,
                         course_filter=course_filter,
                         student_filter=student_filter,
                         teacher_filter=teacher_filter,
                         date_from=date_from,
                         date_to=date_to,
                         status_filter=status_filter,
                         total_count=total_count,
                         present_count=present_count,
                         late_count=late_count,
                         absent_count=absent_count,
                         excused_count=excused_count,
                         attendance_rate=attendance_rate,
                         course_stats=course_stats,
                         student_stats=student_stats)


@admin_bp.route('/all-schedule')
@login_required
@requires_permission_level(2)  # 매니저 이상
def all_schedule():
    """수업 현황 - 강사별 시간표 (일간/주간/월간)"""
    from datetime import timedelta
    import calendar as cal_module

    # 전체 강사 목록
    teachers = User.query.filter_by(role='teacher', is_active=True)\
        .order_by(User.name).all()

    # 선택된 강사 (기본값: 첫 번째 강사)
    selected_teacher_id = request.args.get('teacher_id', '')
    if not selected_teacher_id and teachers:
        selected_teacher_id = teachers[0].user_id

    selected_teacher = None
    if selected_teacher_id:
        selected_teacher = User.query.get(selected_teacher_id)

    today = datetime.utcnow().date()
    view_mode = request.args.get('view', 'weekly')  # daily, weekly, monthly

    # ── 공통: 강사 수업 ID 목록 ──
    teacher_course_ids = []
    if selected_teacher:
        teacher_courses = Course.query.filter_by(
            teacher_id=selected_teacher_id
        ).all()
        teacher_course_ids = [c.course_id for c in teacher_courses]

    # ── 일간 뷰 ──
    day_offset = int(request.args.get('day', 0))
    target_date = today + timedelta(days=day_offset)
    daily_sessions = []
    if view_mode == 'daily' and teacher_course_ids:
        daily_sessions = CourseSession.query.filter(
            CourseSession.course_id.in_(teacher_course_ids),
            CourseSession.session_date == target_date
        ).order_by(CourseSession.start_time).all()

    # ── 주간 뷰 ──
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    week_offset = int(request.args.get('week', 0))
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    weekly_schedule = {i: [] for i in range(7)}
    weekly_courses_only = {i: [] for i in range(7)}   # 세션 없이 Course.weekday로만 표시
    weekly_mismatch = []  # 요일 불일치 세션 목록
    if view_mode == 'weekly' and teacher_course_ids:
        sessions = CourseSession.query.filter(
            CourseSession.course_id.in_(teacher_course_ids),
            CourseSession.session_date >= week_start,
            CourseSession.session_date <= week_end
        ).order_by(CourseSession.session_date, CourseSession.start_time).all()
        session_course_ids_this_week = set()
        for session in sessions:
            day_index = session.session_date.weekday()
            weekly_schedule[day_index].append(session)
            session_course_ids_this_week.add(session.course_id)
            # 요일 불일치 감지
            if (session.course.weekday is not None and
                    session.session_date.weekday() != session.course.weekday):
                weekly_mismatch.append(session)
        # 이번 주 세션이 없는 수업 → Course.weekday 기준으로 표시
        for course in teacher_courses:
            if (course.course_id not in session_course_ids_this_week and
                    course.weekday is not None and
                    not course.is_terminated and
                    course.status == 'active'):
                weekly_courses_only[course.weekday].append(course)

    # ── 월간 뷰 ──
    month_offset = int(request.args.get('month', 0))
    base_year = today.year
    base_month = today.month + month_offset
    while base_month > 12:
        base_month -= 12
        base_year += 1
    while base_month < 1:
        base_month += 12
        base_year -= 1
    from datetime import date as date_cls
    month_first = date_cls(base_year, base_month, 1)
    month_last = date_cls(base_year, base_month, cal_module.monthrange(base_year, base_month)[1])

    # 달력 그리드: 월요일 시작, 6주 × 7일
    cal_grid = cal_module.monthcalendar(base_year, base_month)  # [[0,0,1,2,...], ...]

    monthly_sessions = {}  # {date: [sessions]}
    m_sessions_flat = []
    if view_mode == 'monthly' and teacher_course_ids:
        m_sessions_flat = CourseSession.query.filter(
            CourseSession.course_id.in_(teacher_course_ids),
            CourseSession.session_date >= month_first,
            CourseSession.session_date <= month_last
        ).order_by(CourseSession.start_time).all()
        for s in m_sessions_flat:
            monthly_sessions.setdefault(s.session_date, []).append(s)

    # 뷰별 통계용 flat 세션 목록
    if view_mode == 'daily':
        stat_sessions = daily_sessions
    elif view_mode == 'weekly':
        stat_sessions = [s for day in weekly_schedule.values() for s in day]
    else:
        stat_sessions = m_sessions_flat

    # 시간대 범위 (8:00 ~ 22:00)
    time_slots = [f"{h:02d}:00" for h in range(8, 22)]

    return render_template('admin/all_schedule.html',
                         teachers=teachers,
                         selected_teacher=selected_teacher,
                         selected_teacher_id=selected_teacher_id,
                         view_mode=view_mode,
                         # daily
                         target_date=target_date,
                         day_offset=day_offset,
                         daily_sessions=daily_sessions,
                         # weekly
                         week_start=week_start,
                         week_end=week_end,
                         week_offset=week_offset,
                         weekly_schedule=weekly_schedule,
                         weekly_courses_only=weekly_courses_only,
                         weekly_mismatch=weekly_mismatch,
                         time_slots=time_slots,
                         # monthly
                         month_offset=month_offset,
                         month_first=month_first,
                         month_last=month_last,
                         cal_grid=cal_grid,
                         monthly_sessions=monthly_sessions,
                         base_year=base_year,
                         base_month=base_month,
                         stat_sessions=stat_sessions,
                         today=today,
                         date_cls=date_cls,
                         timedelta=timedelta)


# ==================== 보강수업 신청 관리 ====================

@admin_bp.route('/makeup-requests')
@login_required
@requires_permission_level(2)
def makeup_requests():
    """보강수업 신청 관리"""
    from app.models.makeup_request import MakeupClassRequest
    
    # 필터
    status_filter = request.args.get('status', '').strip()
    
    query = MakeupClassRequest.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # 신청 목록 조회
    requests = query.order_by(MakeupClassRequest.request_date.desc()).all()
    
    # 통계
    total_requests = MakeupClassRequest.query.count()
    pending_requests = MakeupClassRequest.query.filter_by(status='pending').count()
    approved_requests = MakeupClassRequest.query.filter_by(status='approved').count()
    rejected_requests = MakeupClassRequest.query.filter_by(status='rejected').count()
    
    return render_template('admin/makeup_requests.html',
                         requests=requests,
                         status_filter=status_filter,
                         total_requests=total_requests,
                         pending_requests=pending_requests,
                         approved_requests=approved_requests,
                         rejected_requests=rejected_requests)


@admin_bp.route('/makeup-requests/<request_id>/approve', methods=['POST'])
@login_required
@requires_permission_level(2)
def approve_makeup_request(request_id):
    """보강수업 신청 승인 및 1회 수업 생성"""
    from app.models.makeup_request import MakeupClassRequest
    from datetime import date, time, timedelta
    
    makeup_request = MakeupClassRequest.query.get_or_404(request_id)
    
    if makeup_request.status != 'pending':
        flash('이미 처리된 신청입니다.', 'warning')
        return redirect(url_for('admin.makeup_requests'))
    
    # 원본 수업 정보
    original_course = makeup_request.requested_course
    student = makeup_request.student
    
    # 보강수업 날짜 (POST 데이터에서 가져오기, 없으면 다음 주 같은 요일)
    makeup_date_str = request.form.get('makeup_date', '').strip()
    if makeup_date_str:
        makeup_date = datetime.strptime(makeup_date_str, '%Y-%m-%d').date()
    else:
        # 기본값: 다음 주 같은 요일
        today = date.today()
        days_ahead = original_course.weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        makeup_date = today + timedelta(days=days_ahead)
    
    # 1회 보강수업 생성
    # 고유한 course_code 생성 (날짜 + 요청ID 일부)
    unique_code = f"MAKEUP{makeup_date.strftime('%y%m%d')}{makeup_request.request_id[:8]}"

    makeup_course = Course(
        course_name=f"[보강] {original_course.course_name} - {student.name}",
        course_code=unique_code,
        grade=original_course.grade,
        course_type='보강수업',
        teacher_id=original_course.teacher_id,
        weekday=makeup_date.weekday(),  # Python weekday: 0=월, 6=일
        start_time=original_course.start_time,
        end_time=original_course.end_time,
        start_date=makeup_date,
        end_date=makeup_date,
        availability_status='available',
        makeup_class_allowed=False,  # 보강수업은 재보강 불가
        schedule_type='custom',
        max_students=1,  # 1:1 보강
        price_per_session=0,  # 보강수업은 무료
        status='active',
        created_by=current_user.user_id,
        description=f"{student.name} 학생의 보강수업 (원수업: {original_course.course_name})"
    )
    
    db.session.add(makeup_course)
    db.session.flush()
    
    # 1회 세션 생성
    makeup_session = CourseSession(
        course_id=makeup_course.course_id,
        session_number=1,
        session_date=makeup_date,
        start_time=original_course.start_time,
        end_time=original_course.end_time,
        topic=f"{student.name} 보강수업",
        status='scheduled'
    )
    
    db.session.add(makeup_session)
    db.session.flush()
    
    # 학생 자동 등록
    from app.utils.course_utils import enroll_student_to_course
    enrollment = enroll_student_to_course(makeup_course.course_id, student.student_id)
    
    # 신청 상태 업데이트
    makeup_request.status = 'approved'
    makeup_request.admin_response_date = datetime.utcnow()
    makeup_request.admin_response_by = current_user.user_id
    makeup_request.created_makeup_course_id = makeup_course.course_id
    makeup_request.admin_notes = request.form.get('admin_notes', '').strip()
    
    # 학생/학부모에게 알림
    requester = makeup_request.requester
    if requester:
        notification = Notification(
            user_id=requester.user_id,
            notification_type='makeup_approved',
            title='보강수업 신청이 승인되었습니다',
            message=f'"{original_course.course_name}" 보강수업 신청이 승인되었습니다. 보강일: {makeup_date.strftime("%Y년 %m월 %d일")}',
            related_entity_type='course',
            related_entity_id=makeup_course.course_id
        )
        db.session.add(notification)

    # 학부모에게도 알림 (학생이 신청한 경우)
    if requester and requester.role == 'student':
        from app.models.parent_student import ParentStudent
        parent_links = ParentStudent.query.filter_by(student_id=student.student_id).all()
        for link in parent_links:
            parent_notification = Notification(
                user_id=link.parent_id,
                notification_type='makeup_approved',
                title=f'{student.name} 학생의 보강수업 신청 승인',
                message=f'{student.name} 학생의 "{original_course.course_name}" 보강수업 신청이 승인되었습니다. 보강일: {makeup_date.strftime("%Y년 %m월 %d일")}',
                related_entity_type='course',
                related_entity_id=makeup_course.course_id
            )
            db.session.add(parent_notification)
    
    db.session.commit()
    
    flash(f'보강수업 신청이 승인되었습니다. 보강수업이 생성되었습니다: {makeup_course.course_name}', 'success')
    return redirect(url_for('admin.makeup_requests'))


@admin_bp.route('/makeup-requests/<request_id>/reject', methods=['POST'])
@login_required
@requires_permission_level(2)
def reject_makeup_request(request_id):
    """보강수업 신청 거절"""
    from app.models.makeup_request import MakeupClassRequest
    
    makeup_request = MakeupClassRequest.query.get_or_404(request_id)
    
    if makeup_request.status != 'pending':
        flash('이미 처리된 신청입니다.', 'warning')
        return redirect(url_for('admin.makeup_requests'))
    
    # 거절 사유
    reject_reason = request.form.get('reject_reason', '').strip()
    
    # 신청 상태 업데이트
    makeup_request.status = 'rejected'
    makeup_request.admin_response_date = datetime.utcnow()
    makeup_request.admin_response_by = current_user.user_id
    makeup_request.admin_notes = reject_reason
    
    # 신청자에게 알림
    requester = makeup_request.requester
    student = makeup_request.student
    original_course = makeup_request.requested_course

    if requester:
        notification = Notification(
            user_id=requester.user_id,
            notification_type='makeup_rejected',
            title='보강수업 신청이 거절되었습니다',
            message=f'"{original_course.course_name}" 보강수업 신청이 거절되었습니다. 사유: {reject_reason or "없음"}',
            related_entity_type='makeup_request',
            related_entity_id=request_id
        )
        db.session.add(notification)

        # 학부모에게도 알림 (학생이 신청한 경우)
        if requester.role == 'student':
            from app.models.parent_student import ParentStudent
            parent_links = ParentStudent.query.filter_by(student_id=student.student_id, is_active=True).all()
            for link in parent_links:
                parent_notification = Notification(
                    user_id=link.parent_id,
                    notification_type='makeup_rejected',
                    title=f'{student.name} 학생의 보강수업 신청 거절',
                    message=f'{student.name} 학생의 "{original_course.course_name}" 보강수업 신청이 거절되었습니다. 사유: {reject_reason or "없음"}',
                    related_entity_type='makeup_request',
                    related_entity_id=request_id
                )
                db.session.add(parent_notification)

    db.session.commit()

    flash('보강수업 신청이 거절되었습니다.', 'info')
    return redirect(url_for('admin.makeup_requests'))


# ============================================================================
# 교재 관리 (Teaching Materials)
# ============================================================================

@admin_bp.route('/teaching-materials')
@login_required
@requires_permission_level(2)
def teaching_materials():
    """교재 목록"""
    # 필터 파라미터
    grade_filter = request.args.get('grade', '')
    status_filter = request.args.get('status', 'all')  # active, expired, all
    is_public_filter = request.args.get('is_public', '')  # '', '0', '1'

    # 기본 쿼리
    query = TeachingMaterial.query

    # 학년 필터
    if grade_filter:
        query = query.filter(TeachingMaterial.grade == grade_filter)

    # 공개 여부 필터
    if is_public_filter == '1':
        query = query.filter(TeachingMaterial.is_public == True)
    elif is_public_filter == '0':
        query = query.filter(TeachingMaterial.is_public == False)

    # 상태 필터
    today = date.today()
    if status_filter == 'active':
        query = query.filter(
            TeachingMaterial.is_public == True,
            TeachingMaterial.publish_date <= today,
            db.or_(TeachingMaterial.end_date == None, TeachingMaterial.end_date >= today)
        )
    elif status_filter == 'expired':
        query = query.filter(TeachingMaterial.end_date < today)

    materials = query.order_by(TeachingMaterial.created_at.desc()).all()

    # 통계
    today = date.today()
    stats = {
        'total': TeachingMaterial.query.count(),
        'active': TeachingMaterial.query.filter(TeachingMaterial.is_public == True).count(),
        'inactive': TeachingMaterial.query.filter(TeachingMaterial.is_public == False).count(),
        'total_downloads': db.session.query(func.sum(TeachingMaterial.download_count)).scalar() or 0,
        'by_grade': {}
    }

    # 학년별 통계
    grade_counts = db.session.query(
        TeachingMaterial.grade,
        func.count(TeachingMaterial.material_id)
    ).group_by(TeachingMaterial.grade).all()

    for grade, count in grade_counts:
        stats['by_grade'][grade] = count

    return render_template('admin/teaching_materials.html',
                         materials=materials,
                         stats=stats,
                         grade_filter=grade_filter,
                         is_public_filter=is_public_filter,
                         status_filter=status_filter,
                         format_file_size=format_file_size)


@admin_bp.route('/teaching-materials/api/books/search')
@login_required
@requires_permission_level(2)
def search_books_for_material():
    """교재 연결용 도서 검색 API (학년 + 제목)"""
    grade = request.args.get('grade', '').strip()
    title = request.args.get('title', '').strip()

    query = Book.query
    if grade:
        query = query.filter(Book.grade_tags.like(f'%{grade}%'))
    if title:
        query = query.filter(Book.title.ilike(f'%{title}%'))

    books = query.order_by(Book.title).limit(30).all()
    return jsonify([{
        'book_id': b.book_id,
        'title': b.title,
        'author': b.author or '',
        'publisher': b.publisher or '',
        'cover_image_url': b.cover_image_url or '',
        'grade_tags': b.grade_tags or '[]',
    } for b in books])


@admin_bp.route('/teaching-materials/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def create_teaching_material():
    """교재 등록 (복수 파일 지원)"""
    form = TeachingMaterialForm()

    if form.validate_on_submit():
        # 업로드된 파일 목록 (최대 5개)
        uploaded_files = request.files.getlist('file_uploads')
        uploaded_files = [f for f in uploaded_files if f and f.filename]

        if not uploaded_files:
            flash('파일을 하나 이상 선택하세요.', 'danger')
            return render_template('admin/teaching_material_form.html', form=form, mode='create')

        if len(uploaded_files) > 10:
            flash('파일은 최대 10개까지 업로드할 수 있습니다.', 'danger')
            return render_template('admin/teaching_material_form.html', form=form, mode='create')

        # 허용 확장자
        allowed_exts = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'hwp', 'zip'}
        for f in uploaded_files:
            ext = os.path.splitext(secure_filename(f.filename))[1].lstrip('.').lower()
            if ext not in allowed_exts:
                flash(f'허용되지 않는 파일 형식: {f.filename}. 허용: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, HWP, ZIP', 'danger')
                return render_template('admin/teaching_material_form.html', form=form, mode='create')

        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'materials')
        os.makedirs(upload_folder, exist_ok=True)

        # 대상 선택 JSON 생성 및 grade 자동 설정
        if form.target_type.data == 'grade':
            target_grades = form.target_grades.data or []
            target_audience = json.dumps({'type': 'grade', 'grades': target_grades}, ensure_ascii=False)
            auto_grade = target_grades[0] if target_grades else '전체'
        else:
            course_ids = form.target_course_ids.data.split(',') if form.target_course_ids.data else []
            course_ids = [cid.strip() for cid in course_ids if cid.strip()]
            target_audience = json.dumps({'type': 'course', 'course_ids': course_ids}, ensure_ascii=False)
            auto_grade = '수업별'

        # 첫 번째 파일 정보로 TeachingMaterial 레코드 생성 (backward compat)
        first_file = uploaded_files[0]
        first_name = secure_filename(first_file.filename)
        first_ext = os.path.splitext(first_name)[1]
        first_stored = f"{uuid.uuid4().hex}{first_ext}"

        book_id = request.form.get('book_id') or None

        material = TeachingMaterial(
            title=form.title.data,
            grade=auto_grade,
            original_filename=first_name,
            storage_path=os.path.join('materials', first_stored),
            file_size=0,
            file_type=first_ext.lstrip('.').lower(),
            publish_date=form.publish_date.data,
            end_date=form.end_date.data,
            is_public=form.is_public.data,
            target_audience=target_audience,
            created_by=current_user.user_id,
            book_id=book_id
        )
        db.session.add(material)
        db.session.flush()  # material_id 확보

        # 각 파일 저장 및 TeachingMaterialFile 생성
        total_size = 0
        for idx, file in enumerate(uploaded_files):
            orig_name = secure_filename(file.filename)
            file_ext = os.path.splitext(orig_name)[1]
            stored_name = f"{uuid.uuid4().hex}{file_ext}" if idx > 0 else first_stored
            file_path = os.path.join(upload_folder, stored_name)
            file.save(file_path)
            size = os.path.getsize(file_path)
            total_size += size

            tmf = TeachingMaterialFile(
                material_id=material.material_id,
                original_filename=orig_name,
                storage_path=os.path.join('materials', stored_name),
                file_size=size,
                file_type=file_ext.lstrip('.').lower(),
                sort_order=idx
            )
            db.session.add(tmf)

        material.file_size = total_size
        db.session.commit()

        flash(f'교재가 등록되었습니다. ({len(uploaded_files)}개 파일)', 'success')
        return redirect(url_for('admin.teaching_material_detail', material_id=material.material_id))

    return render_template('admin/teaching_material_form.html', form=form, mode='create')


@admin_bp.route('/teaching-materials/<material_id>')
@login_required
@requires_permission_level(2)
def teaching_material_detail(material_id):
    """교재 상세"""
    material = TeachingMaterial.query.get_or_404(material_id)

    # 다운로드 내역
    downloads = TeachingMaterialDownload.query.filter_by(
        material_id=material_id
    ).order_by(TeachingMaterialDownload.downloaded_at.desc()).limit(20).all()

    # 대상 선택 파싱
    try:
        target_audience = json.loads(material.target_audience)
    except:
        target_audience = {'type': 'grade', 'grades': []}

    # 대상 수업명 가져오기 (course 타입일 경우)
    target_courses = []
    if target_audience.get('type') == 'course':
        course_ids = target_audience.get('course_ids', [])
        if course_ids:
            target_courses = Course.query.filter(Course.course_id.in_(course_ids)).all()

    return render_template('admin/teaching_material_detail.html',
                         material=material,
                         downloads=downloads,
                         target_audience=target_audience,
                         target_courses=target_courses,
                         format_file_size=format_file_size)


@admin_bp.route('/teaching-materials/<material_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def edit_teaching_material(material_id):
    """교재 수정"""
    material = TeachingMaterial.query.get_or_404(material_id)
    form = TeachingMaterialForm(obj=material)

    # 기존 대상 선택 로드
    try:
        target_audience = json.loads(material.target_audience)
        if request.method == 'GET':
            form.target_type.data = target_audience.get('type', 'grade')
            if target_audience.get('type') == 'grade':
                form.target_grades.data = target_audience.get('grades', [])
            else:
                form.target_course_ids.data = ','.join(target_audience.get('course_ids', []))
    except:
        target_audience = {'type': 'grade', 'grades': []}

    if form.validate_on_submit():
        # 대상 선택 업데이트 및 grade 자동 설정
        if form.target_type.data == 'grade':
            target_grades = form.target_grades.data or []
            target_audience = json.dumps({'type': 'grade', 'grades': target_grades}, ensure_ascii=False)
            auto_grade = target_grades[0] if target_grades else '전체'
        else:
            course_ids = form.target_course_ids.data.split(',') if form.target_course_ids.data else []
            course_ids = [cid.strip() for cid in course_ids if cid.strip()]
            target_audience = json.dumps({'type': 'course', 'course_ids': course_ids}, ensure_ascii=False)
            auto_grade = '수업별'

        # 기본 정보 업데이트
        material.title = form.title.data
        material.grade = auto_grade
        material.publish_date = form.publish_date.data
        material.end_date = form.end_date.data
        material.is_public = form.is_public.data
        material.target_audience = target_audience
        material.book_id = request.form.get('book_id') or None

        # 새 파일 추가 (기존 파일 유지, 추가만)
        new_files = request.files.getlist('file_uploads')
        new_files = [f for f in new_files if f and f.filename]

        if new_files:
            allowed_exts = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'hwp', 'zip'}
            current_count = len(material.files)
            if current_count + len(new_files) > 10:
                flash(f'파일은 최대 10개까지 등록 가능합니다. (현재 {current_count}개)', 'danger')
                return render_template('admin/teaching_material_form.html',
                                     form=form, mode='edit', material=material,
                                     target_audience=target_audience)

            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'materials')
            os.makedirs(upload_folder, exist_ok=True)
            next_order = current_count

            for file in new_files:
                ext = os.path.splitext(secure_filename(file.filename))[1].lstrip('.').lower()
                if ext not in allowed_exts:
                    flash(f'허용되지 않는 파일 형식: {file.filename}', 'danger')
                    continue
                orig_name = secure_filename(file.filename)
                file_ext = os.path.splitext(orig_name)[1]
                stored_name = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(upload_folder, stored_name)
                file.save(file_path)
                size = os.path.getsize(file_path)

                tmf = TeachingMaterialFile(
                    material_id=material.material_id,
                    original_filename=orig_name,
                    storage_path=os.path.join('materials', stored_name),
                    file_size=size,
                    file_type=file_ext.lstrip('.').lower(),
                    sort_order=next_order
                )
                db.session.add(tmf)
                next_order += 1

            # 총 파일 크기 업데이트
            db.session.flush()
            material.file_size = sum(f.file_size for f in material.files)

        db.session.commit()
        flash('교재가 수정되었습니다.', 'success')
        return redirect(url_for('admin.teaching_material_detail', material_id=material.material_id))

    return render_template('admin/teaching_material_form.html',
                         form=form,
                         mode='edit',
                         material=material,
                         target_audience=target_audience)


@admin_bp.route('/teaching-materials/<material_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def delete_teaching_material(material_id):
    """교재 삭제 (모든 첨부 파일 포함)"""
    material = TeachingMaterial.query.get_or_404(material_id)

    # 신규 방식: TeachingMaterialFile 파일들 삭제
    for tmf in material.files:
        fp = os.path.join(current_app.config['UPLOAD_FOLDER'], tmf.storage_path)
        if os.path.exists(fp):
            os.remove(fp)

    # 구형 단일 파일 삭제 (backward compat)
    if not material.files:
        old_fp = os.path.join(current_app.config['UPLOAD_FOLDER'], material.storage_path)
        if os.path.exists(old_fp):
            os.remove(old_fp)

    db.session.delete(material)
    db.session.commit()

    flash('교재가 삭제되었습니다.', 'info')
    return redirect(url_for('admin.teaching_materials'))


@admin_bp.route('/teaching-materials/<material_id>/files/<file_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def delete_teaching_material_file(material_id, file_id):
    """교재 개별 파일 삭제"""
    material = TeachingMaterial.query.get_or_404(material_id)
    tmf = TeachingMaterialFile.query.filter_by(file_id=file_id, material_id=material_id).first_or_404()

    # 파일 삭제
    fp = os.path.join(current_app.config['UPLOAD_FOLDER'], tmf.storage_path)
    if os.path.exists(fp):
        os.remove(fp)

    db.session.delete(tmf)
    db.session.flush()

    # 남은 파일이 없으면 교재 자체 삭제 여부 경고
    remaining = len(material.files)
    if remaining == 0:
        flash('마지막 파일을 삭제했습니다. 새 파일을 업로드하세요.', 'warning')
    else:
        # 총 파일 크기 갱신 및 대표 파일 정보 갱신
        material.file_size = sum(f.file_size for f in material.files)
        first = material.files[0]
        material.original_filename = first.original_filename
        material.storage_path = first.storage_path
        material.file_type = first.file_type
        flash('파일이 삭제되었습니다.', 'success')

    db.session.commit()
    return redirect(url_for('admin.edit_teaching_material', material_id=material_id))


@admin_bp.route('/teaching-materials/<material_id>/files/<file_id>/download')
@login_required
@requires_permission_level(2)
def download_teaching_material_file(material_id, file_id):
    """교재 개별 파일 다운로드"""
    tmf = TeachingMaterialFile.query.filter_by(file_id=file_id, material_id=material_id).first_or_404()
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], tmf.storage_path)

    if not os.path.exists(file_path):
        flash('파일을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('admin.teaching_material_detail', material_id=material_id))

    # 다운로드 기록
    material = TeachingMaterial.query.get(material_id)
    if material:
        download = TeachingMaterialDownload(material_id=material_id, user_id=current_user.user_id)
        db.session.add(download)
        material.download_count += 1
        db.session.commit()

    return send_file(file_path, as_attachment=True, download_name=tmf.original_filename)


@admin_bp.route('/teaching-materials/<material_id>/toggle-active', methods=['POST'])
@login_required
@requires_permission_level(2)
def toggle_material_active(material_id):
    """교재 공개/비공개 토글"""
    material = TeachingMaterial.query.get_or_404(material_id)

    # is_public 상태 토글
    material.is_public = not material.is_public
    db.session.commit()

    status_text = '공개' if material.is_public else '비공개'
    flash(f'교재가 {status_text} 상태로 변경되었습니다.', 'success')

    return redirect(url_for('admin.teaching_material_detail', material_id=material_id))


@admin_bp.route('/teaching-materials/<material_id>/download')
@login_required
@requires_permission_level(2)
def download_teaching_material(material_id):
    """교재 다운로드 (관리자용)"""
    material = TeachingMaterial.query.get_or_404(material_id)

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], material.storage_path)

    if not os.path.exists(file_path):
        flash('파일을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('admin.teaching_material_detail', material_id=material_id))

    # 다운로드 기록
    download = TeachingMaterialDownload(
        material_id=material_id,
        user_id=current_user.user_id
    )
    db.session.add(download)

    material.download_count += 1
    db.session.commit()

    return send_file(file_path, as_attachment=True, download_name=material.original_filename)


# ============================================================================
# 동영상 관리 (Videos)
# ============================================================================

@admin_bp.route('/videos')
@login_required
@requires_permission_level(2)
def videos():
    """동영상 목록"""
    # 필터 파라미터
    grade_filter = request.args.get('grade', '')
    status_filter = request.args.get('status', 'active')
    is_public_filter = request.args.get('is_public', '')

    # 기본 쿼리
    query = Video.query

    # 학년 필터
    if grade_filter:
        query = query.filter(Video.grade == grade_filter)

    # 공개 여부 필터
    if is_public_filter == '1':
        query = query.filter(Video.is_public == True)
    elif is_public_filter == '0':
        query = query.filter(Video.is_public == False)

    # 상태 필터
    today = date.today()
    if status_filter == 'active':
        query = query.filter(
            Video.is_public == True,
            Video.publish_date <= today,
            Video.end_date >= today
        )
    elif status_filter == 'expired':
        query = query.filter(Video.end_date < today)

    videos = query.order_by(Video.created_at.desc()).all()

    # 통계
    today = date.today()
    stats = {
        'total': Video.query.count(),
        'active': Video.query.filter(Video.is_public == True).count(),
        'inactive': Video.query.filter(Video.is_public == False).count(),
        'total_views': db.session.query(func.sum(Video.view_count)).scalar() or 0,
        'by_grade': {}
    }

    # 학년별 통계
    grade_counts = db.session.query(
        Video.grade,
        func.count(Video.video_id)
    ).group_by(Video.grade).all()

    for grade, count in grade_counts:
        stats['by_grade'][grade] = count

    return render_template('admin/videos.html',
                         videos=videos,
                         stats=stats,
                         grade_filter=grade_filter,
                         is_public_filter=is_public_filter,
                         status_filter=status_filter)


@admin_bp.route('/videos/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def create_video():
    """동영상 등록"""
    form = VideoForm()

    if form.validate_on_submit():
        # YouTube 비디오 ID 추출
        video_id = extract_youtube_video_id(form.youtube_url.data)

        # 대상 선택 JSON 생성 및 grade 자동 설정
        if form.target_type.data == 'grade':
            target_grades = form.target_grades.data or []
            target_audience = json.dumps({
                'type': 'grade',
                'grades': target_grades
            }, ensure_ascii=False)
            # 첫 번째 대상 학년을 grade로 설정 (없으면 '전체')
            auto_grade = target_grades[0] if target_grades else '전체'
        else:
            course_ids = form.target_course_ids.data.split(',') if form.target_course_ids.data else []
            course_ids = [cid.strip() for cid in course_ids if cid.strip()]
            target_audience = json.dumps({
                'type': 'course',
                'course_ids': course_ids
            }, ensure_ascii=False)
            # 수업별 대상인 경우 '수업별'로 설정
            auto_grade = '수업별'

        # 동영상 생성
        video = Video(
            title=form.title.data,
            grade=auto_grade,
            youtube_url=form.youtube_url.data,
            youtube_video_id=video_id,
            publish_date=form.publish_date.data,
            end_date=form.end_date.data,
            is_public=form.is_public.data,
            target_audience=target_audience,
            created_by=current_user.user_id
        )

        db.session.add(video)
        db.session.commit()

        flash('동영상이 등록되었습니다.', 'success')
        return redirect(url_for('admin.video_detail', video_id=video.video_id))

    return render_template('admin/video_form.html', form=form, mode='create')


@admin_bp.route('/videos/<video_id>')
@login_required
@requires_permission_level(2)
def video_detail(video_id):
    """동영상 상세"""
    video = Video.query.get_or_404(video_id)

    # 조회 내역
    views = VideoView.query.filter_by(
        video_id=video_id
    ).order_by(VideoView.viewed_at.desc()).limit(20).all()

    # 대상 선택 파싱
    try:
        target_audience = json.loads(video.target_audience)
    except:
        target_audience = {'type': 'grade', 'grades': []}

    # 대상 수업명 가져오기
    target_courses = []
    if target_audience.get('type') == 'course':
        course_ids = target_audience.get('course_ids', [])
        if course_ids:
            target_courses = Course.query.filter(Course.course_id.in_(course_ids)).all()

    return render_template('admin/video_detail.html',
                         video=video,
                         views=views,
                         target_audience=target_audience,
                         target_courses=target_courses)


@admin_bp.route('/videos/<video_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def edit_video(video_id):
    """동영상 수정"""
    video = Video.query.get_or_404(video_id)
    form = VideoForm(obj=video)

    # 기존 대상 선택 로드
    try:
        target_audience = json.loads(video.target_audience)
        if request.method == 'GET':
            form.target_type.data = target_audience.get('type', 'grade')
            if target_audience.get('type') == 'grade':
                form.target_grades.data = target_audience.get('grades', [])
            else:
                form.target_course_ids.data = ','.join(target_audience.get('course_ids', []))
    except:
        target_audience = {'type': 'grade', 'grades': []}

    if form.validate_on_submit():
        # 대상 선택 업데이트 및 grade 자동 설정
        if form.target_type.data == 'grade':
            target_grades = form.target_grades.data or []
            target_audience = json.dumps({
                'type': 'grade',
                'grades': target_grades
            }, ensure_ascii=False)
            # 첫 번째 대상 학년을 grade로 설정 (없으면 '전체')
            auto_grade = target_grades[0] if target_grades else '전체'
        else:
            course_ids = form.target_course_ids.data.split(',') if form.target_course_ids.data else []
            course_ids = [cid.strip() for cid in course_ids if cid.strip()]
            target_audience = json.dumps({
                'type': 'course',
                'course_ids': course_ids
            }, ensure_ascii=False)
            # 수업별 대상인 경우 '수업별'로 설정
            auto_grade = '수업별'

        # 기본 정보 업데이트
        video.title = form.title.data
        video.grade = auto_grade
        video.youtube_url = form.youtube_url.data
        video.youtube_video_id = extract_youtube_video_id(form.youtube_url.data)
        video.publish_date = form.publish_date.data
        video.end_date = form.end_date.data
        video.is_public = form.is_public.data

        video.target_audience = target_audience

        db.session.commit()
        flash('동영상이 수정되었습니다.', 'success')
        return redirect(url_for('admin.video_detail', video_id=video.video_id))

    return render_template('admin/video_form.html',
                         form=form,
                         mode='edit',
                         video=video,
                         target_audience=target_audience)


@admin_bp.route('/videos/<video_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def delete_video(video_id):
    """동영상 삭제"""
    video = Video.query.get_or_404(video_id)

    db.session.delete(video)
    db.session.commit()

    flash('동영상이 삭제되었습니다.', 'info')
    return redirect(url_for('admin.videos'))


@admin_bp.route('/videos/<video_id>/toggle-active', methods=['POST'])
@login_required
@requires_permission_level(2)
def toggle_video_active(video_id):
    """동영상 공개/비공개 토글"""
    video = Video.query.get_or_404(video_id)

    # is_public 상태 토글
    video.is_public = not video.is_public
    db.session.commit()

    status_text = '공개' if video.is_public else '비공개'
    flash(f'동영상이 {status_text} 상태로 변경되었습니다.', 'success')

    return redirect(url_for('admin.video_detail', video_id=video_id))


# ============================================================================
# API - Course Search
# ============================================================================

@admin_bp.route('/api/courses/search')
@login_required
@requires_permission_level(2)
def api_search_courses():
    """수업 검색 API (교재/동영상 대상 선택용)"""
    query_text = request.args.get('q', '').strip()

    if not query_text:
        return jsonify([])

    courses = Course.query.filter(
        Course.status == 'active',
        db.or_(
            Course.course_name.ilike(f'%{query_text}%'),
            Course.course_code.ilike(f'%{query_text}%')
        )
    ).limit(20).all()

    results = []
    for course in courses:
        enrollment_count = CourseEnrollment.query.filter_by(
            course_id=course.course_id,
            status='active'
        ).count()

        results.append({
            'course_id': course.course_id,
            'course_name': course.course_name,
            'course_code': course.course_code,
            'grade': course.grade or '',
            'teacher_name': course.teacher.name if course.teacher else '',
            'enrollment_count': enrollment_count
        })

    return jsonify(results)


# ============================================================================
# 학부모-자녀 연결 요청 관리 (Parent-Child Link Requests)
# ============================================================================

@admin_bp.route('/parent-link-requests')
@login_required
@requires_permission_level(2)
def parent_link_requests():
    """학부모 자녀 연결 요청 목록"""
    status_filter = request.args.get('status', 'pending')

    query = ParentLinkRequest.query

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    requests = query.order_by(ParentLinkRequest.created_at.desc()).all()

    # 통계
    stats = {
        'pending': ParentLinkRequest.query.filter_by(status='pending').count(),
        'approved': ParentLinkRequest.query.filter_by(status='approved').count(),
        'rejected': ParentLinkRequest.query.filter_by(status='rejected').count(),
        'cancelled': ParentLinkRequest.query.filter_by(status='cancelled').count()
    }

    return render_template('admin/parent_link_requests.html',
                         requests=requests,
                         stats=stats,
                         status_filter=status_filter)


@admin_bp.route('/parent-link-requests/<request_id>')
@login_required
@requires_permission_level(2)
def parent_link_request_detail(request_id):
    """연결 요청 상세 - 학생 검색 및 매칭"""
    link_request = ParentLinkRequest.query.get_or_404(request_id)

    # 학생 검색 (이름 기반)
    search_results = []
    if link_request.student_name:
        search_results = Student.query.filter(
            Student.name.ilike(f'%{link_request.student_name}%')
        ).all()

    # 이미 해당 학부모와 연결된 학생들
    already_linked = db.session.query(Student.student_id).join(ParentStudent).filter(
        ParentStudent.parent_id == link_request.parent_id,
        ParentStudent.is_active == True
    ).all()
    already_linked_ids = [s[0] for s in already_linked]

    return render_template('admin/parent_link_request_detail.html',
                         link_request=link_request,
                         search_results=search_results,
                         already_linked_ids=already_linked_ids)


@admin_bp.route('/parent-link-requests/<request_id>/approve', methods=['POST'])
@login_required
@requires_permission_level(2)
def approve_parent_link_request(request_id):
    """연결 요청 승인"""
    link_request = ParentLinkRequest.query.get_or_404(request_id)
    student_id = request.form.get('student_id')

    if not student_id:
        flash('학생을 선택해주세요.', 'warning')
        return redirect(url_for('admin.parent_link_request_detail', request_id=request_id))

    student = Student.query.get_or_404(student_id)

    # 이미 연결되어 있는지 확인
    existing = ParentStudent.query.filter_by(
        parent_id=link_request.parent_id,
        student_id=student_id
    ).first()

    if existing and existing.is_active:
        flash('이미 연결된 학생입니다.', 'warning')
        return redirect(url_for('admin.parent_link_request_detail', request_id=request_id))

    # 기존 연결이 비활성화된 경우 재활성화
    if existing and not existing.is_active:
        existing.is_active = True
        existing.created_by = current_user.user_id
    else:
        # 새 연결 생성
        relation = ParentStudent(
            parent_id=link_request.parent_id,
            student_id=student_id,
            relation_type=link_request.relation_type,
            permission_level='full',
            created_by=current_user.user_id
        )
        db.session.add(relation)

    # 요청 상태 업데이트
    link_request.status = 'approved'
    link_request.matched_student_id = student_id
    link_request.reviewed_by = current_user.user_id
    link_request.reviewed_at = datetime.utcnow()
    link_request.admin_notes = request.form.get('admin_notes', '').strip() or None

    db.session.commit()

    # 학부모에게 알림
    notification = Notification(
        user_id=link_request.parent_id,
        notification_type='link_approved',
        title='자녀 연결 승인',
        message=f'{student.name} 학생과 연결되었습니다!',
        link_url=url_for('parent.index')
    )
    db.session.add(notification)
    db.session.commit()

    flash(f'{link_request.parent.name}님과 {student.name} 학생이 연결되었습니다.', 'success')
    return redirect(url_for('admin.parent_link_requests'))


@admin_bp.route('/parent-link-requests/<request_id>/reject', methods=['POST'])
@login_required
@requires_permission_level(2)
def reject_parent_link_request(request_id):
    """연결 요청 거절"""
    from app.models.parent_student import ParentStudent
    link_request = ParentLinkRequest.query.get_or_404(request_id)
    # 폼 필드명 admin_notes (템플릿과 일치)
    reject_reason = request.form.get('admin_notes', '').strip() or request.form.get('reject_reason', '').strip()

    if not reject_reason:
        flash('거절 사유를 입력해주세요.', 'warning')
        return redirect(url_for('admin.parent_link_request_detail', request_id=request_id))

    # 요청 상태 업데이트
    link_request.status = 'rejected'
    link_request.reviewed_by = current_user.user_id
    link_request.reviewed_at = datetime.utcnow()
    link_request.admin_notes = reject_reason

    # 이미 승인된 연결이 있으면 비활성화
    student_id = link_request.matched_student_id
    if student_id:
        existing = ParentStudent.query.filter_by(
            parent_id=link_request.parent_id,
            student_id=student_id,
            is_active=True
        ).first()
        if existing:
            existing.is_active = False

    db.session.commit()

    # 학부모에게 알림
    notification = Notification(
        user_id=link_request.parent_id,
        notification_type='link_rejected',
        title='자녀 연결 요청 거절',
        message=f'자녀 연결 요청이 거절되었습니다. 사유: {reject_reason}',
        link_url=url_for('parent.link_requests')
    )
    db.session.add(notification)
    db.session.commit()

    flash('연결 요청이 거절되었습니다.', 'info')
    return redirect(url_for('admin.parent_link_requests'))


@admin_bp.route('/api/students/search-v2')
@login_required
@requires_permission_level(2)
def api_search_students():
    """학생 검색 API (연결 요청용) - search_students로 통합됨"""
    query_text = request.args.get('q', '').strip()

    if not query_text:
        return jsonify({'students': []})

    # 이름으로만 검색 (student_code 필드 없음, 임시학생 제외)
    students = Student.query.filter(
        Student.is_temp == False,
        Student.name.ilike(f'%{query_text}%')
    ).limit(20).all()

    results = []
    for student in students:
        # 수강 중인 과목 수
        active_courses = CourseEnrollment.query.filter_by(
            student_id=student.student_id,
            status='active'
        ).count()

        # 연결된 학부모 수
        parent_count = ParentStudent.query.filter_by(
            student_id=student.student_id,
            is_active=True
        ).count()

        results.append({
            'student_id': student.student_id,
            'name': student.name,
            'student_code': student.student_id[:8],  # student_id의 앞 8자리를 코드로 사용
            'grade': student.grade or '',
            'school': '-',  # school 필드 없음
            'is_active': True,  # is_active 필드 없음, 항상 True로 가정
            'active_course_count': active_courses,
            'parent_count': parent_count
        })

    return jsonify({'students': results})

# ============================================================================
# 강사 승인 관리 (Teacher Approval Management)
# ============================================================================

@admin_bp.route('/pending-teachers')
@login_required
@requires_permission_level(2)
def pending_teachers():
    """승인 대기 중인 강사 목록"""
    # 필터
    status_filter = request.args.get('status', 'pending')
    
    # 쿼리 빌드
    query = User.query.filter(User.role == 'teacher')
    
    if status_filter == 'pending':
        query = query.filter(User.is_active == False)
    elif status_filter == 'approved':
        query = query.filter(User.is_active == True)
    
    teachers = query.order_by(User.created_at.desc()).all()
    
    # 통계
    pending_count = User.query.filter(
        User.role == 'teacher',
        User.is_active == False
    ).count()
    
    approved_count = User.query.filter(
        User.role == 'teacher',
        User.is_active == True
    ).count()
    
    return render_template('admin/pending_teachers.html',
                         teachers=teachers,
                         status_filter=status_filter,
                         pending_count=pending_count,
                         approved_count=approved_count)


@admin_bp.route('/pending-teachers/<user_id>/approve', methods=['POST'])
@login_required
@requires_permission_level(2)
def approve_teacher(user_id):
    """강사 계정 승인"""
    teacher = User.query.get_or_404(user_id)
    
    if teacher.role != 'teacher':
        flash('강사 계정이 아닙니다.', 'error')
        return redirect(url_for('admin.pending_teachers'))
    
    # 승인 처리
    teacher.is_active = True

    # 승인 알림
    notification = Notification(
        user_id=teacher.user_id,
        notification_type='teacher_approved',
        title='강사 계정 승인 완료',
        message=f'축하합니다! {teacher.name}님의 강사 계정이 승인되었습니다. 이제 로그인하여 시스템을 사용할 수 있습니다.',
        link_url=url_for('auth.login')
    )
    db.session.add(notification)
    db.session.commit()

    # SMS 발송
    if teacher.phone:
        from app.utils.sms import send_sms_message
        sms_msg = f'[MOMOAI] {teacher.name}님, 강사 계정이 승인되었습니다. 이제 로그인하여 시스템을 사용할 수 있습니다.'
        send_sms_message(teacher.phone, sms_msg)

    flash(f'{teacher.name}님의 강사 계정이 승인되었습니다.', 'success')
    return redirect(url_for('admin.pending_teachers'))


@admin_bp.route('/pending-teachers/<user_id>/reject', methods=['POST'])
@login_required
@requires_permission_level(2)
def reject_teacher(user_id):
    """강사 계정 거절 (삭제)"""
    teacher = User.query.get_or_404(user_id)
    
    if teacher.role != 'teacher':
        flash('강사 계정이 아닙니다.', 'error')
        return redirect(url_for('admin.pending_teachers'))
    
    reject_reason = request.form.get('reason', '').strip()
    
    # 거절 알림 (계정 삭제 전 전송)
    if reject_reason:
        notification = Notification(
            user_id=teacher.user_id,
            notification_type='teacher_rejected',
            title='강사 계정 신청 거절',
            message=f'죄송합니다. {teacher.name}님의 강사 계정 신청이 거절되었습니다. 사유: {reject_reason}',
            link_url=url_for('auth.signup')
        )
        db.session.add(notification)
        db.session.commit()
    
    # 계정 삭제
    teacher_name = teacher.name
    db.session.delete(teacher)
    db.session.commit()
    
    flash(f'{teacher_name}님의 강사 계정 신청이 거절되었습니다.', 'info')
    return redirect(url_for('admin.pending_teachers'))


# ============================================================================
# 통합 회원 승인 관리 (Unified User Approval)
# ============================================================================

@admin_bp.route('/pending-users')
@login_required
@requires_permission_level(2)
def pending_users():
    """승인 대기 중인 전체 회원 목록 (강사/학부모/학생, 거절된 사용자 제외)"""
    role_filter = request.args.get('role', '').strip()

    # 거절됐거나 이미 한 번 승인된(정지 포함) 사용자 ID 목록 제외
    exclude_ids = [
        n.user_id for n in Notification.query.filter(
            Notification.notification_type.in_(['account_rejected', 'account_approved'])
        ).with_entities(Notification.user_id).all()
    ]

    base_query = User.query.filter_by(is_active=False).filter(
        User.role.in_(['teacher', 'parent', 'student'])
    )
    if exclude_ids:
        base_query = base_query.filter(~User.user_id.in_(exclude_ids))

    query = base_query
    if role_filter and role_filter in ('teacher', 'parent', 'student'):
        query = query.filter_by(role=role_filter)

    pending = query.order_by(User.created_at.desc()).all()

    # 역할별 카운트 (거절/정지 제외)
    def _count_role(role=None):
        q = User.query.filter_by(is_active=False)
        if role:
            q = q.filter_by(role=role)
        else:
            q = q.filter(User.role.in_(['teacher', 'parent', 'student']))
        if exclude_ids:
            q = q.filter(~User.user_id.in_(exclude_ids))
        return q.count()

    counts = {
        'all': _count_role(),
        'teacher': _count_role('teacher'),
        'parent': _count_role('parent'),
        'student': _count_role('student'),
    }

    return render_template('admin/pending_users.html',
                           pending=pending,
                           role_filter=role_filter,
                           counts=counts)


@admin_bp.route('/pending-users/<user_id>/approve', methods=['POST'])
@login_required
@requires_permission_level(2)
def approve_user(user_id):
    """회원 계정 승인"""
    user = User.query.get_or_404(user_id)

    if user.is_active:
        flash(f'{user.name}은(는) 이미 활성화된 계정입니다.', 'warning')
        return redirect(url_for('admin.pending_users'))

    user.is_active = True
    db.session.flush()

    # 승인 알림 (사용자가 다음 로그인 시 확인 가능)
    from app.models.notification import Notification
    Notification.create_notification(
        user_id=user.user_id,
        notification_type='account_approved',
        title='계정이 승인되었습니다',
        message='관리자가 회원가입을 승인했습니다. 이제 서비스를 이용하실 수 있습니다.',
        link_url='/'
    )

    db.session.commit()

    # SMS 발송
    if user.phone:
        from app.utils.sms import send_sms_message
        role_label_sms = {'teacher': '강사', 'parent': '학부모', 'student': '학생'}.get(user.role, '회원')
        sms_msg = f'[MOMOAI] {user.name}님, {role_label_sms} 계정이 승인되었습니다. 이제 로그인하여 서비스를 이용하실 수 있습니다.'
        send_sms_message(user.phone, sms_msg)

    role_label = {'teacher': '강사', 'parent': '학부모', 'student': '학생'}.get(user.role, user.role)
    flash(f'{user.name} ({role_label}) 계정이 승인되었습니다.', 'success')
    return redirect(url_for('admin.pending_users'))


@admin_bp.route('/pending-users/<user_id>/reject', methods=['POST'])
@login_required
@requires_permission_level(2)
def reject_user(user_id):
    """회원 계정 거절 (비활성 상태 유지, 대기 목록에서 제외)"""
    user = User.query.get_or_404(user_id)

    # 중복 거절 방지
    already_rejected = Notification.query.filter_by(
        user_id=user.user_id,
        notification_type='account_rejected'
    ).first()

    if not already_rejected:
        # 사용자에게 거절 알림 전송 (승인 대기 페이지에서 상태 확인용)
        Notification.create_notification(
            user_id=user.user_id,
            notification_type='account_rejected',
            title='계정 신청이 거절되었습니다',
            message='관리자가 회원가입 신청을 거절했습니다. 자세한 사항은 학원에 문의해주세요.',
            link_url=url_for('auth.pending_approval')
        )
        db.session.commit()

    role_label = {'teacher': '강사', 'parent': '학부모', 'student': '학생'}.get(user.role, user.role)
    flash(f'{user.name} ({role_label}) 계정 승인이 거절되었습니다.', 'info')
    return redirect(url_for('admin.pending_users'))


# ============================================================================
# 직원 계정 생성 (Staff Account Creation)
# ============================================================================

@admin_bp.route('/create-staff', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def create_staff():
    """직원 계정 생성 (강사/관리자)"""
    from app.admin.forms import CreateStaffForm
    import secrets
    import string
    
    form = CreateStaffForm()
    
    if form.validate_on_submit():
        # 초기 비밀번호 생성 (8자리: 대문자+소문자+숫자+특수문자)
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        initial_password = ''.join(secrets.choice(alphabet) for i in range(8))
        
        # role_level 설정
        if form.role.data == 'admin':
            role_level = 2  # manager
        else:
            role_level = 3  # teacher
        
        # 계정 생성
        user = User(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data if form.phone.data else None,
            role=form.role.data,
            role_level=role_level,
            is_active=True,
            must_change_password=True  # 첫 로그인 시 비밀번호 변경 필수
        )
        user.set_password(initial_password)
        
        db.session.add(user)
        
        # 알림 전송
        notification = Notification(
            user_id=user.user_id,
            notification_type='account_created',
            title='계정이 생성되었습니다',
            message=f'{user.name}님의 계정이 생성되었습니다. 초기 비밀번호로 로그인 후 반드시 비밀번호를 변경해주세요.',
            link_url=url_for('auth.login')
        )
        db.session.add(notification)
        db.session.commit()
        
        # 성공 메시지와 함께 초기 비밀번호 표시
        flash(f'계정이 생성되었습니다!', 'success')
        return render_template('admin/staff_created.html',
                             user=user,
                             initial_password=initial_password)
    
    return render_template('admin/create_staff.html', form=form)


@admin_bp.route('/staff-list')
@login_required
@requires_permission_level(2)
def staff_list():
    """직원 목록 (강사/관리자)"""
    role_filter = request.args.get('role', 'all')
    
    sort = request.args.get('sort', 'newest')

    query = User.query.filter(User.role.in_(['teacher', 'admin']))

    if role_filter != 'all':
        query = query.filter(User.role == role_filter)

    if sort == 'name':
        staff_members = query.order_by(User.name).all()
    else:
        staff_members = query.order_by(User.created_at.desc()).all()

    # 통계
    teacher_count = User.query.filter(User.role == 'teacher').count()
    admin_count = User.query.filter(User.role == 'admin').count()

    # zoom_link 복호화 맵
    from app.utils.zoom_utils import decrypt_zoom_link
    zoom_links_decrypted = {}
    for s in staff_members:
        if s.zoom_link:
            try:
                zoom_links_decrypted[s.user_id] = decrypt_zoom_link(s.zoom_link)
            except Exception:
                zoom_links_decrypted[s.user_id] = ''

    return render_template('admin/staff_list.html',
                         staff_members=staff_members,
                         role_filter=role_filter,
                         sort=sort,
                         teacher_count=teacher_count,
                         admin_count=admin_count,
                         zoom_links_decrypted=zoom_links_decrypted)


@admin_bp.route('/parent-list')
@login_required
@requires_permission_level(2)
def parent_list():
    """학부모 계정 목록"""
    from app.models.parent_student import ParentStudent

    search = request.args.get('search', '').strip()
    query = User.query.filter(User.role == 'parent')

    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.phone.ilike(f'%{search}%')
            )
        )

    sort = request.args.get('sort', 'newest')
    if sort == 'name':
        parents = query.order_by(User.name).all()
    else:
        parents = query.order_by(User.created_at.desc()).all()

    # 각 학부모의 연결된 자녀 정보
    parent_data = []
    for parent in parents:
        relations = ParentStudent.query.filter_by(
            parent_id=parent.user_id, is_active=True
        ).all()
        parent_data.append({
            'user': parent,
            'children': [r.student for r in relations]
        })

    total = User.query.filter(User.role == 'parent').count()
    active = User.query.filter(User.role == 'parent', User.is_active == True).count()

    return render_template('admin/parent_list.html',
                           parent_data=parent_data,
                           total=total,
                           active=active,
                           search=search,
                           sort=sort)


@admin_bp.route('/parents/<string:parent_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def edit_parent(parent_id):
    """학부모 정보 수정"""
    parent = User.query.get_or_404(parent_id)
    if parent.role != 'parent':
        flash('학부모 계정이 아닙니다.', 'danger')
        return redirect(url_for('admin.parent_list'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        kakao_id = request.form.get('kakao_id', '').strip()
        is_active = 'is_active' in request.form

        if not name or not email:
            flash('이름과 이메일은 필수 항목입니다.', 'danger')
            return redirect(request.url)

        # 이메일 중복 체크 (자신 제외)
        existing = User.query.filter(
            User.email == email, User.user_id != parent_id
        ).first()
        if existing:
            flash('이미 사용 중인 이메일입니다.', 'danger')
            return redirect(request.url)

        parent.name = name
        parent.email = email
        parent.phone = phone if phone else None
        parent.kakao_id = kakao_id if kakao_id else None
        parent.is_active = is_active
        db.session.commit()

        flash(f'{parent.name}님의 정보가 수정되었습니다.', 'success')
        return redirect(url_for('admin.parent_list'))

    return render_template('admin/edit_parent.html', parent=parent)


@admin_bp.route('/parents/<string:parent_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(1)  # master_admin만
def delete_parent(parent_id):
    """학부모 계정 완전 삭제"""
    user = User.query.get_or_404(parent_id)
    if user.role != 'parent':
        flash('학부모 계정이 아닙니다.', 'danger')
        return redirect(url_for('admin.parent_list'))

    from datetime import datetime as dt
    name = user.name
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = dt.utcnow()
    db.session.commit()

    flash(f'{name} 계정이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.parent_list'))


@admin_bp.route('/staff/<string:user_id>/toggle-active', methods=['POST'])
@login_required
@requires_permission_level(2)
def toggle_staff_active(user_id):
    """강사/직원 계정 사용/미사용 토글"""
    user = User.query.get_or_404(user_id)

    if user.role not in ('teacher', 'admin'):
        return jsonify({'success': False, 'message': '강사/직원 계정만 변경할 수 있습니다.'}), 400

    # 자기 자신은 비활성화 불가
    if user.user_id == current_user.user_id:
        return jsonify({'success': False, 'message': '자신의 계정은 변경할 수 없습니다.'}), 400

    user.is_active = not user.is_active
    db.session.commit()

    role_label = '강사' if user.role == 'teacher' else '관리자'
    if user.is_active:
        message = f'{user.name} ({role_label}) 계정이 활성화(사용)되었습니다.'
        new_status = 'active'
    else:
        message = f'{user.name} ({role_label}) 계정이 비활성화(미사용)되었습니다.'
        new_status = 'suspended'

    return jsonify({'success': True, 'new_status': new_status, 'message': message})


@admin_bp.route('/users/<string:user_id>/reset-password', methods=['POST'])
@login_required
@requires_permission_level(2)
def reset_password(user_id):
    """비밀번호 초기화 (강사/학부모 공용)"""
    import secrets
    import string

    user = User.query.get_or_404(user_id)

    # 8자리 초기 비밀번호 생성
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    new_password = ''.join(secrets.choice(alphabet) for _ in range(8))

    user.set_password(new_password)
    user.must_change_password = True
    db.session.commit()

    return render_template('admin/password_reset_result.html',
                           user=user,
                           new_password=new_password)


@admin_bp.route('/staff/<string:staff_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)
def edit_staff(staff_id):
    """직원 정보 수정"""
    from app.admin.forms import EditStaffForm
    from app.utils.zoom_utils import encrypt_zoom_link, decrypt_zoom_link, generate_zoom_token

    staff = User.query.get_or_404(staff_id)

    form = EditStaffForm(original_email=staff.email)

    if form.validate_on_submit():
        staff.name = form.name.data
        staff.email = form.email.data
        staff.phone = form.phone.data if form.phone.data else None
        staff.is_active = form.is_active.data

        # role 변경 시 role_level도 업데이트
        new_role = form.role.data
        if new_role != staff.role:
            staff.role = new_role
            staff.role_level = 2 if new_role == 'admin' else 3

        # 줌 링크 처리
        zoom_link_input = form.zoom_link.data.strip() if form.zoom_link.data else ''
        if zoom_link_input:
            encrypted_link = encrypt_zoom_link(zoom_link_input)
            staff.zoom_link = encrypted_link
            if not staff.zoom_token:
                staff.zoom_token = generate_zoom_token(staff.name)
        elif not zoom_link_input and staff.zoom_link:
            # 입력이 비어 있고 기존 링크가 있으면 그대로 유지
            pass

        db.session.commit()
        flash(f'{staff.name}님의 정보가 수정되었습니다.', 'success')
        return redirect(url_for('admin.staff_list'))

    # GET: 현재 값으로 폼 채우기
    if request.method == 'GET':
        form.name.data = staff.name
        form.email.data = staff.email
        form.phone.data = staff.phone
        form.role.data = staff.role
        form.is_active.data = staff.is_active
        if staff.zoom_link:
            form.zoom_link.data = decrypt_zoom_link(staff.zoom_link)

    return render_template('admin/edit_staff.html', form=form, staff=staff)


@admin_bp.route('/staff/<string:staff_id>/zoom-link', methods=['POST'])
@login_required
@requires_permission_level(2)
def update_staff_zoom_link(staff_id):
    """강사 줌 링크 업데이트"""
    from app.utils.zoom_utils import encrypt_zoom_link

    staff = User.query.get_or_404(staff_id)

    # 강사인지 확인
    if staff.role != 'teacher':
        return jsonify({
            'success': False,
            'message': '강사만 줌 링크를 설정할 수 있습니다.'
        }), 400

    data = request.get_json()
    zoom_link = data.get('zoom_link', '').strip()

    if not zoom_link:
        return jsonify({
            'success': False,
            'message': '줌 링크를 입력하세요.'
        }), 400

    try:
        # 줌 링크 암호화
        encrypted_link = encrypt_zoom_link(zoom_link)
        staff.zoom_link = encrypted_link

        # 줌 토큰이 없으면 생성
        if not staff.zoom_token:
            from app.utils.zoom_utils import generate_zoom_token
            staff.zoom_token = generate_zoom_token(staff.name)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '줌 링크가 저장되었습니다.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'저장 중 오류가 발생했습니다: {str(e)}'
        }), 500



# ==================== 게시판 관리 ====================

@admin_bp.route('/boards/class')
@login_required
@requires_permission_level(2)
def board_class_manage():
    """클래스 게시판 관리"""
    from app.models.class_board import ClassBoardPost, ClassBoardComment

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = ClassBoardPost.query
    if search:
        query = query.filter(
            db.or_(
                ClassBoardPost.title.ilike(f'%{search}%'),
                ClassBoardPost.content.ilike(f'%{search}%')
            )
        )
    query = query.order_by(ClassBoardPost.created_at.desc())
    pagination = query.paginate(page=page, per_page=30, error_out=False)
    posts = pagination.items

    total_posts = ClassBoardPost.query.count()
    total_comments = ClassBoardComment.query.count()

    return render_template('admin/board_class_manage.html',
                           posts=posts,
                           pagination=pagination,
                           search=search,
                           total_posts=total_posts,
                           total_comments=total_comments)


@admin_bp.route('/boards/class/posts/<post_id>/edit', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_class_edit_post(post_id):
    """클래스 게시판 게시글 수정 (관리자)"""
    from app.models.class_board import ClassBoardPost

    post = ClassBoardPost.query.get_or_404(post_id)
    post.title = request.form.get('title', post.title).strip()
    post.content = request.form.get('content', post.content).strip()
    post.post_type = request.form.get('post_type', post.post_type)
    post.is_notice = request.form.get('is_notice') == '1'
    post.is_pinned = request.form.get('is_pinned') == '1'
    db.session.commit()

    flash(f'"{post.title}" 게시글이 수정되었습니다.', 'success')
    return redirect(url_for('admin.board_class_manage',
                            page=request.args.get('page', 1),
                            search=request.args.get('search', '')))


@admin_bp.route('/boards/class/posts/<post_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_class_delete_post(post_id):
    """클래스 게시판 게시글 삭제 (관리자)"""
    from app.models.class_board import ClassBoardPost

    post = ClassBoardPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.board_class_manage'))


@admin_bp.route('/boards/teacher')
@login_required
@requires_permission_level(2)
def board_teacher_manage():
    """강사 게시판 관리"""
    from app.models.teacher_board import TeacherBoard

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = TeacherBoard.query
    if search:
        query = query.filter(
            db.or_(
                TeacherBoard.title.ilike(f'%{search}%'),
                TeacherBoard.content.ilike(f'%{search}%')
            )
        )
    query = query.order_by(TeacherBoard.is_notice.desc(), TeacherBoard.created_at.desc())
    pagination = query.paginate(page=page, per_page=30, error_out=False)
    posts = pagination.items

    total_posts = TeacherBoard.query.count()

    return render_template('admin/board_teacher_manage.html',
                           posts=posts,
                           pagination=pagination,
                           search=search,
                           total_posts=total_posts)


@admin_bp.route('/boards/teacher/posts/<post_id>/edit', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_teacher_edit_post(post_id):
    """강사 게시판 게시글 수정 (관리자)"""
    from app.models.teacher_board import TeacherBoard

    post = TeacherBoard.query.get_or_404(post_id)
    post.title = request.form.get('title', post.title).strip()
    post.content = request.form.get('content', post.content).strip()
    post.is_notice = request.form.get('is_notice') == '1'
    db.session.commit()

    flash(f'"{post.title}" 게시글이 수정되었습니다.', 'success')
    return redirect(url_for('admin.board_teacher_manage',
                            page=request.args.get('page', 1),
                            search=request.args.get('search', '')))


@admin_bp.route('/boards/teacher/posts/<post_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_teacher_delete_post(post_id):
    """강사 게시판 게시글 삭제 (관리자)"""
    from app.models.teacher_board import TeacherBoard

    post = TeacherBoard.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.board_teacher_manage'))


@admin_bp.route('/boards/teacher/posts/<post_id>/toggle-notice', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_teacher_toggle_notice(post_id):
    """강사 게시판 공지 토글"""
    from app.models.teacher_board import TeacherBoard

    post = TeacherBoard.query.get_or_404(post_id)
    post.is_notice = not post.is_notice
    db.session.commit()

    status = '공지' if post.is_notice else '일반 글'
    flash(f'"{post.title}" 게시글이 {status}로 변경되었습니다.', 'success')
    return redirect(url_for('admin.board_teacher_manage'))


@admin_bp.route('/boards/harkness')
@login_required
@requires_permission_level(2)
def board_harkness_manage():
    """하크니스 게시판 관리"""
    from app.models.harkness_board import HarknessBoard, HarknessPost

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    # 게시판 목록
    boards = HarknessBoard.query.order_by(
        HarknessBoard.board_type.asc(),
        HarknessBoard.created_at.desc()
    ).all()

    # 게시글 목록 (검색 포함)
    query = HarknessPost.query
    if search:
        query = query.filter(
            db.or_(
                HarknessPost.title.ilike(f'%{search}%'),
                HarknessPost.content.ilike(f'%{search}%')
            )
        )
    query = query.order_by(HarknessPost.created_at.desc())
    pagination = query.paginate(page=page, per_page=30, error_out=False)
    posts = pagination.items

    total_boards = HarknessBoard.query.count()
    total_posts = HarknessPost.query.count()

    return render_template('admin/board_harkness_manage.html',
                           boards=boards,
                           posts=posts,
                           pagination=pagination,
                           search=search,
                           total_boards=total_boards,
                           total_posts=total_posts)


@admin_bp.route('/boards/harkness/boards/<board_id>/edit', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_harkness_edit_board(board_id):
    """하크니스 게시판 수정 (관리자)"""
    from app.models.harkness_board import HarknessBoard

    board = HarknessBoard.query.get_or_404(board_id)
    board.title = request.form.get('title', board.title).strip()
    board.description = request.form.get('description', board.description or '').strip() or None
    db.session.commit()

    flash(f'"{board.title}" 게시판이 수정되었습니다.', 'success')
    return redirect(url_for('admin.board_harkness_manage'))


@admin_bp.route('/boards/harkness/boards/<board_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_harkness_delete_board(board_id):
    """하크니스 게시판 삭제 (관리자) — 하위 레코드 수동 삭제 후 게시판 삭제"""
    from app.models.harkness_board import (
        HarknessBoard, HarknessPost, HarknessComment,
        HarknessPostLike, HarknessQuestionLike
    )

    board = HarknessBoard.query.get_or_404(board_id)
    board_title = board.title

    post_ids = [p.post_id for p in
                HarknessPost.query.filter_by(board_id=board_id)
                .with_entities(HarknessPost.post_id).all()]

    if post_ids:
        HarknessQuestionLike.query.filter(
            HarknessQuestionLike.post_id.in_(post_ids)
        ).delete(synchronize_session=False)
        HarknessPostLike.query.filter(
            HarknessPostLike.post_id.in_(post_ids)
        ).delete(synchronize_session=False)
        HarknessComment.query.filter(
            HarknessComment.post_id.in_(post_ids)
        ).delete(synchronize_session=False)
        HarknessPost.query.filter_by(board_id=board_id).delete(synchronize_session=False)

    db.session.delete(board)
    db.session.commit()

    flash(f'"{board_title}" 게시판이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.board_harkness_manage'))


@admin_bp.route('/boards/harkness/boards/<board_id>/toggle-active', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_harkness_toggle_active(board_id):
    """하크니스 게시판 활성화 토글"""
    from app.models.harkness_board import HarknessBoard

    board = HarknessBoard.query.get_or_404(board_id)
    board.is_active = not board.is_active
    db.session.commit()

    status = '활성화' if board.is_active else '비활성화'
    flash(f'"{board.title}" 게시판이 {status}되었습니다.', 'success')
    return redirect(url_for('admin.board_harkness_manage'))


@admin_bp.route('/boards/harkness/posts/<post_id>/edit', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_harkness_edit_post(post_id):
    """하크니스 게시글 수정 (관리자)"""
    from app.models.harkness_board import HarknessPost

    post = HarknessPost.query.get_or_404(post_id)
    post.title = request.form.get('title', post.title).strip()
    post.content = request.form.get('content', post.content or '').strip() or None
    post.is_notice = request.form.get('is_notice') == '1'
    db.session.commit()

    flash(f'"{post.title}" 게시글이 수정되었습니다.', 'success')
    return redirect(url_for('admin.board_harkness_manage',
                            page=request.args.get('page', 1),
                            search=request.args.get('search', '')))


@admin_bp.route('/boards/harkness/posts/<post_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)
def board_harkness_delete_post(post_id):
    """하크니스 게시글 삭제 (관리자)"""
    from app.models.harkness_board import HarknessPost

    post = HarknessPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.board_harkness_manage'))


# ==================== 데이터 내보내기 ====================

@admin_bp.route('/export/students')
@login_required
@requires_permission_level(2)
def export_students():
    """학생 목록 Excel 내보내기"""
    from app.utils.export_utils import export_students_to_excel

    students = Student.query.order_by(Student.name).all()

    return export_students_to_excel(students)


@admin_bp.route('/export/courses')
@login_required
@requires_permission_level(2)
def export_courses():
    """수업 목록 Excel 내보내기"""
    from app.utils.export_utils import export_courses_to_excel

    courses = Course.query.order_by(Course.created_at.desc()).all()

    return export_courses_to_excel(courses)


@admin_bp.route('/export/payments')
@login_required
@requires_permission_level(2)
def export_payments():
    """결제 내역 Excel 내보내기"""
    from app.utils.export_utils import export_payments_to_excel
    from datetime import datetime, timedelta

    # 기간 필터 (기본: 최근 3개월)
    months = int(request.args.get('months', 3))
    start_date = datetime.utcnow() - timedelta(days=months*30)

    payments = Payment.query.filter(
        Payment.created_at >= start_date
    ).order_by(Payment.created_at.desc()).all()

    return export_payments_to_excel(payments)


@admin_bp.route('/export/attendance')
@login_required
@requires_permission_level(2)
def export_attendance():
    """출석 내역 Excel 내보내기"""
    from app.utils.export_utils import export_attendance_to_excel
    from datetime import datetime, timedelta

    # 기간 필터 (기본: 최근 1개월)
    months = int(request.args.get('months', 1))
    start_date = datetime.utcnow() - timedelta(days=months*30)

    # 출석 데이터 조회
    attendances = db.session.query(Attendance, CourseSession, Course, Student)\
        .join(CourseSession, Attendance.session_id == CourseSession.session_id)\
        .join(Course, CourseSession.course_id == Course.course_id)\
        .join(CourseEnrollment, Attendance.enrollment_id == CourseEnrollment.enrollment_id)\
        .join(Student, CourseEnrollment.student_id == Student.student_id)\
        .filter(CourseSession.session_date >= start_date.date())\
        .order_by(CourseSession.session_date.desc()).all()

    # 데이터 변환
    attendance_data = []
    for attendance, session, course, student in attendances:
        attendance_data.append({
            'date': session.session_date.strftime('%Y-%m-%d'),
            'course_name': course.course_name,
            'student_name': student.name,
            'status': attendance.status,
            'late_minutes': attendance.late_minutes if attendance.late_minutes else '-',
            'notes': attendance.notes or '-',
            'checked_at': attendance.checked_at.strftime('%Y-%m-%d %H:%M') if attendance.checked_at else '-'
        })

    return export_attendance_to_excel(attendance_data)


@admin_bp.route('/export/monthly-report')
@login_required
@requires_permission_level(2)
def export_monthly_report():
    """월간 종합 리포트 Excel 내보내기"""
    from app.utils.export_utils import create_excel_workbook, create_excel_response, add_title_row, add_info_row, style_header_row, style_data_rows, auto_adjust_column_width
    from datetime import datetime, timedelta
    from app.models.essay import Essay

    # 이번 달 데이터
    now = datetime.utcnow()
    first_day_of_month = datetime(now.year, now.month, 1)
    if now.month == 12:
        first_day_of_next_month = datetime(now.year + 1, 1, 1)
    else:
        first_day_of_next_month = datetime(now.year, now.month + 1, 1)

    wb, ws = create_excel_workbook("월간 리포트")

    # 제목
    month_str = now.strftime('%Y년 %m월')
    add_title_row(ws, f"{month_str} 종합 리포트", 5)
    add_info_row(ws, f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", 2)

    # 1. 전체 통계
    ws.append([])
    ws.append(['구분', '전체', '이번 달', '증감', ''])

    total_students = Student.query.count()
    month_students = Student.query.filter(Student.created_at >= first_day_of_month).count()

    total_courses = Course.query.count()
    month_courses = Course.query.filter(
        Course.status == 'active',
        Course.created_at >= first_day_of_month
    ).count()

    total_essays = Essay.query.count()
    month_essays = Essay.query.filter(Essay.created_at >= first_day_of_month).count()

    month_payments = Payment.query.filter(
        Payment.created_at >= first_day_of_month,
        Payment.status == 'completed'
    ).all()
    month_revenue = sum(p.amount for p in month_payments)

    ws.append(['학생 수', total_students, month_students, f'+{month_students}', ''])
    ws.append(['진행 중인 수업', total_courses, month_courses, f'+{month_courses}', ''])
    ws.append(['첨삭 수', total_essays, month_essays, f'+{month_essays}', ''])
    ws.append(['이번 달 수익', '', f'{month_revenue:,}원', '', ''])

    # 2. 수업별 통계
    ws.append([])
    ws.append(['상위 5개 수업', '강사', '수강생', '세션', '출석률'])
    style_header_row(ws, row_num=ws.max_row, column_count=5)

    # 상위 수업 (Python에서 정렬)
    all_active_courses = Course.query.all()
    sorted_courses = sorted(all_active_courses, key=lambda c: c.enrolled_count, reverse=True)
    top_courses = sorted_courses[:5]

    for course in top_courses:
        # 출석률 계산
        total_attendance = db.session.query(func.count(Attendance.attendance_id))\
            .join(CourseEnrollment)\
            .filter(CourseEnrollment.course_id == course.course_id).scalar() or 0

        present_count = db.session.query(func.count(Attendance.attendance_id))\
            .join(CourseEnrollment)\
            .filter(
                CourseEnrollment.course_id == course.course_id,
                Attendance.status == 'present'
            ).scalar() or 0

        attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0

        ws.append([
            course.course_name,
            course.teacher.name if course.teacher else '-',
            f"{course.enrolled_count}/{course.max_students}",
            f"{course.completed_sessions}/{course.total_sessions}",
            f"{attendance_rate:.1f}%"
        ])

    # 3. 이번 달 신규 학생
    ws.append([])
    ws.append(['이번 달 신규 학생', '학년', '등급', '가입일', ''])
    style_header_row(ws, row_num=ws.max_row, column_count=5)

    new_students = Student.query.filter(
        Student.created_at >= first_day_of_month
    ).order_by(Student.created_at.desc()).all()

    for student in new_students[:10]:  # 최대 10명
        ws.append([
            student.name,
            student.grade or '-',
            student.tier or '-',
            student.created_at.strftime('%Y-%m-%d'),
            ''
        ])

    auto_adjust_column_width(ws)

    return create_excel_response(wb, f"월간리포트_{month_str}")


# ==================== PDF 내보내기 ====================

@admin_bp.route('/export/monthly-report-pdf')
@login_required
@requires_permission_level(2)
def export_monthly_report_pdf():
    """월간 종합 리포트 PDF 내보내기"""
    from app.utils.pdf_utils import generate_monthly_report_pdf
    from app.models.essay import Essay

    # 이번 달 데이터
    now = datetime.utcnow()
    first_day_of_month = datetime(now.year, now.month, 1)
    month_str = now.strftime('%Y년 %m월')

    # 통계 수집
    total_students = Student.query.count()
    month_students = Student.query.filter(Student.created_at >= first_day_of_month).count()

    total_courses = Course.query.count()
    month_courses = Course.query.filter(
        Course.status == 'active',
        Course.created_at >= first_day_of_month
    ).count()

    total_essays = Essay.query.count()
    month_essays = Essay.query.filter(Essay.created_at >= first_day_of_month).count()

    month_payments = Payment.query.filter(
        Payment.created_at >= first_day_of_month,
        Payment.status == 'completed'
    ).all()
    month_revenue = sum(p.amount for p in month_payments)

    # 상위 수업 (Python에서 정렬)
    all_active_courses = Course.query.all()

    # enrolled_count로 정렬 (내림차순)
    sorted_courses = sorted(all_active_courses, key=lambda c: c.enrolled_count, reverse=True)
    top_courses = sorted_courses[:5]

    top_courses_data = []
    for course in top_courses:
        total_attendance = db.session.query(func.count(Attendance.attendance_id))\
            .join(CourseEnrollment)\
            .filter(CourseEnrollment.course_id == course.course_id).scalar() or 0

        present_count = db.session.query(func.count(Attendance.attendance_id))\
            .join(CourseEnrollment)\
            .filter(
                CourseEnrollment.course_id == course.course_id,
                Attendance.status == 'present'
            ).scalar() or 0

        attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0

        top_courses_data.append({
            'name': course.course_name,
            'teacher': course.teacher.name if course.teacher else '-',
            'students': f"{course.enrolled_count}/{course.max_students}",
            'attendance_rate': f"{attendance_rate:.1f}%"
        })

    statistics = {
        'total_students': total_students,
        'month_students': month_students,
        'total_courses': total_courses,
        'month_courses': month_courses,
        'total_essays': total_essays,
        'month_essays': month_essays,
        'month_revenue': month_revenue,
        'top_courses': top_courses_data
    }

    return generate_monthly_report_pdf(month_str, statistics)


# ===========================
# 온라인 강의실 (Zoom) 관리
# ===========================

@admin_bp.route('/zoom-links')
@login_required
@requires_permission_level(2)  # 관리자만
def zoom_links():
    """줌 링크 관리 페이지"""
    # 모든 강사 목록 조회
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()

    # 각 강사의 줌 링크 정보와 최근 접속 통계
    from app.models.zoom_access import ZoomAccessLog
    from sqlalchemy import func

    teachers_data = []
    for teacher in teachers:
        # 최근 30일 접속 횟수
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        access_count = db.session.query(func.count(ZoomAccessLog.log_id))\
            .filter(
                ZoomAccessLog.teacher_id == teacher.user_id,
                ZoomAccessLog.accessed_at >= thirty_days_ago
            ).scalar() or 0

        # 최근 접속 시간
        last_access = db.session.query(ZoomAccessLog)\
            .filter(ZoomAccessLog.teacher_id == teacher.user_id)\
            .order_by(ZoomAccessLog.accessed_at.desc())\
            .first()

        teachers_data.append({
            'teacher': teacher,
            'has_zoom_link': bool(teacher.zoom_link),
            'zoom_token': teacher.zoom_token or '미생성',
            'access_count': access_count,
            'last_access': last_access.accessed_at if last_access else None
        })

    return render_template('admin/zoom_links.html',
                         teachers_data=teachers_data)


@admin_bp.route('/zoom-links/<string:teacher_id>', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)  # 관리자만
def edit_zoom_link(teacher_id):
    """강사 줌 링크 수정"""
    from app.admin.forms import ZoomLinkForm
    from app.utils.zoom_utils import encrypt_zoom_link, decrypt_zoom_link, generate_zoom_token

    teacher = User.query.get_or_404(teacher_id)

    if teacher.role != 'teacher':
        flash('강사 계정만 줌 링크를 설정할 수 있습니다.', 'danger')
        return redirect(url_for('admin.zoom_links'))

    form = ZoomLinkForm()

    if form.validate_on_submit():
        # 줌 링크 암호화
        encrypted_link = encrypt_zoom_link(form.zoom_link.data)
        teacher.zoom_link = encrypted_link

        # 토큰이 없으면 생성
        if not teacher.zoom_token:
            teacher.zoom_token = generate_zoom_token(teacher.name)

        db.session.commit()
        flash(f'{teacher.name} 선생님의 줌 링크가 저장되었습니다.', 'success')
        return redirect(url_for('admin.zoom_links'))

    # GET 요청 시 기존 링크 복호화하여 표시
    if teacher.zoom_link:
        form.zoom_link.data = decrypt_zoom_link(teacher.zoom_link)

    return render_template('admin/edit_zoom_link.html',
                         teacher=teacher,
                         form=form)


@admin_bp.route('/zoom-links/<string:teacher_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)  # 관리자만
def delete_zoom_link(teacher_id):
    """강사 줌 링크 삭제"""
    teacher = User.query.get_or_404(teacher_id)

    teacher.zoom_link = None
    db.session.commit()

    flash(f'{teacher.name} 선생님의 줌 링크가 삭제되었습니다.', 'info')
    return redirect(url_for('admin.zoom_links'))


@admin_bp.route('/zoom-links/<string:teacher_id>/regenerate-token', methods=['POST'])
@login_required
@requires_permission_level(2)  # 관리자만
def regenerate_zoom_token(teacher_id):
    """강사 줌 토큰 재생성"""
    from app.utils.zoom_utils import generate_zoom_token

    teacher = User.query.get_or_404(teacher_id)

    # 새 토큰 생성
    teacher.zoom_token = generate_zoom_token(teacher.name)
    db.session.commit()

    flash(f'{teacher.name} 선생님의 줌 토큰이 재생성되었습니다.', 'success')
    return redirect(url_for('admin.zoom_links'))


@admin_bp.route('/zoom-access-logs')
@login_required
@requires_permission_level(2)  # 관리자만
def zoom_access_logs():
    """줌 접속 로그 조회"""
    from app.models.zoom_access import ZoomAccessLog

    # 페이지네이션
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # 필터링
    teacher_id = request.args.get('teacher_id')
    student_id = request.args.get('student_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = ZoomAccessLog.query

    if teacher_id:
        query = query.filter(ZoomAccessLog.teacher_id == teacher_id)

    if student_id:
        query = query.filter(ZoomAccessLog.student_id == student_id)

    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(ZoomAccessLog.accessed_at >= date_from_dt)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(ZoomAccessLog.accessed_at <= date_to_dt)
        except ValueError:
            pass

    logs = query.order_by(ZoomAccessLog.accessed_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 통계
    total_accesses = query.count()
    unique_students = db.session.query(func.count(func.distinct(ZoomAccessLog.student_id)))\
        .filter(ZoomAccessLog.log_id.in_([log.log_id for log in query.all()]))\
        .scalar() or 0

    # 강사 목록 (필터용)
    teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()

    return render_template('admin/zoom_access_logs.html',
                         logs=logs,
                         teachers=teachers,
                         total_accesses=total_accesses,
                         unique_students=unique_students,
                         filters={
                             'teacher_id': teacher_id,
                             'student_id': student_id,
                             'date_from': date_from,
                             'date_to': date_to
                         })


# ==================== 상담 기록 관리 ====================

@admin_bp.route('/consultations')
@login_required
@requires_permission_level(2)  # 매니저 이상
def consultations():
    """상담 기록 전체 목록 (검색 기능 포함)"""
    from app.models.consultation import ConsultationRecord

    # 필터
    counselor_id = request.args.get('counselor_id', '').strip()
    student_id = request.args.get('student_id', '').strip()
    major_category = request.args.get('major_category', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = ConsultationRecord.query

    # 필터 적용
    if counselor_id:
        query = query.filter_by(counselor_id=counselor_id)

    if student_id:
        query = query.filter_by(student_id=student_id)

    if major_category:
        query = query.filter_by(major_category=major_category)

    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(ConsultationRecord.consultation_date >= from_date)
        except:
            pass

    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(ConsultationRecord.consultation_date <= to_date)
        except:
            pass

    consultations = query.order_by(ConsultationRecord.consultation_date.desc()).all()

    # 강사 목록 (필터용)
    teachers = User.query.filter(User.role.in_(['teacher', 'admin', 'master_admin']))\
        .order_by(User.name).all()

    # 학생 목록 (필터용)
    students = Student.query.order_by(Student.name).all()

    return render_template('admin/consultations.html',
                         consultations=consultations,
                         teachers=teachers,
                         students=students,
                         filters={
                             'counselor_id': counselor_id,
                             'student_id': student_id,
                             'major_category': major_category,
                             'date_from': date_from,
                             'date_to': date_to
                         })


@admin_bp.route('/consultations/<int:consultation_id>')
@login_required
@requires_permission_level(2)  # 매니저 이상
def consultation_detail(consultation_id):
    """상담 기록 상세"""
    from app.models.consultation import ConsultationRecord

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    # 참고인 정보 가져오기
    reference_teachers = []
    if consultation.reference_teacher_ids:
        reference_teachers = User.query.filter(
            User.user_id.in_(consultation.reference_teacher_ids)
        ).all()

    # 모든 강사 목록 (참고인 설정용)
    all_teachers = User.query.filter(
        User.role.in_(['teacher', 'admin', 'master_admin']),
        User.user_id != consultation.counselor_id  # 작성자 제외
    ).order_by(User.name).all()

    return render_template('admin/consultation_detail.html',
                         consultation=consultation,
                         reference_teachers=reference_teachers,
                         all_teachers=all_teachers)


@admin_bp.route('/consultations/<int:consultation_id>/share', methods=['POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def share_consultation(consultation_id):
    """상담 기록 공유 (참고인 설정)"""
    from app.models.consultation import ConsultationRecord
    from app.models.notification import Notification

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    teacher_ids = request.form.getlist('teacher_ids')

    if not teacher_ids:
        flash('공유할 강사를 선택하세요.', 'warning')
        return redirect(url_for('admin.consultation_detail', consultation_id=consultation_id))

    # 참고인 업데이트
    import json
    consultation.reference_teachers = json.dumps(teacher_ids)
    db.session.commit()

    # 선택된 강사들에게 알림 전송
    for teacher_id in teacher_ids:
        notification = Notification(
            user_id=teacher_id,
            type='consultation_shared',
            title='상담 기록 공유',
            message=f'"{consultation.title}" 상담 기록이 공유되었습니다. (학생: {consultation.student.name})',
            link=url_for('teacher.consultation_detail', consultation_id=consultation.consultation_id)
        )
        db.session.add(notification)

    db.session.commit()

    flash(f'{len(teacher_ids)}명의 강사에게 상담 기록을 공유했습니다.', 'success')
    return redirect(url_for('admin.consultation_detail', consultation_id=consultation_id))


@admin_bp.route('/consultations/<int:consultation_id>/delete', methods=['POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def delete_consultation(consultation_id):
    """상담 기록 삭제"""
    from app.models.consultation import ConsultationRecord

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    db.session.delete(consultation)
    db.session.commit()

    flash('상담 기록이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.consultations'))


# ==================== 학생 프로필 관리 ====================

@admin_bp.route('/students/<student_id>/profile')
@login_required
@requires_permission_level(2)  # 매니저 이상
def student_profile(student_id):
    """학생 종합 프로필 페이지 - 탭 기반 통합"""
    from app.models.student_profile import StudentProfile
    from app.models.consultation import ConsultationRecord
    from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType
    from app.models.course import CourseEnrollment, Course
    from app.models.parent_student import ParentStudent
    from app.models.teacher_feedback import TeacherFeedback

    student = Student.query.get_or_404(student_id)
    profile = StudentProfile.query.filter_by(student_id=student_id).first()

    # 수강 내역 (모든 수업, 최신 입반순)
    enrollments = CourseEnrollment.query.filter_by(student_id=student_id)\
        .order_by(CourseEnrollment.enrolled_at.desc()).all()

    # 학부모 정보
    parent_relations = ParentStudent.query.filter_by(student_id=student_id, is_active=True).all()
    parents = [pr.parent for pr in parent_relations]

    # 피드백 이력
    feedbacks = TeacherFeedback.query.filter_by(student_id=student_id)\
        .order_by(TeacherFeedback.created_at.desc())\
        .limit(10)\
        .all()

    # MBTI 최신 결과 조회
    mbti_result = ReadingMBTIResult.query.filter_by(student_id=student_id)\
        .order_by(ReadingMBTIResult.created_at.desc())\
        .first()

    # MBTI 유형 정보 조회
    mbti_type = None
    if mbti_result:
        mbti_type = ReadingMBTIType.query.get(mbti_result.type_id)

    # 상담 이력 조회 (최신순, 최대 10개만)
    consultations = ConsultationRecord.query.filter_by(student_id=student_id)\
        .order_by(ConsultationRecord.consultation_date.desc())\
        .limit(10)\
        .all()

    # AI 인사이트 생성
    from app.utils.student_insights import generate_student_insights
    insights = generate_student_insights(
        student, enrollments, profile, mbti_result, mbti_type, consultations, feedbacks
    )

    return render_template('admin/student_profile.html',
                         student=student,
                         profile=profile,
                         enrollments=enrollments,
                         parents=parents,
                         feedbacks=feedbacks,
                         mbti_result=mbti_result,
                         mbti_type=mbti_type,
                         consultations=consultations,
                         insights=insights)


@admin_bp.route('/student-profiles')
@login_required
@requires_permission_level(2)  # 매니저 이상
def student_profiles():
    """학생 프로필 목록"""
    from app.models.student_profile import StudentProfile

    # 검색 필터
    search = request.args.get('search', '').strip()
    grade_filter = request.args.get('grade', '').strip()
    course_type_filter = request.args.get('course_type', '').strip()

    # 학생 조회 (프로필 포함)
    query = Student.query

    # 이름/ID 검색
    if search:
        query = query.filter(
            (Student.name.like(f'%{search}%')) |
            (Student.student_id.like(f'%{search}%'))
        )

    # 학년 필터
    if grade_filter:
        query = query.filter(Student.grade == grade_filter)

    # 수업 형태 필터 (수강 중인 수업 기준)
    if course_type_filter:
        query = query.join(CourseEnrollment, Student.student_id == CourseEnrollment.student_id)\
                     .join(Course, CourseEnrollment.course_id == Course.course_id)\
                     .filter(
                         CourseEnrollment.status == 'active',
                         Course.course_type == course_type_filter
                     ).distinct()

    students = query.order_by(Student.name).all()

    # 계정 연결된 학생 user_id → User 매핑
    linked_user_ids = [s.user_id for s in students if s.user_id]
    user_map = {}
    if linked_user_ids:
        users = User.query.filter(User.user_id.in_(linked_user_ids)).all()
        user_map = {u.user_id: u for u in users}

    # 학년 목록 (드롭다운용)
    grades = ['초1', '초2', '초3', '초4', '초5', '초6',
              '중1', '중2', '중3',
              '고1', '고2', '고3']

    # 수업 형태 목록
    course_types = ['베이직', '프리미엄', '정규반', '하크니스']

    return render_template('admin/student_profiles.html',
                         students=students,
                         user_map=user_map,
                         search=search,
                         grade_filter=grade_filter,
                         course_type_filter=course_type_filter,
                         grades=grades,
                         course_types=course_types)


@admin_bp.route('/students/<student_id>/toggle-active', methods=['POST'])
@login_required
@requires_permission_level(2)
def toggle_student_active(student_id):
    """학생 계정 사용/미사용 토글"""
    student = Student.query.get_or_404(student_id)

    if not student.user_id:
        return jsonify({'success': False, 'message': '연결된 계정이 없습니다.'}), 400

    user = User.query.get(student.user_id)
    if not user:
        return jsonify({'success': False, 'message': '사용자 계정을 찾을 수 없습니다.'}), 404

    user.is_active = not user.is_active

    if user.is_active:
        # 복원: account_restored 알림
        Notification.create_notification(
            user_id=user.user_id,
            notification_type='account_restored',
            title='계정이 복원되었습니다',
            message='관리자가 계정을 다시 활성화했습니다. 서비스를 정상 이용하실 수 있습니다.',
            link_url='/'
        )
        new_status = 'active'
        message = f'{student.name} 학생 계정이 활성화(사용)되었습니다.'
    else:
        # 정지: account_suspended 알림
        Notification.create_notification(
            user_id=user.user_id,
            notification_type='account_suspended',
            title='계정 이용이 제한되었습니다',
            message='관리자가 계정을 일시 정지했습니다. 자세한 사항은 학원에 문의해주세요.',
            link_url='/auth/pending-approval'
        )
        new_status = 'suspended'
        message = f'{student.name} 학생 계정이 비활성화(미사용)되었습니다.'

    db.session.commit()
    return jsonify({'success': True, 'new_status': new_status, 'message': message})


@admin_bp.route('/students/<string:student_id>/change-status', methods=['POST'])
@login_required
@requires_permission_level(2)
def change_student_status(student_id):
    """학생 등록 상태 변경 (active/leave/withdrawn)"""
    student = Student.query.get_or_404(student_id)
    new_status = request.json.get('status') if request.is_json else request.form.get('status')

    if new_status not in ('active', 'leave', 'withdrawn'):
        return jsonify({'success': False, 'message': '유효하지 않은 상태값입니다.'}), 400

    student.status = new_status
    student.status_changed_at = datetime.utcnow()
    db.session.commit()

    status_labels = {'active': '등록', 'leave': '휴원', 'withdrawn': '퇴원'}
    return jsonify({'success': True, 'new_status': new_status,
                    'message': f'{student.name} 학생 상태가 {status_labels[new_status]}으로 변경되었습니다.'})


@admin_bp.route('/student-risk-analysis')
@login_required
@requires_permission_level(2)  # 매니저 이상
def student_risk_analysis():
    """전체 학생 위험도 분석 대시보드"""
    from app.utils.student_insights import get_all_students_risk_analysis

    # 전체 학생 위험도 분석
    risk_analysis = get_all_students_risk_analysis()

    # 통계 계산
    stats = {
        'total': len(risk_analysis['high_risk']) + len(risk_analysis['medium_risk']) + len(risk_analysis['low_risk']),
        'high_risk': len(risk_analysis['high_risk']),
        'medium_risk': len(risk_analysis['medium_risk']),
        'low_risk': len(risk_analysis['low_risk'])
    }

    return render_template('admin/student_risk_analysis.html',
                         risk_analysis=risk_analysis,
                         stats=stats)


@admin_bp.route('/student-profiles/create/<student_id>', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def create_student_profile(student_id):
    """학생 프로필 생성"""
    from app.models.student_profile import StudentProfile
    from app.admin.forms import StudentProfileForm
    import json

    student = Student.query.get_or_404(student_id)

    # 이미 프로필이 있는지 확인
    existing_profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if existing_profile:
        flash('이미 프로필이 존재합니다.', 'warning')
        return redirect(url_for('admin.edit_student_profile', student_id=student_id))

    form = StudentProfileForm()

    # student_id 필드에 현재 학생만 설정
    form.student_id.choices = [(student.student_id, student.name)]
    form.student_id.data = student.student_id

    if form.validate_on_submit():
        profile = StudentProfile(
            student_id=student_id,
            survey_date=form.survey_date.data,
            address=form.address.data,
            parent_contact=form.parent_contact.data,
            current_school=form.current_school.data,
            reading_experience=form.reading_experience.data,
            reading_competency=int(form.reading_competency.data) if form.reading_competency.data else None,
            weekly_reading_amount=form.weekly_reading_amount.data,
            preferred_genres=json.dumps(form.preferred_genres.data, ensure_ascii=False) if form.preferred_genres.data else None,
            personality_traits=json.dumps(form.personality_traits.data, ensure_ascii=False) if form.personality_traits.data else None,
            main_improvement_goal=form.main_improvement_goal.data,
            preferred_class_style=form.preferred_class_style.data,
            teacher_request=form.teacher_request.data,
            referral_source=form.referral_source.data,
            education_info_needs=json.dumps(form.education_info_needs.data, ensure_ascii=False) if form.education_info_needs.data else None,
            academic_goals=json.dumps(form.academic_goals.data, ensure_ascii=False) if form.academic_goals.data else None,
            career_interests=json.dumps(form.career_interests.data, ensure_ascii=False) if form.career_interests.data else None,
            other_interests=form.other_interests.data,
            sibling_info=form.sibling_info.data,
            created_by=current_user.user_id
        )

        db.session.add(profile)
        db.session.commit()

        flash('학생 프로필이 생성되었습니다.', 'success')
        return redirect(url_for('admin.student_profile', student_id=student_id))

    return render_template('admin/student_profile_form.html',
                         form=form,
                         student=student,
                         is_edit=False)


@admin_bp.route('/student-profiles/edit/<student_id>', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def edit_student_profile(student_id):
    """학생 프로필 수정"""
    from app.models.student_profile import StudentProfile
    from app.admin.forms import StudentProfileForm
    import json

    student = Student.query.get_or_404(student_id)
    profile = StudentProfile.query.filter_by(student_id=student_id).first_or_404()

    form = StudentProfileForm(obj=profile)

    # student_id 필드에 현재 학생만 설정
    form.student_id.choices = [(student.student_id, student.name)]
    form.student_id.data = student.student_id

    if request.method == 'GET':
        # 폼에 기존 데이터 채우기
        form.survey_date.data = profile.survey_date
        form.address.data = profile.address
        form.parent_contact.data = profile.parent_contact
        form.current_school.data = profile.current_school
        form.reading_experience.data = profile.reading_experience
        form.reading_competency.data = str(profile.reading_competency) if profile.reading_competency else ''
        form.weekly_reading_amount.data = profile.weekly_reading_amount
        form.preferred_genres.data = profile.preferred_genres_list
        form.personality_traits.data = profile.personality_traits_list
        form.main_improvement_goal.data = profile.main_improvement_goal
        form.preferred_class_style.data = profile.preferred_class_style
        form.teacher_request.data = profile.teacher_request
        form.referral_source.data = profile.referral_source
        form.education_info_needs.data = profile.education_info_needs_list
        form.academic_goals.data = profile.academic_goals_list
        form.career_interests.data = profile.career_interests_list
        form.other_interests.data = profile.other_interests
        form.sibling_info.data = profile.sibling_info

    if form.validate_on_submit():
        profile.survey_date = form.survey_date.data
        profile.address = form.address.data
        profile.parent_contact = form.parent_contact.data
        profile.current_school = form.current_school.data
        profile.reading_experience = form.reading_experience.data
        profile.reading_competency = int(form.reading_competency.data) if form.reading_competency.data else None
        profile.weekly_reading_amount = form.weekly_reading_amount.data
        profile.preferred_genres = json.dumps(form.preferred_genres.data, ensure_ascii=False) if form.preferred_genres.data else None
        profile.personality_traits = json.dumps(form.personality_traits.data, ensure_ascii=False) if form.personality_traits.data else None
        profile.main_improvement_goal = form.main_improvement_goal.data
        profile.preferred_class_style = form.preferred_class_style.data
        profile.teacher_request = form.teacher_request.data
        profile.referral_source = form.referral_source.data
        profile.education_info_needs = json.dumps(form.education_info_needs.data, ensure_ascii=False) if form.education_info_needs.data else None
        profile.academic_goals = json.dumps(form.academic_goals.data, ensure_ascii=False) if form.academic_goals.data else None
        profile.career_interests = json.dumps(form.career_interests.data, ensure_ascii=False) if form.career_interests.data else None
        profile.other_interests = form.other_interests.data
        profile.sibling_info = form.sibling_info.data

        db.session.commit()

        flash('학생 프로필이 수정되었습니다.', 'success')
        return redirect(url_for('admin.student_profile', student_id=student_id))

    return render_template('admin/student_profile_form.html',
                         form=form,
                         student=student,
                         profile=profile,
                         is_edit=True)


@admin_bp.route('/student-profiles/import', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def import_student_profiles():
    """Excel 파일에서 학생 프로필 일괄 임포트"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('파일을 선택하세요.', 'danger')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('파일을 선택하세요.', 'danger')
            return redirect(request.url)

        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Excel 파일만 업로드 가능합니다.', 'danger')
            return redirect(request.url)

        try:
            import pandas as pd
            from app.models.student_profile import StudentProfile
            import json

            # Excel 파일 읽기
            df = pd.read_excel(file)

            success_count = 0
            error_count = 0
            errors = []

            for idx, row in df.iterrows():
                try:
                    # 학생 이름으로 학생 찾기
                    student_name = row.get('1. 학생의 이름', '').strip()
                    if not student_name:
                        continue

                    student = Student.query.filter_by(name=student_name).first()
                    if not student:
                        errors.append(f'행 {idx+2}: 학생 "{student_name}"을 찾을 수 없습니다.')
                        error_count += 1
                        continue

                    # 이미 프로필이 있는지 확인
                    existing_profile = StudentProfile.query.filter_by(student_id=student.student_id).first()
                    if existing_profile:
                        errors.append(f'행 {idx+2}: 학생 "{student_name}"의 프로필이 이미 존재합니다.')
                        error_count += 1
                        continue

                    # 프로필 데이터 파싱 및 생성
                    profile = StudentProfile(
                        student_id=student.student_id,
                        survey_date=row.get('타임스탬프') if pd.notna(row.get('타임스탬프')) else None,
                        address=row.get('4. 주소(신규 학생들에게는 원고지 1권과 가이드가 발송됩니다, 발송 시 우편물을 받으실 수 있도록 동,호수까지 적어주시면 감사하겠습니다. 해외학생들은 배송이 어려운 점 양해 부탁드립니다).') if pd.notna(row.get('4. 주소(신규 학생들에게는 원고지 1권과 가이드가 발송됩니다, 발송 시 우편물을 받으실 수 있도록 동,호수까지 적어주시면 감사하겠습니다. 해외학생들은 배송이 어려운 점 양해 부탁드립니다).')) else None,
                        parent_contact=str(row.get('5. 학부모 연락처')) if pd.notna(row.get('5. 학부모 연락처')) else None,
                        current_school=row.get('6. 재학 중인 학교 이름') if pd.notna(row.get('6. 재학 중인 학교 이름')) else None,
                        reading_experience=row.get('8. 독서논술 수업 경험 및 기간') if pd.notna(row.get('8. 독서논술 수업 경험 및 기간')) else None,
                        reading_competency=int(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')) if pd.notna(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')) and str(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')).isdigit() else None,
                        weekly_reading_amount=row.get('10. 학생의 한 주 평균 독서량을 체크해주세요.') if pd.notna(row.get('10. 학생의 한 주 평균 독서량을 체크해주세요.')) else None,
                        preferred_genres=json.dumps([g.strip() for g in str(row.get('11. 학생이 선호하는 독서 분야를 모두 선택해주세요.')).split(',')] if pd.notna(row.get('11. 학생이 선호하는 독서 분야를 모두 선택해주세요.')) else [], ensure_ascii=False),
                        personality_traits=json.dumps([p.strip() for p in str(row.get('12. 학생의 성향을 모두 알려주세요. ')).split(',')] if pd.notna(row.get('12. 학생의 성향을 모두 알려주세요. ')) else [], ensure_ascii=False),
                        main_improvement_goal=row.get('13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)') if pd.notna(row.get('13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)')) else None,
                        preferred_class_style=row.get('17.  가장 선호하는 수업 목표를 선택해주세요. (1개만 선택 가능)') if pd.notna(row.get('17.  가장 선호하는 수업 목표를 선택해주세요. (1개만 선택 가능)')) else None,
                        teacher_request=row.get('18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요. ') if pd.notna(row.get('18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요. ')) else None,
                        referral_source=row.get('19. 모모의 책장을 어떻게 알게 되셨나요?') if pd.notna(row.get('19. 모모의 책장을 어떻게 알게 되셨나요?')) else None,
                        education_info_needs=json.dumps([e.strip() for e in str(row.get('1. 필요한 교육&입시 정보가 있으신가요?')).split(',')] if pd.notna(row.get('1. 필요한 교육&입시 정보가 있으신가요?')) else [], ensure_ascii=False),
                        academic_goals=json.dumps([a.strip() for a in str(row.get('2. 진학 목표가 있으신가요?')).split(',')] if pd.notna(row.get('2. 진학 목표가 있으신가요?')) else [], ensure_ascii=False),
                        career_interests=json.dumps([c.strip() for c in str(row.get('3. 관심 있는 학생의 진로 분야는 무엇입니까?')).split(',')] if pd.notna(row.get('3. 관심 있는 학생의 진로 분야는 무엇입니까?')) else [], ensure_ascii=False),
                        other_interests=row.get('4. 기타 교육분야 관심사항이 있으시면 모두 적어주세요.') if pd.notna(row.get('4. 기타 교육분야 관심사항이 있으시면 모두 적어주세요.')) else None,
                        sibling_info=row.get('형제/자매 정보를 입력해주세요.') if pd.notna(row.get('형제/자매 정보를 입력해주세요.')) else None,
                        created_by=current_user.user_id
                    )

                    db.session.add(profile)
                    success_count += 1

                except Exception as e:
                    errors.append(f'행 {idx+2}: {str(e)}')
                    error_count += 1

            db.session.commit()

            flash(f'성공: {success_count}건, 실패: {error_count}건', 'success' if error_count == 0 else 'warning')

            if errors:
                # 에러 로그를 세션에 저장
                session['import_errors'] = errors[:50]  # 최대 50개만

            return redirect(url_for('admin.student_profiles'))

        except Exception as e:
            flash(f'파일 처리 중 오류 발생: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('admin/import_student_profiles.html')


@admin_bp.route('/student-profiles/delete/<student_id>', methods=['POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def delete_student_profile(student_id):
    """학생 프로필 삭제"""
    from app.models.student_profile import StudentProfile

    profile = StudentProfile.query.filter_by(student_id=student_id).first_or_404()

    db.session.delete(profile)
    db.session.commit()

    flash('학생 프로필이 삭제되었습니다.', 'success')
    return redirect(url_for('admin.student_profiles'))


@admin_bp.route('/student-profiles/import-with-students', methods=['GET', 'POST'])
@login_required
@requires_permission_level(2)  # 매니저 이상
def import_students_and_profiles():
    """Excel 파일에서 학생 + 프로필 동시 생성"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('파일을 선택하세요.', 'danger')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('파일을 선택하세요.', 'danger')
            return redirect(request.url)

        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Excel 파일만 업로드 가능합니다.', 'danger')
            return redirect(request.url)

        try:
            import pandas as pd
            from app.models.student_profile import StudentProfile
            import json
            from datetime import datetime
            import uuid

            # Excel 파일 읽기
            df = pd.read_excel(file)

            success_count = 0
            error_count = 0
            errors = []
            students_created = 0
            profiles_created = 0

            for idx, row in df.iterrows():
                try:
                    # 학생 이름 추출
                    student_name = row.get('1. 학생의 이름', '').strip()
                    if not student_name:
                        continue

                    # 학생이 이미 존재하는지 확인
                    existing_student = Student.query.filter_by(name=student_name).first()

                    if existing_student:
                        # 이미 학생이 있으면 프로필만 확인
                        student = existing_student

                        # 프로필이 이미 있는지 확인
                        existing_profile = StudentProfile.query.filter_by(student_id=student.student_id).first()
                        if existing_profile:
                            errors.append(f'행 {idx+2}: 학생 "{student_name}"의 프로필이 이미 존재합니다.')
                            error_count += 1
                            continue
                    else:
                        # 학생 생성
                        gender = row.get('2. 학생의 성별')
                        birthdate_raw = row.get('3. 학생의 생년월일')
                        school = row.get('6. 재학 중인 학교 이름')
                        grade_raw = row.get('7.  <2026> 기준으로 학생은 몇 학년인가요?')

                        # 생년월일 파싱
                        birthdate = None
                        if pd.notna(birthdate_raw):
                            try:
                                if isinstance(birthdate_raw, str):
                                    birthdate = datetime.strptime(birthdate_raw, '%Y-%m-%d').date()
                                else:
                                    birthdate = birthdate_raw.date() if hasattr(birthdate_raw, 'date') else None
                            except:
                                pass

                        # 학년 파싱 (예: "중학교 1학년" -> "중1")
                        grade = None
                        if pd.notna(grade_raw):
                            grade_str = str(grade_raw)
                            if '초등' in grade_str or '초' in grade_str:
                                for i in range(1, 7):
                                    if str(i) in grade_str:
                                        grade = f'초{i}'
                                        break
                            elif '중학' in grade_str or '중' in grade_str:
                                for i in range(1, 4):
                                    if str(i) in grade_str:
                                        grade = f'중{i}'
                                        break
                            elif '고등' in grade_str or '고' in grade_str:
                                for i in range(1, 4):
                                    if str(i) in grade_str:
                                        grade = f'고{i}'
                                        break

                        # Student 생성
                        student = Student(
                            student_id=str(uuid.uuid4()),
                            name=student_name,
                            grade=grade,
                            school=school if pd.notna(school) else None,
                            birth_date=birthdate
                        )
                        db.session.add(student)
                        db.session.flush()
                        students_created += 1

                    # StudentProfile 생성
                    profile = StudentProfile(
                        student_id=student.student_id,
                        survey_date=row.get('타임스탬프') if pd.notna(row.get('타임스탬프')) else None,
                        address=row.get('4. 주소(신규 학생들에게는 원고지 1권과 가이드가 발송됩니다, 발송 시 우편물을 받으실 수 있도록 동,호수까지 적어주시면 감사하겠습니다. 해외학생들은 배송이 어려운 점 양해 부탁드립니다).') if pd.notna(row.get('4. 주소(신규 학생들에게는 원고지 1권과 가이드가 발송됩니다, 발송 시 우편물을 받으실 수 있도록 동,호수까지 적어주시면 감사하겠습니다. 해외학생들은 배송이 어려운 점 양해 부탁드립니다).')) else None,
                        parent_contact=str(row.get('5. 학부모 연락처')) if pd.notna(row.get('5. 학부모 연락처')) else None,
                        current_school=row.get('6. 재학 중인 학교 이름') if pd.notna(row.get('6. 재학 중인 학교 이름')) else None,
                        reading_experience=row.get('8. 독서논술 수업 경험 및 기간') if pd.notna(row.get('8. 독서논술 수업 경험 및 기간')) else None,
                        reading_competency=int(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')) if pd.notna(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')) and str(row.get('9. 부모님이 느끼시는 학생의 독서역량을 체크해주세요.')).isdigit() else None,
                        weekly_reading_amount=row.get('10. 학생의 한 주 평균 독서량을 체크해주세요.') if pd.notna(row.get('10. 학생의 한 주 평균 독서량을 체크해주세요.')) else None,
                        preferred_genres=json.dumps([g.strip() for g in str(row.get('11. 학생이 선호하는 독서 분야를 모두 선택해주세요.')).split(',')] if pd.notna(row.get('11. 학생이 선호하는 독서 분야를 모두 선택해주세요.')) else [], ensure_ascii=False),
                        personality_traits=json.dumps([p.strip() for p in str(row.get('12. 학생의 성향을 모두 알려주세요. ')).split(',')] if pd.notna(row.get('12. 학생의 성향을 모두 알려주세요. ')) else [], ensure_ascii=False),
                        main_improvement_goal=row.get('13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)') if pd.notna(row.get('13. 모모의 책장 수업에서 가장 향상시키고 싶으신 부분은 무엇입니까? (최우선 요소 1개만 선택 가능)')) else None,
                        preferred_class_style=row.get('17.  가장 선호하는 수업 목표를 선택해주세요. (1개만 선택 가능)') if pd.notna(row.get('17.  가장 선호하는 수업 목표를 선택해주세요. (1개만 선택 가능)')) else None,
                        teacher_request=row.get('18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요. ') if pd.notna(row.get('18. 선생님께 수업에 관해 요청드리고 싶은 부분이 있다면 적어주세요. ')) else None,
                        referral_source=row.get('19. 모모의 책장을 어떻게 알게 되셨나요?') if pd.notna(row.get('19. 모모의 책장을 어떻게 알게 되셨나요?')) else None,
                        education_info_needs=json.dumps([e.strip() for e in str(row.get('1. 필요한 교육&입시 정보가 있으신가요?')).split(',')] if pd.notna(row.get('1. 필요한 교육&입시 정보가 있으신가요?')) else [], ensure_ascii=False),
                        academic_goals=json.dumps([a.strip() for a in str(row.get('2. 진학 목표가 있으신가요?')).split(',')] if pd.notna(row.get('2. 진학 목표가 있으신가요?')) else [], ensure_ascii=False),
                        career_interests=json.dumps([c.strip() for c in str(row.get('3. 관심 있는 학생의 진로 분야는 무엇입니까?')).split(',')] if pd.notna(row.get('3. 관심 있는 학생의 진로 분야는 무엇입니까?')) else [], ensure_ascii=False),
                        other_interests=row.get('4. 기타 교육분야 관심사항이 있으시면 모두 적어주세요.') if pd.notna(row.get('4. 기타 교육분야 관심사항이 있으시면 모두 적어주세요.')) else None,
                        sibling_info=row.get('형제/자매 정보를 입력해주세요.') if pd.notna(row.get('형제/자매 정보를 입력해주세요.')) else None,
                        created_by=current_user.user_id
                    )

                    db.session.add(profile)
                    profiles_created += 1
                    success_count += 1

                except Exception as e:
                    errors.append(f'행 {idx+2}: {str(e)}')
                    error_count += 1

            db.session.commit()

            flash(f'✅ 총 {success_count}건 성공 (학생 {students_created}명 생성, 프로필 {profiles_created}개 생성) | ❌ 실패: {error_count}건', 'success' if error_count == 0 else 'warning')

            if errors:
                session['import_errors'] = errors[:50]

            return redirect(url_for('admin.student_profiles'))

        except Exception as e:
            flash(f'파일 처리 중 오류 발생: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('admin/import_students_and_profiles.html')


# ============================================================================
# MBTI 기반 상담 기록 생성
# ============================================================================

@admin_bp.route('/consultations/new', methods=['GET', 'POST'])
@login_required
@requires_permission_level(3)  # 강사 이상
def create_consultation():
    """MBTI 기반 상담 기록 생성"""
    from app.models.consultation import ConsultationRecord
    from app.utils.mbti_recommendations import (
        get_student_latest_mbti,
        format_recommendations_for_consultation
    )
    from datetime import date as date_type

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        consultation_date_str = request.form.get('consultation_date')
        major_category = request.form.get('major_category')
        title = request.form.get('title')
        content = request.form.get('content')
        share_with_parents = request.form.get('share_with_parents') == 'on'

        # 날짜 변환
        consultation_date = date_type.fromisoformat(consultation_date_str) if consultation_date_str else date_type.today()

        # MBTI 정보 가져오기
        mbti_result = get_student_latest_mbti(student_id)
        mbti_type = mbti_result.type_combination if mbti_result else None
        mbti_recommendations = format_recommendations_for_consultation(mbti_result) if mbti_result else None
        recommended_style = mbti_result.mbti_type.type_name if mbti_result and mbti_result.mbti_type else None

        # 상담 기록 생성
        consultation = ConsultationRecord(
            consultation_date=consultation_date,
            counselor_id=current_user.user_id,
            student_id=student_id,
            major_category=major_category,
            title=title,
            content=content,
            student_mbti_type=mbti_type,
            recommended_teaching_style=recommended_style,
            teaching_recommendations=mbti_recommendations,
            share_with_parents=share_with_parents
        )

        if share_with_parents:
            consultation.share_to_parents()

        db.session.add(consultation)

        # 학부모에게 알림 (공유 설정 시)
        if share_with_parents:
            from app.models import ParentStudent
            parents = ParentStudent.query.filter_by(
                student_id=student_id,
                is_active=True
            ).all()

            for parent_rel in parents:
                notification = Notification(
                    user_id=parent_rel.parent_id,
                    notification_type='consultation_shared',
                    title='새로운 상담 기록',
                    message=f'{consultation.student.name} 학생의 상담 기록이 공유되었습니다.',
                    link_url=url_for('parent.view_consultation',
                                   student_id=student_id,
                                   consultation_id=consultation.consultation_id)
                )
                db.session.add(notification)

        db.session.commit()

        flash(f'상담 기록이 생성되었습니다.', 'success')
        return redirect(url_for('admin.consultation_detail', consultation_id=consultation.consultation_id))

    # GET: 학생 목록 조회
    students = Student.query.order_by(Student.name).all()

    return render_template('admin/consultations/create.html',
                         students=students,
                         today=date_type.today().isoformat())


@admin_bp.route('/api/student-mbti/<student_id>')
@login_required
@requires_permission_level(3)
def api_student_mbti(student_id):
    """학생 MBTI 정보 API (AJAX)"""
    from app.utils.mbti_recommendations import (
        get_student_latest_mbti,
        generate_teaching_recommendations,
        format_recommendations_for_consultation
    )

    mbti_result = get_student_latest_mbti(student_id)

    if not mbti_result:
        return jsonify({
            'success': False,
            'message': 'MBTI 검사 결과가 없습니다.'
        })

    recommendations = generate_teaching_recommendations(mbti_result)
    formatted_text = format_recommendations_for_consultation(mbti_result)

    return jsonify({
        'success': True,
        'mbti_type': mbti_result.type_combination,
        'type_name': mbti_result.mbti_type.type_name,
        'type_code': mbti_result.mbti_type.type_code,
        'combo_description': mbti_result.mbti_type.combo_description,
        'reading_style': recommendations['reading_style'],
        'speaking_style': recommendations['speaking_style'],
        'writing_style': recommendations['writing_style'],
        'strengths': recommendations['strengths'],
        'weaknesses': recommendations['weaknesses'],
        'tips': recommendations['tips'],
        'recommended_approaches': recommendations['recommended_approaches'],
        'formatted_recommendations': formatted_text
    })


@admin_bp.route('/mbti-results/<int:result_id>')
@login_required
@requires_permission_level(2)  # 매니저 이상
def mbti_result_detail(result_id):
    """MBTI 결과 상세 페이지"""
    from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType
    from app.utils.mbti_recommendations import generate_teaching_recommendations

    result = ReadingMBTIResult.query.get_or_404(result_id)
    mbti_type = ReadingMBTIType.query.get(result.type_id)
    recommendations = generate_teaching_recommendations(result)

    return render_template('admin/mbti_result_detail.html',
                         result=result,
                         mbti_type=mbti_type,
                         recommendations=recommendations)


@admin_bp.route('/class-messages')
@login_required
@requires_permission_level(2)
def messages_manage():
    """수업 공지 및 메세지 전체 관리"""
    from app.models.notification_reply import NotificationReply

    type_filter   = request.args.get('type', '')
    teacher_filter = request.args.get('teacher_id', '')
    search        = request.args.get('search', '').strip()
    page          = request.args.get('page', 1, type=int)
    per_page      = 25

    # 수신자가 학생인 메시지만 조회 (학부모 중복 제거)
    query = Notification.query.join(
        User, Notification.user_id == User.user_id
    ).filter(
        Notification.notification_type.in_(['class_announcement', 'homework_assignment']),
        User.role == 'student'
    )

    if type_filter:
        query = query.filter(Notification.notification_type == type_filter)
    if teacher_filter:
        query = query.filter(Notification.related_user_id == teacher_filter)
    if search:
        query = query.filter(db.or_(
            Notification.title.ilike(f'%{search}%'),
            Notification.message.ilike(f'%{search}%')
        ))

    all_notifications = query.order_by(Notification.created_at.desc()).all()

    # Python에서 그룹화 — (title, 발송자, 대상 entity, 유형)이 같으면 동일 메시지 묶음
    seen    = {}
    grouped = []
    for n in all_notifications:
        key = (n.title, n.related_user_id, n.related_entity_id, n.notification_type)
        if key not in seen:
            entry = {
                'notification': n,
                'total_sent':   0,
                'read_count':   0,
                '_reply_ids':   set(),
            }
            seen[key] = entry
            grouped.append(entry)
        g = seen[key]
        g['total_sent'] += 1
        if n.is_read:
            g['read_count'] += 1
        for reply in n.replies:
            g['_reply_ids'].add(reply.reply_id)

    for g in grouped:
        g['reply_count'] = len(g['_reply_ids'])
        del g['_reply_ids']

    # 통계
    total_count        = len(grouped)
    ann_count          = sum(1 for g in grouped if g['notification'].notification_type == 'class_announcement')
    hw_count           = total_count - ann_count
    today_count        = sum(
        1 for g in grouped
        if g['notification'].created_at.date() == datetime.utcnow().date()
    )

    # 페이지네이션 (Python slice)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page        = max(1, min(page, total_pages))
    items       = grouped[(page - 1) * per_page : page * per_page]

    # 강사 목록 (필터 셀렉트용)
    teacher_ids = list({g['notification'].related_user_id for g in grouped if g['notification'].related_user_id})
    teachers    = User.query.filter(User.user_id.in_(teacher_ids)).order_by(User.name).all()

    # 대상 이름 조회용 캐시
    course_cache  = {}
    student_cache = {}
    for g in items:
        n = g['notification']
        if n.related_entity_type == 'course' and n.related_entity_id:
            if n.related_entity_id not in course_cache:
                c = Course.query.get(n.related_entity_id)
                course_cache[n.related_entity_id] = c.course_name if c else '-'
        elif n.related_entity_type == 'student' and n.related_entity_id:
            if n.related_entity_id not in student_cache:
                s = Student.query.get(n.related_entity_id)
                student_cache[n.related_entity_id] = s.name if s else '-'

    return render_template(
        'admin/messages_manage.html',
        items=items,
        total_count=total_count,
        ann_count=ann_count,
        hw_count=hw_count,
        today_count=today_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        teachers=teachers,
        type_filter=type_filter,
        teacher_filter=teacher_filter,
        search=search,
        course_cache=course_cache,
        student_cache=student_cache,
    )


# ==================== API 사용량 대시보드 ====================

@admin_bp.route('/api-usage')
@login_required
@requires_permission_level(1)
def api_usage_dashboard():
    """Claude / Gemini API 월별 사용량 대시보드"""
    from app.models.api_usage_log import ApiUsageLog
    from sqlalchemy import extract, func

    # 테이블이 없으면 자동 생성
    try:
        ApiUsageLog.query.limit(1).all()
    except Exception:
        db.create_all()

    # 월 선택 파라미터
    today = date.today()
    year  = request.args.get('year',  today.year,  type=int)
    month = request.args.get('month', today.month, type=int)

    base_q = ApiUsageLog.query.filter(
        extract('year',  ApiUsageLog.created_at) == year,
        extract('month', ApiUsageLog.created_at) == month,
    )

    # ── 요약 통계 ─────────────────────────────────────────
    def summary(api_type=None):
        q = base_q
        if api_type:
            q = q.filter(ApiUsageLog.api_type == api_type)
        row = q.with_entities(
            func.count(ApiUsageLog.id),
            func.sum(ApiUsageLog.input_tokens),
            func.sum(ApiUsageLog.output_tokens),
            func.sum(ApiUsageLog.cache_read_tokens),
            func.sum(ApiUsageLog.cache_write_tokens),
            func.sum(ApiUsageLog.cost_usd),
        ).first()
        return {
            'count':        row[0] or 0,
            'input_tokens': row[1] or 0,
            'output_tokens':row[2] or 0,
            'cache_read':   row[3] or 0,
            'cache_write':  row[4] or 0,
            'cost_usd':     round(row[5] or 0, 4),
        }

    total_stats  = summary()
    claude_stats = summary('claude')
    gemini_stats = summary('gemini')

    # ── 일별 추이 (당월) ──────────────────────────────────
    daily_rows = base_q.with_entities(
        extract('day', ApiUsageLog.created_at).label('day'),
        ApiUsageLog.api_type,
        func.sum(ApiUsageLog.cost_usd).label('cost'),
        func.count(ApiUsageLog.id).label('cnt'),
    ).group_by('day', ApiUsageLog.api_type).order_by('day').all()

    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    daily_claude = [0.0] * (days_in_month + 1)
    daily_gemini = [0.0] * (days_in_month + 1)
    for row in daily_rows:
        d = int(row.day)
        if row.api_type == 'claude':
            daily_claude[d] = round(row.cost or 0, 4)
        else:
            daily_gemini[d] = round(row.cost or 0, 4)

    # ── 계정별 사용량 ─────────────────────────────────────
    user_rows = base_q.with_entities(
        ApiUsageLog.user_id,
        ApiUsageLog.api_type,
        func.count(ApiUsageLog.id).label('cnt'),
        func.sum(ApiUsageLog.input_tokens + ApiUsageLog.output_tokens).label('total_tok'),
        func.sum(ApiUsageLog.cost_usd).label('cost'),
    ).group_by(ApiUsageLog.user_id, ApiUsageLog.api_type).all()

    # user_id → User 매핑
    uid_set = {r.user_id for r in user_rows if r.user_id}
    users_map = {u.user_id: u for u in User.query.filter(User.user_id.in_(uid_set)).all()}

    user_stats = {}   # user_id → {name, role, claude:{}, gemini:{}}
    for r in user_rows:
        uid = r.user_id or '(미확인)'
        if uid not in user_stats:
            u = users_map.get(uid)
            user_stats[uid] = {
                'name': u.name if u else '(알 수 없음)',
                'role': u.role if u else '-',
                'claude': {'cnt': 0, 'total_tok': 0, 'cost': 0.0},
                'gemini': {'cnt': 0, 'total_tok': 0, 'cost': 0.0},
            }
        key = r.api_type if r.api_type in ('claude', 'gemini') else 'claude'
        user_stats[uid][key]['cnt']       += r.cnt or 0
        user_stats[uid][key]['total_tok'] += int(r.total_tok or 0)
        user_stats[uid][key]['cost']      += round(r.cost or 0, 4)

    user_list = sorted(user_stats.values(),
                       key=lambda x: x['claude']['cost'] + x['gemini']['cost'],
                       reverse=True)

    # ── 월 선택용 목록 ────────────────────────────────────
    month_options = []
    for i in range(12):
        d = today.replace(day=1) - timedelta(days=1) * (i * 30)
        month_options.append({'year': d.year, 'month': d.month,
                               'label': f"{d.year}년 {d.month}월"})

    USD_TO_KRW = 1400

    return render_template(
        'admin/api_usage.html',
        year=year, month=month,
        total_stats=total_stats,
        claude_stats=claude_stats,
        gemini_stats=gemini_stats,
        daily_claude=daily_claude[1:],
        daily_gemini=daily_gemini[1:],
        days_in_month=days_in_month,
        user_list=user_list,
        month_options=month_options,
        USD_TO_KRW=USD_TO_KRW,
    )


# ==================== 아이디 관리 ====================

@admin_bp.route('/account-management')
@login_required
@requires_permission_level(2)
def account_management():
    """비활성 계정 조회 및 복원"""
    role_filter = request.args.get('role', '').strip()
    search = request.args.get('search', '').strip()

    # 비활성 계정 (삭제되지 않은 것만)
    query = User.query.filter_by(is_active=False).filter(
        User.role.in_(['teacher', 'parent', 'student'])
    ).filter(db.or_(User.is_deleted == False, User.is_deleted == None))

    if role_filter:
        query = query.filter_by(role=role_filter)

    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )

    users = query.order_by(User.created_at.desc()).all()

    # 삭제된 계정
    deleted_query = User.query.filter_by(is_deleted=True).filter(
        User.role.in_(['teacher', 'parent', 'student'])
    )
    if role_filter:
        deleted_query = deleted_query.filter_by(role=role_filter)
    if search:
        deleted_query = deleted_query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    deleted_users = deleted_query.order_by(User.deleted_at.desc()).all()

    # 역할별 통계
    role_counts = {
        'teacher': User.query.filter_by(is_active=False, role='teacher').filter(
            db.or_(User.is_deleted == False, User.is_deleted == None)).count(),
        'parent': User.query.filter_by(is_active=False, role='parent').filter(
            db.or_(User.is_deleted == False, User.is_deleted == None)).count(),
        'student': User.query.filter_by(is_active=False, role='student').filter(
            db.or_(User.is_deleted == False, User.is_deleted == None)).count(),
    }
    total_inactive = sum(role_counts.values())

    return render_template('admin/account_management.html',
                           users=users,
                           deleted_users=deleted_users,
                           total_inactive=total_inactive,
                           role_counts=role_counts,
                           role_filter=role_filter,
                           search=search)


@admin_bp.route('/users/<string:user_id>/restore', methods=['POST'])
@login_required
@requires_permission_level(2)
def restore_user(user_id):
    """비활성 계정 복원"""
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    flash(f'{user.name} 계정이 복원되었습니다.', 'success')
    return redirect(url_for('admin.account_management'))


@admin_bp.route('/help')
@login_required
@requires_permission_level(2)
def help_page():
    """관리자 사이트 사용 설명서"""
    return render_template('admin/help.html')


@admin_bp.route('/teacher-hours')
@login_required
@requires_permission_level(2)
def teacher_hours():
    """강사 월별 시수 계산표"""
    from collections import defaultdict
    from app.utils.hours_calculator import build_teacher_monthly_data
    from app.models.teacher_hours import TeacherHoursCorrection

    year  = request.args.get('year',  date.today().year,  type=int)
    month = request.args.get('month', date.today().month, type=int)

    teachers = User.query.filter(
        User.role == 'teacher',
        User.is_active == True
    ).order_by(User.name).all()

    data = {t.user_id: build_teacher_monthly_data(t.user_id, year, month) for t in teachers}

    corrections = TeacherHoursCorrection.query.filter_by(year=year, month=month).all()
    corrections_map = defaultdict(list)
    for c in corrections:
        corrections_map[c.teacher_id].append(c)

    return render_template(
        'admin/teacher_hours.html',
        teachers=teachers,
        data=data,
        corrections=corrections_map,
        year=year,
        month=month,
    )


@admin_bp.route('/teacher-hours/correction', methods=['POST'])
@login_required
@requires_permission_level(2)
def add_hours_correction():
    """시수 수동 보정 추가 (AJAX)"""
    from app.models.teacher_hours import TeacherHoursCorrection

    teacher_id = request.form.get('teacher_id', '').strip()
    year       = request.form.get('year',  type=int)
    month      = request.form.get('month', type=int)
    hours_delta = request.form.get('hours_delta', type=float)
    note        = request.form.get('note', '').strip()
    date_str    = request.form.get('correction_date', '').strip()
    course_type = request.form.get('course_type', '').strip() or None

    if not teacher_id or year is None or month is None or hours_delta is None:
        return jsonify({'success': False, 'error': '필수 값이 누락되었습니다.'}), 400

    correction_date = None
    if date_str:
        try:
            from datetime import date as _date
            correction_date = _date.fromisoformat(date_str)
        except ValueError:
            return jsonify({'success': False, 'error': '날짜 형식이 올바르지 않습니다.'}), 400

    correction = TeacherHoursCorrection(
        teacher_id=teacher_id,
        year=year,
        month=month,
        correction_date=correction_date,
        course_type=course_type,
        hours_delta=hours_delta,
        note=note or None,
        created_by=current_user.user_id,
    )
    db.session.add(correction)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': correction.id,
        'hours_delta': correction.hours_delta,
        'note': correction.note or '',
        'correction_date': correction.correction_date.isoformat() if correction.correction_date else '',
        'course_type': correction.course_type or '',
    })


@admin_bp.route('/teacher-hours/correction/<int:cid>', methods=['DELETE'])
@login_required
@requires_permission_level(2)
def delete_hours_correction(cid):
    """시수 수동 보정 삭제 (AJAX)"""
    from app.models.teacher_hours import TeacherHoursCorrection

    correction = TeacherHoursCorrection.query.get_or_404(cid)
    db.session.delete(correction)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/help/pdf')
@login_required
@requires_permission_level(2)
def help_pdf():
    """관리자 사용 설명서 PDF 다운로드"""
    from app.utils.pdf_utils import generate_admin_manual_pdf
    return generate_admin_manual_pdf()
