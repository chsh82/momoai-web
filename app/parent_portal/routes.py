# -*- coding: utf-8 -*-
"""학부모 포털 라우트"""
from flask import render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os

from app.parent_portal import parent_bp
from app.models import (db, Student, ParentStudent, CourseEnrollment,
                       TeacherFeedback, Payment, Attendance, CourseSession, User)
from app.models.essay import Essay
from app.models.teaching_material import TeachingMaterial, TeachingMaterialDownload
from app.models.video import Video, VideoView
from app.models.parent_link_request import ParentLinkRequest
from app.models.notification import Notification
from app.models.announcement import Announcement, AnnouncementRead
from app.models.student_profile import StudentProfile
from app.models.consultation import ConsultationRecord
from app.utils.decorators import requires_role
from app.utils.course_utils import calculate_tuition_amount
from app.utils.content_access import can_access_content, format_file_size, extract_youtube_video_id
from app.parent_portal.forms import StudentRegistrationSurveyForm


@parent_bp.route('/')
@login_required
@requires_role('parent', 'admin')
def index():
    """학부모 대시보드"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    # 전체 통계
    total_children = len(children)
    total_enrollments = 0
    unread_feedbacks = 0
    total_unpaid = 0

    for child in children:
        # 수강 중인 수업
        enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id,
            status='active'
        ).count()
        total_enrollments += enrollments

        # 읽지 않은 피드백
        unread = TeacherFeedback.query.filter_by(
            student_id=child.student_id,
            parent_id=current_user.user_id,
            is_read=False
        ).count()
        unread_feedbacks += unread

        # 미납 금액
        active_enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id,
            status='active'
        ).all()

        for enrollment in active_enrollments:
            calc = calculate_tuition_amount(enrollment)
            total_unpaid += calc['remaining_amount']

    # 최근 피드백
    recent_feedbacks = TeacherFeedback.query.filter_by(
        parent_id=current_user.user_id
    ).order_by(TeacherFeedback.created_at.desc()).limit(5).all()

    # ===== 차트 데이터 생성 =====
    from sqlalchemy import func, extract
    from datetime import timedelta
    import json

    # 1. 자녀별 출석률 비교
    child_names = []
    child_attendance_rates = []
    for child in children:
        enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id,
            status='active'
        ).all()

        if enrollments:
            total_sessions = sum(e.course.total_sessions for e in enrollments if e.course.total_sessions > 0)
            attended_sessions = sum(e.attended_sessions for e in enrollments)

            if total_sessions > 0:
                rate = (attended_sessions / total_sessions) * 100
                child_names.append(child.name)
                child_attendance_rates.append(round(rate, 1))

    # 2. 자녀별 첨삭 수 비교
    child_essay_names = []
    child_essay_counts = []
    for child in children:
        essay_count = Essay.query.filter_by(student_id=child.student_id).count()
        if essay_count > 0:
            child_essay_names.append(child.name)
            child_essay_counts.append(essay_count)

    # 3. 월별 결제 금액 추이 (최근 6개월)
    six_months_ago = datetime.utcnow() - timedelta(days=180)

    # 모든 자녀의 student_id 목록
    child_ids = [c.student_id for c in children]

    monthly_payments = db.session.query(
        extract('year', Payment.created_at).label('year'),
        extract('month', Payment.created_at).label('month'),
        func.sum(Payment.amount).label('total')
    ).join(CourseEnrollment, Payment.enrollment_id == CourseEnrollment.enrollment_id)\
     .filter(
         CourseEnrollment.student_id.in_(child_ids) if child_ids else False,
         Payment.created_at >= six_months_ago
     ).group_by('year', 'month')\
     .order_by('year', 'month').all()

    payment_labels = [f"{int(row.year)}-{int(row.month):02d}" for row in monthly_payments]
    payment_data = [int(row.total) for row in monthly_payments]

    return render_template('parent/index.html',
                         children=children,
                         total_children=total_children,
                         total_enrollments=total_enrollments,
                         unread_feedbacks=unread_feedbacks,
                         total_unpaid=total_unpaid,
                         recent_feedbacks=recent_feedbacks,
                         child_names=json.dumps(child_names),
                         child_attendance_rates=json.dumps(child_attendance_rates),
                         child_essay_names=json.dumps(child_essay_names),
                         child_essay_counts=json.dumps(child_essay_counts),
                         payment_labels=json.dumps(payment_labels),
                         payment_data=json.dumps(payment_data))


@parent_bp.route('/children')
@login_required
@requires_role('parent', 'admin')
def children():
    """자녀 목록"""
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children_data = []
    for pr in parent_relations:
        student = pr.student

        # 수강 중인 수업
        enrollments = CourseEnrollment.query.filter_by(
            student_id=student.student_id,
            status='active'
        ).all()

        # 평균 출석률
        total_rate = 0
        count = 0
        for enrollment in enrollments:
            total_rate += enrollment.attendance_rate
            count += 1

        avg_attendance_rate = total_rate / count if count > 0 else 0

        # 읽지 않은 피드백
        unread_feedbacks = TeacherFeedback.query.filter_by(
            student_id=student.student_id,
            parent_id=current_user.user_id,
            is_read=False
        ).count()

        # 미납 금액
        unpaid_amount = 0
        for enrollment in enrollments:
            calc = calculate_tuition_amount(enrollment)
            unpaid_amount += calc['remaining_amount']

        children_data.append({
            'student': student,
            'enrollments': enrollments,
            'avg_attendance_rate': avg_attendance_rate,
            'unread_feedbacks': unread_feedbacks,
            'unpaid_amount': unpaid_amount
        })

    return render_template('parent/children.html',
                         children_data=children_data)


@parent_bp.route('/children/<student_id>')
@login_required
@requires_role('parent', 'admin')
def child_detail(student_id):
    """자녀 상세 정보"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.children'))

    student = Student.query.get_or_404(student_id)

    # 수강 중인 수업
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 첨삭 기록 (최근 5개)
    recent_essays = student.essays[:5] if hasattr(student, 'essays') else []

    return render_template('parent/child_detail.html',
                         student=student,
                         enrollments=enrollments,
                         recent_essays=recent_essays)


@parent_bp.route('/children/<student_id>/attendance')
@login_required
@requires_role('parent', 'admin')
def child_attendance(student_id):
    """자녀 출석 현황"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.children'))

    student = Student.query.get_or_404(student_id)

    # 필터
    course_filter = request.args.get('course', '').strip()

    # 수강 중인 수업 목록
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 선택된 수업 또는 전체
    if course_filter:
        selected_enrollments = [e for e in enrollments if e.course_id == course_filter]
    else:
        selected_enrollments = enrollments

    # 출석 레코드 조회
    attendance_data = []
    for enrollment in selected_enrollments:
        # 이 수업의 모든 세션과 출석 기록
        sessions = CourseSession.query.filter_by(
            course_id=enrollment.course_id
        ).order_by(CourseSession.session_date.desc()).all()

        for session in sessions:
            attendance = Attendance.query.filter_by(
                session_id=session.session_id,
                student_id=student_id
            ).first()

            if attendance:
                attendance_data.append({
                    'course': enrollment.course,
                    'session': session,
                    'attendance': attendance
                })

    return render_template('parent/child_attendance.html',
                         student=student,
                         enrollments=enrollments,
                         attendance_data=attendance_data,
                         course_filter=course_filter)


@parent_bp.route('/children/<student_id>/feedback')
@login_required
@requires_role('parent', 'admin')
def child_feedback(student_id):
    """자녀 피드백 조회"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.children'))

    student = Student.query.get_or_404(student_id)

    # 나에게 온 피드백 (학생 비공개)
    feedbacks = TeacherFeedback.query.filter_by(
        student_id=student_id,
        parent_id=current_user.user_id
    ).order_by(TeacherFeedback.created_at.desc()).all()

    # 읽지 않은 피드백 수
    unread_count = sum(1 for f in feedbacks if not f.is_read)

    return render_template('parent/child_feedback.html',
                         student=student,
                         feedbacks=feedbacks,
                         unread_count=unread_count)


@parent_bp.route('/feedback/<feedback_id>')
@login_required
@requires_role('parent', 'admin')
def view_feedback(feedback_id):
    """피드백 상세 보기"""
    feedback = TeacherFeedback.query.get_or_404(feedback_id)

    # 권한 확인
    if feedback.parent_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    # 읽음 처리
    if not feedback.is_read:
        feedback.mark_as_read()
        db.session.commit()

    return render_template('parent/feedback_detail.html',
                         feedback=feedback)


@parent_bp.route('/children/<student_id>/payments')
@login_required
@requires_role('parent', 'admin')
def child_payments(student_id):
    """자녀 결제 관리"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.children'))

    student = Student.query.get_or_404(student_id)

    # 수강 중인 수업별 결제 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    payment_data = []
    total_paid = 0
    total_unpaid = 0

    for enrollment in enrollments:
        calc = calculate_tuition_amount(enrollment)

        # 결제 이력
        payments = Payment.query.filter_by(
            enrollment_id=enrollment.enrollment_id,
            status='completed'
        ).order_by(Payment.paid_at.desc()).all()

        payment_data.append({
            'enrollment': enrollment,
            'course': enrollment.course,
            'calculation': calc,
            'payments': payments
        })

        total_paid += calc['paid_amount']
        total_unpaid += calc['remaining_amount']

    return render_template('parent/child_payments.html',
                         student=student,
                         payment_data=payment_data,
                         total_paid=total_paid,
                         total_unpaid=total_unpaid)


@parent_bp.route('/payments')
@login_required
@requires_role('parent', 'admin')
def all_payments():
    """전체 결제 내역"""
    # 내 자녀들의 모든 결제 내역
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    student_ids = [pr.student_id for pr in parent_relations]

    payments = Payment.query.filter(
        Payment.student_id.in_(student_ids)
    ).order_by(Payment.created_at.desc()).all()

    return render_template('parent/all_payments.html',
                         payments=payments)


@parent_bp.route('/feedback')
@login_required
@requires_role('parent', 'admin')
def all_feedback():
    """전체 피드백"""
    feedbacks = TeacherFeedback.query.filter_by(
        parent_id=current_user.user_id
    ).order_by(TeacherFeedback.created_at.desc()).all()

    # 읽지 않은 피드백 수
    unread_count = sum(1 for f in feedbacks if not f.is_read)

    return render_template('parent/all_feedback.html',
                         feedbacks=feedbacks,
                         unread_count=unread_count)


# ==================== 보강수업 신청 (학부모) ====================

@parent_bp.route('/makeup-classes/<student_id>')
@login_required
@requires_role('parent', 'admin')
def makeup_classes(student_id):
    """자녀의 보강수업 신청"""
    from app.models.makeup_request import MakeupClassRequest
    from app.models import Course
    
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()
    
    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))
    
    student = Student.query.get_or_404(student_id)
    
    # 보강신청 가능한 수업 조회 (같은 학년, makeup_class_allowed=True, 진행 중)
    available_courses = Course.query.filter(
        Course.grade == student.grade,
        Course.makeup_class_allowed == True,
        Course.status == 'active'
    ).order_by(Course.weekday, Course.start_time).all()
    
    # 해당 학생의 신청 내역 조회 (최근 5건만)
    student_requests = MakeupClassRequest.query.filter_by(
        student_id=student_id
    ).order_by(MakeupClassRequest.request_date.desc()).limit(5).all()

    return render_template('parent/makeup_classes.html',
                         student=student,
                         available_courses=available_courses,
                         student_requests=student_requests)


@parent_bp.route('/makeup-classes/<student_id>/request/<course_id>', methods=['POST'])
@login_required
@requires_role('parent', 'admin')
def request_makeup_class(student_id, course_id):
    """자녀의 보강수업 신청"""
    from app.models.makeup_request import MakeupClassRequest
    from app.models import Course, User
    from app.models.notification import Notification
    
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()
    
    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))
    
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)
    
    # 보강신청 가능 여부 확인
    if not course.makeup_class_allowed:
        flash('이 수업은 보강신청이 불가능합니다.', 'error')
        return redirect(url_for('parent.makeup_classes', student_id=student_id))
    
    # 학년 확인
    if course.grade != student.grade:
        flash('자녀의 학년 수업만 신청할 수 있습니다.', 'error')
        return redirect(url_for('parent.makeup_classes', student_id=student_id))
    
    # 중복 신청 확인
    existing_request = MakeupClassRequest.query.filter_by(
        student_id=student_id,
        requested_course_id=course_id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('이미 해당 수업에 대한 보강신청이 진행 중입니다.', 'warning')
        return redirect(url_for('parent.makeup_classes', student_id=student_id))
    
    # 신청 사유
    reason = request.form.get('reason', '').strip()
    
    # 보강수업 신청 생성
    makeup_request = MakeupClassRequest(
        student_id=student_id,
        requested_course_id=course_id,
        reason=reason,
        requested_by=current_user.user_id,
        status='pending'
    )
    
    db.session.add(makeup_request)
    
    # 관리자에게 알림
    from flask import url_for
    admins = User.query.filter(User.role_level <= 2).all()
    for admin in admins:
        notification = Notification(
            user_id=admin.user_id,
            notification_type='makeup_request',
            title='새로운 보강수업 신청',
            message=f'{student.name} 학생의 학부모가 "{course.course_name}" 보강수업을 신청했습니다.',
            related_entity_type='makeup_request',
            related_entity_id=makeup_request.request_id,
            link_url=url_for('admin.makeup_requests', _external=False)
        )
        db.session.add(notification)
    
    db.session.commit()
    
    flash(f'{student.name} 학생의 보강수업 신청이 완료되었습니다. 관리자 승인을 기다려주세요.', 'success')
    return redirect(url_for('parent.makeup_classes', student_id=student_id))


@parent_bp.route('/makeup-classes/<student_id>/cancel/<request_id>', methods=['POST'])
@login_required
@requires_role('parent', 'admin')
def cancel_makeup_request(student_id, request_id):
    """보강수업 신청 취소"""
    from app.models.makeup_request import MakeupClassRequest
    
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()
    
    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))
    
    makeup_request = MakeupClassRequest.query.get_or_404(request_id)
    
    # 권한 확인
    if makeup_request.student_id != student_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.makeup_classes', student_id=student_id))
    
    # pending 상태만 취소 가능
    if makeup_request.status != 'pending':
        flash('대기 중인 신청만 취소할 수 있습니다.', 'warning')
        return redirect(url_for('parent.makeup_classes', student_id=student_id))
    
    # 신청 삭제
    db.session.delete(makeup_request)
    db.session.commit()
    
    flash('보강수업 신청이 취소되었습니다.', 'info')
    return redirect(url_for('parent.makeup_classes', student_id=student_id))


@parent_bp.route('/makeup-classes')
@login_required
@requires_role('parent', 'admin')
def makeup_classes_index():
    """보강수업 신청 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    return render_template('parent/makeup_classes_index.html',
                         children=children)


@parent_bp.route('/makeup-classes/<student_id>/history')
@login_required
@requires_role('parent', 'admin')
def makeup_classes_history(student_id):
    """자녀의 보강수업 신청 전체 이력"""
    from app.models.makeup_request import MakeupClassRequest
    from app.models import Course

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 전체 신청 내역 조회
    all_requests = MakeupClassRequest.query.filter_by(
        student_id=student_id
    ).order_by(MakeupClassRequest.request_date.desc()).all()

    # 상태별 통계
    pending_count = sum(1 for r in all_requests if r.status == 'pending')
    approved_count = sum(1 for r in all_requests if r.status == 'approved')
    rejected_count = sum(1 for r in all_requests if r.status == 'rejected')

    return render_template('parent/makeup_classes_history.html',
                         student=student,
                         all_requests=all_requests,
                         pending_count=pending_count,
                         approved_count=approved_count,
                         rejected_count=rejected_count)


# ==================== 출결 현황 ====================

@parent_bp.route('/attendance')
@login_required
@requires_role('parent', 'admin')
def attendance_index():
    """출결 현황 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    return render_template('parent/attendance_index.html',
                         children=children)


@parent_bp.route('/attendance/<student_id>')
@login_required
@requires_role('parent', 'admin')
def attendance(student_id):
    """자녀의 출결 현황"""
    from app.models import Course

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 학생의 모든 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id
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

    return render_template('parent/attendance.html',
                         student=student,
                         course_attendance_data=course_attendance_data)


# ==================== 과제 및 첨삭 확인 ====================

@parent_bp.route('/essays')
@login_required
@requires_role('parent', 'admin')
def essays_index():
    """과제 및 첨삭 확인 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    # 각 자녀의 정보와 에세이 통계를 함께 저장
    children = []
    for pr in parent_relations:
        child_data = {
            'student': pr.student,
            'student_id': pr.student.student_id,
            'name': pr.student.name,
            'grade': pr.student.grade,
            'essay_count': Essay.query.filter_by(student_id=pr.student.student_id).count(),
            'pending_count': Essay.query.filter_by(student_id=pr.student.student_id, status='pending').count(),
            'completed_count': Essay.query.filter_by(student_id=pr.student.student_id, status='completed').count()
        }
        children.append(child_data)

    return render_template('parent/essays_index.html',
                         children=children)


@parent_bp.route('/essays/<student_id>')
@login_required
@requires_role('parent', 'admin')
def essays(student_id):
    """자녀의 과제 및 첨삭 목록"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 자녀의 모든 에세이
    essays = Essay.query.filter_by(
        student_id=student_id
    ).order_by(Essay.created_at.desc()).all()

    return render_template('parent/essays.html',
                         student=student,
                         essays=essays)


@parent_bp.route('/essays/<student_id>/<essay_id>')
@login_required
@requires_role('parent', 'admin')
def view_essay(student_id, essay_id):
    """자녀의 첨삭 상세 보기"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)
    essay = Essay.query.get_or_404(essay_id)

    # 에세이가 해당 학생의 것인지 확인
    if essay.student_id != student_id:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.essays', student_id=student_id))

    return render_template('parent/view_essay.html',
                         student=student,
                         essay=essay)


# ==================== 학습 교재 (Teaching Materials) ====================

@parent_bp.route('/materials')
@login_required
@requires_role('parent', 'admin')
def materials_list():
    """교재 목록 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    return render_template('parent/materials_index.html',
                         children=children)


@parent_bp.route('/materials/<student_id>')
@login_required
@requires_role('parent', 'admin')
def child_materials(student_id):
    """자녀의 학습 교재 목록"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

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

    return render_template('parent/child_materials.html',
                         student=student,
                         materials=accessible_materials,
                         search=search,
                         grade_filter=grade_filter)


@parent_bp.route('/materials/<student_id>/<material_id>')
@login_required
@requires_role('parent', 'admin')
def child_material_detail(student_id, material_id):
    """자녀의 교재 상세 정보"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)
    material = TeachingMaterial.query.get_or_404(material_id)

    # 접근 권한 확인
    if not can_access_content(material, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.child_materials', student_id=student_id))

    # 파일 크기 포맷팅
    file_size_formatted = format_file_size(material.file_size)

    return render_template('parent/child_material_detail.html',
                         student=student,
                         material=material,
                         file_size_formatted=file_size_formatted)


@parent_bp.route('/materials/<student_id>/<material_id>/download')
@login_required
@requires_role('parent', 'admin')
def download_child_material(student_id, material_id):
    """자녀의 교재 다운로드"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)
    material = TeachingMaterial.query.get_or_404(material_id)

    # 접근 권한 확인
    if not can_access_content(material, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.child_materials', student_id=student_id))

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

@parent_bp.route('/videos')
@login_required
@requires_role('parent', 'admin')
def videos_list():
    """동영상 목록 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    return render_template('parent/videos_index.html',
                         children=children)


@parent_bp.route('/videos/<student_id>')
@login_required
@requires_role('parent', 'admin')
def child_videos(student_id):
    """자녀의 학습 동영상 목록"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

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

    return render_template('parent/child_videos.html',
                         student=student,
                         videos=accessible_videos,
                         search=search,
                         grade_filter=grade_filter)


@parent_bp.route('/videos/<student_id>/<video_id>')
@login_required
@requires_role('parent', 'admin')
def child_video_player(student_id, video_id):
    """자녀의 동영상 플레이어"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)
    video = Video.query.get_or_404(video_id)

    # 접근 권한 확인
    if not can_access_content(video, current_user, student):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.child_videos', student_id=student_id))

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

    return render_template('parent/child_video_player.html',
                         student=student,
                         video=video,
                         youtube_video_id=youtube_video_id)


# ============================================================================
# 자녀 연결 요청 (Parent-Child Link Requests)
# ============================================================================

@parent_bp.route('/link-child', methods=['GET', 'POST'])
@login_required
@requires_role('parent', 'admin')
def link_child():
    """자녀 연결 요청"""
    if request.method == 'POST':
        # 생년월일 문자열을 date 객체로 변환
        birth_date_str = request.form.get('student_birth_date')
        birth_date = None
        if birth_date_str:
            try:
                from datetime import datetime
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                birth_date = None

        # 학부모가 입력한 자녀 정보
        link_request = ParentLinkRequest(
            parent_id=current_user.user_id,
            student_name=request.form.get('student_name').strip(),
            student_birth_date=birth_date,
            student_grade=request.form.get('student_grade'),
            student_school=request.form.get('student_school').strip() if request.form.get('student_school') else None,
            relation_type=request.form.get('relation_type', 'parent'),
            additional_info=request.form.get('additional_info').strip() if request.form.get('additional_info') else None,
            status='pending'
        )
        db.session.add(link_request)
        db.session.commit()

        # 관리자에게 알림 전송
        admin_users = User.query.filter(User.role_level <= 2).all()  # admin, manager
        for admin in admin_users:
            notification = Notification(
                user_id=admin.user_id,
                notification_type='parent_link_request',
                title='학부모 자녀 연결 요청',
                message=f'{current_user.name}님이 자녀 연결을 요청했습니다. (자녀명: {link_request.student_name})',
                link_url=url_for('admin.parent_link_requests')
            )
            db.session.add(notification)

        db.session.commit()

        flash('자녀 연결 요청이 제출되었습니다. 관리자 검토 후 연결됩니다. (1-2일 소요)', 'success')
        return redirect(url_for('parent.link_requests'))

    return render_template('parent/link_child.html')


@parent_bp.route('/link-requests')
@login_required
@requires_role('parent', 'admin')
def link_requests():
    """내 연결 요청 목록"""
    # 내가 제출한 연결 요청들
    requests = ParentLinkRequest.query.filter_by(
        parent_id=current_user.user_id
    ).order_by(ParentLinkRequest.created_at.desc()).all()

    # 이미 연결된 자녀 목록
    linked_children = db.session.query(Student).join(ParentStudent).filter(
        ParentStudent.parent_id == current_user.user_id,
        ParentStudent.is_active == True
    ).all()

    return render_template('parent/link_requests.html',
                         requests=requests,
                         linked_children=linked_children)


@parent_bp.route('/link-requests/<request_id>/cancel', methods=['POST'])
@login_required
@requires_role('parent', 'admin')
def cancel_link_request(request_id):
    """연결 요청 취소"""
    link_request = ParentLinkRequest.query.filter_by(
        request_id=request_id,
        parent_id=current_user.user_id
    ).first_or_404()

    if link_request.status != 'pending':
        flash('이미 처리된 요청은 취소할 수 없습니다.', 'warning')
        return redirect(url_for('parent.link_requests'))

    link_request.status = 'cancelled'
    db.session.commit()

    flash('연결 요청이 취소되었습니다.', 'info')
    return redirect(url_for('parent.link_requests'))


# ==================== 공지사항 ====================

@parent_bp.route('/announcements')
@login_required
@requires_role('parent', 'admin')
def announcements():
    """공지사항 목록"""
    # 학부모에게 표시할 공지사항 조회
    all_announcements = Announcement.query.filter_by(
        is_published=True
    ).order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc()
    ).all()

    # 현재 사용자가 볼 수 있는 공지만 필터링
    visible_announcements = []
    for announcement in all_announcements:
        if announcement.is_active:
            target_roles = announcement.target_roles_list
            if 'all' in target_roles or 'parent' in target_roles:
                visible_announcements.append(announcement)

    # 읽음 상태 추가
    announcements_with_status = []
    for announcement in visible_announcements:
        is_read = announcement.is_read_by(current_user.user_id)
        announcements_with_status.append({
            'announcement': announcement,
            'is_read': is_read
        })

    return render_template('parent/announcements.html',
                         announcements=announcements_with_status)


@parent_bp.route('/announcements/<announcement_id>')
@login_required
@requires_role('parent', 'admin')
def view_announcement(announcement_id):
    """공지사항 상세"""
    announcement = Announcement.query.get_or_404(announcement_id)

    # 권한 확인
    if not announcement.is_active:
        flash('해당 공지사항을 볼 수 없습니다.', 'error')
        return redirect(url_for('parent.announcements'))

    target_roles = announcement.target_roles_list
    if 'all' not in target_roles and 'parent' not in target_roles:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.announcements'))

    # 읽음 처리
    announcement.mark_as_read_by(current_user.user_id)
    db.session.commit()

    return render_template('parent/view_announcement.html',
                         announcement=announcement)


# ==================== 데이터 내보내기 ====================

@parent_bp.route('/export/child-attendance/<student_id>')
@login_required
@requires_role('parent', 'admin')
def export_child_attendance(student_id):
    """자녀 출석 내역 Excel 내보내기"""
    from app.utils.export_utils import export_attendance_to_excel
    from datetime import datetime

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 출석 데이터 조회
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id
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


@parent_bp.route('/export/child-payments/<student_id>')
@login_required
@requires_role('parent', 'admin')
def export_child_payments(student_id):
    """자녀 결제 내역 Excel 내보내기"""
    from app.utils.export_utils import export_payments_to_excel

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 결제 내역 조회
    payments = Payment.query.join(CourseEnrollment).filter(
        CourseEnrollment.student_id == student_id
    ).order_by(Payment.created_at.desc()).all()

    return export_payments_to_excel(payments)


@parent_bp.route('/export/child-report/<student_id>')
@login_required
@requires_role('parent', 'admin')
def export_child_report(student_id):
    """자녀 종합 리포트 Excel 내보내기"""
    from app.utils.export_utils import export_student_report_to_excel
    from app.models.essay import Essay

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student_id
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

@parent_bp.route('/export/child-report-pdf/<student_id>')
@login_required
@requires_role('parent', 'admin')
def export_child_report_pdf(student_id):
    """자녀 성적표 PDF 내보내기"""
    from app.utils.pdf_utils import generate_student_report_card_pdf
    from app.models.essay import Essay

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 수강 정보
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student_id
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


@parent_bp.route('/export/child-attendance-certificate/<student_id>')
@login_required
@requires_role('parent', 'admin')
def export_child_attendance_certificate(student_id):
    """자녀 출석 확인서 PDF 내보내기"""
    from app.utils.pdf_utils import generate_attendance_certificate_pdf
    from datetime import timedelta

    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 기간 설정 (최근 3개월)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)

    # 출석 데이터 조회
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id
    ).all()

    attendance_records = []
    for enrollment in enrollments:
        attendances = Attendance.query.filter_by(
            enrollment_id=enrollment.enrollment_id
        ).join(CourseSession).filter(
            CourseSession.session_date >= start_date.date(),
            CourseSession.session_date <= end_date.date()
        ).order_by(CourseSession.session_date).all()

        for attendance in attendances:
            session = CourseSession.query.get(attendance.session_id)
            attendance_records.append({
                'date': session.session_date.strftime('%Y-%m-%d'),
                'course_name': enrollment.course.course_name,
                'status': attendance.status,
                'notes': attendance.notes
            })

    return generate_attendance_certificate_pdf(student, start_date, end_date, attendance_records)


# ============================================================
# 독서 논술 MBTI
# ============================================================

@parent_bp.route('/reading-mbti')
@login_required
@requires_role('parent', 'admin')
def reading_mbti():
    """독서 논술 MBTI - 자녀 선택"""
    from app.models.reading_mbti import ReadingMBTIResult

    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    # 각 자녀의 검사 이력 통계
    children_stats = []
    for child in children:
        results = ReadingMBTIResult.query.filter_by(
            student_id=child.student_id
        ).order_by(ReadingMBTIResult.created_at.desc()).all()

        latest_result = results[0] if results else None

        children_stats.append({
            'student': child,
            'total_tests': len(results),
            'latest_result': latest_result,
            'has_test': latest_result is not None
        })

    return render_template('parent/reading_mbti/index.html',
                           children_stats=children_stats)


@parent_bp.route('/reading-mbti/child/<student_id>')
@login_required
@requires_role('parent', 'admin')
def child_mbti(student_id):
    """자녀의 독서 논술 MBTI 결과"""
    from app.models.reading_mbti import ReadingMBTIResult

    student = Student.query.get_or_404(student_id)

    # 부모-자녀 관계 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation:
        flash('해당 학생의 정보를 조회할 권한이 없습니다.', 'error')
        return redirect(url_for('parent.reading_mbti'))

    # 검사 결과 조회
    results = ReadingMBTIResult.query.filter_by(
        student_id=student_id
    ).order_by(ReadingMBTIResult.created_at.desc()).all()

    latest_result = results[0] if results else None

    return render_template('parent/reading_mbti/child_detail.html',
                           student=student,
                           results=results,
                           latest_result=latest_result)


# ============================================================
# ACE 평가 조회 (ACE Evaluation)
# ============================================================

@parent_bp.route('/ace-evaluation')
@login_required
@requires_role('parent', 'admin')
def ace_evaluation():
    """ACE 분기 평가 - 자녀 선택"""
    from app.models.ace_evaluation import AceEvaluation, WeeklyEvaluation

    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    children = [pr.student for pr in parent_relations]

    # 각 자녀의 평가 통계
    children_stats = []
    for child in children:
        # ACE 분기 평가
        ace_evals = AceEvaluation.query.filter_by(
            student_id=child.student_id
        ).order_by(AceEvaluation.created_at.desc()).all()

        # 주차 평가
        weekly_evals = WeeklyEvaluation.query.filter_by(
            student_id=child.student_id
        ).order_by(WeeklyEvaluation.created_at.desc()).all()

        latest_ace = ace_evals[0] if ace_evals else None
        latest_weekly = weekly_evals[0] if weekly_evals else None

        children_stats.append({
            'student': child,
            'ace_count': len(ace_evals),
            'weekly_count': len(weekly_evals),
            'latest_ace': latest_ace,
            'latest_weekly': latest_weekly
        })

    return render_template('parent/ace_evaluation/index.html',
                           children_stats=children_stats)


@parent_bp.route('/ace-evaluation/child/<student_id>')
@login_required
@requires_role('parent', 'admin')
def child_ace_evaluation(student_id):
    """자녀의 ACE 평가 상세"""
    from app.models.ace_evaluation import AceEvaluation, WeeklyEvaluation, ACE_AXES

    student = Student.query.get_or_404(student_id)

    # 부모-자녀 관계 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation:
        flash('해당 학생의 정보를 조회할 권한이 없습니다.', 'error')
        return redirect(url_for('parent.ace_evaluation'))

    # 평가 결과 조회
    ace_evals = AceEvaluation.query.filter_by(
        student_id=student_id
    ).order_by(AceEvaluation.created_at.desc()).all()

    weekly_evals = WeeklyEvaluation.query.filter_by(
        student_id=student_id
    ).order_by(WeeklyEvaluation.created_at.desc()).all()

    latest_ace = ace_evals[0] if ace_evals else None

    return render_template('parent/ace_evaluation/child_detail.html',
                           student=student,
                           ace_evals=ace_evals,
                           weekly_evals=weekly_evals,
                           latest_ace=latest_ace,
                           ace_axes=ACE_AXES)


@parent_bp.route('/ace-evaluation/report/<student_id>')
@login_required
@requires_role('parent', 'admin')
def ace_report(student_id):
    """자녀 ACE 평가 리포트 (출력용)"""
    from app.models.ace_evaluation import WeeklyEvaluation, AceEvaluation, ACE_AXES

    student = Student.query.get_or_404(student_id)

    # 부모-자녀 관계 확인 (관리자는 모든 학생 접근 가능)
    if current_user.role != 'admin':
        relation = ParentStudent.query.filter_by(
            parent_id=current_user.user_id,
            student_id=student_id,
            is_active=True
        ).first()

        if not relation:
            flash('해당 학생의 정보를 조회할 권한이 없습니다.', 'error')
            return redirect(url_for('parent.ace_evaluation'))

    # 주차 평가 데이터
    weekly_evals = WeeklyEvaluation.query.filter_by(
        student_id=student_id
    ).order_by(WeeklyEvaluation.eval_date).all()

    # ACE 평가 데이터
    ace_evals = AceEvaluation.query.filter_by(
        student_id=student_id
    ).order_by(AceEvaluation.year, AceEvaluation.quarter).all()

    # 선택된 분기 (쿼리 파라미터로 전달 가능)
    selected_quarter_idx = request.args.get('quarter_idx', type=int)
    if selected_quarter_idx is None and ace_evals:
        selected_quarter_idx = len(ace_evals) - 1  # 최신 분기

    selected_ace = None
    if selected_quarter_idx is not None and 0 <= selected_quarter_idx < len(ace_evals):
        selected_ace = ace_evals[selected_quarter_idx]

    return render_template('teacher/ace_evaluation/report.html',
                         student=student,
                         weekly_evals=weekly_evals,
                         ace_evals=ace_evals,
                         selected_ace=selected_ace,
                         selected_quarter_idx=selected_quarter_idx,
                         ace_axes=ACE_AXES,
                         report_date=datetime.today())


# ============================================================
# 신규 등록 설문 (Registration Survey)
# ============================================================

@parent_bp.route('/registration-survey', methods=['GET', 'POST'])
@login_required
@requires_role('parent', 'admin')
def registration_survey():
    """신규 학생 등록 설문"""
    import uuid
    import json

    form = StudentRegistrationSurveyForm()

    if request.method == 'POST':
        # 체크박스 데이터 수동 수집
        preferred_genres = request.form.getlist('preferred_genres')
        personality_traits = request.form.getlist('personality_traits')
        education_info_needs = request.form.getlist('education_info_needs')
        academic_goals = request.form.getlist('academic_goals')
        career_interests = request.form.getlist('career_interests')

        # 필수 체크박스 검증
        if not personality_traits:
            flash('학생의 성향을 최소 1개 이상 선택해주세요.', 'error')
            return render_template('parent/registration_survey.html', form=form)

        if not education_info_needs:
            flash('필요한 교육&입시 정보를 최소 1개 이상 선택해주세요.', 'error')
            return render_template('parent/registration_survey.html', form=form)

        # 독서역량 텍스트를 숫자로 변환 (1-5)
        competency_map = {
            '독서역량 매우 부족': 1,
            '독서역량 부족': 2,
            '독서역량 보통': 3,
            '독서역량 우수': 4,
            '독서역량 매우 우수': 5
        }

        # 나머지 필드 검증
        if form.validate_on_submit():
            # ============================================
            # 🔍 STEP 1: 기존 학생 검색 (중복 방지)
            # ============================================
            matching_students = Student.query.filter(
                Student.name == form.student_name.data.strip(),
                Student.birth_date == form.student_birthdate.data
            ).all()

            # 매칭되는 학생이 있으면 확인 페이지로 이동
            if matching_students:
                # 폼 데이터를 JSON으로 저장
                form_data = {
                    'student_name': form.student_name.data.strip(),
                    'student_gender': form.student_gender.data,
                    'student_birthdate': form.student_birthdate.data.isoformat(),
                    'address': form.address.data.strip(),
                    'parent_contact': form.parent_contact.data.strip(),
                    'current_school': form.current_school.data.strip(),
                    'grade': form.grade.data,
                    'reading_experience': form.reading_experience.data,
                    'reading_competency': form.reading_competency.data,
                    'weekly_reading_amount': form.weekly_reading_amount.data,
                    'preferred_genres': preferred_genres,
                    'personality_traits': personality_traits,
                    'main_improvement_goal': form.main_improvement_goal.data,
                    'preferred_class_style': form.preferred_class_style.data,
                    'teacher_request': form.teacher_request.data if form.teacher_request.data else None,
                    'referral_source': form.referral_source.data,
                    'education_info_needs': education_info_needs,
                    'academic_goals': academic_goals,
                    'career_interests': career_interests,
                    'other_interests': form.other_interests.data if form.other_interests.data else None,
                    'sibling_info': form.sibling_info.data if form.sibling_info.data else None
                }

                return render_template('parent/registration_confirm.html',
                                     matching_students=matching_students,
                                     submitted_name=form.student_name.data.strip(),
                                     submitted_birthdate=form.student_birthdate.data,
                                     form_data_json=json.dumps(form_data, ensure_ascii=False))

            # ============================================
            # ✅ STEP 2: 새 학생 생성 (매칭 없음)
            # ============================================
            # 1. 기본 선생님 할당 (관리자 중 첫 번째 사용자)
            default_teacher = User.query.filter(User.role_level <= 2).first()
            if not default_teacher:
                flash('시스템 오류: 관리자를 찾을 수 없습니다. 관리자에게 문의하세요.', 'error')
                return render_template('parent/registration_survey.html', form=form)

            # 2. 학생 레코드 생성 (Student 모델의 실제 필드만 사용)
            new_student = Student(
                student_id=str(uuid.uuid4()),
                teacher_id=default_teacher.user_id,  # 필수 필드
                name=form.student_name.data.strip(),
                grade=form.grade.data,
                school=form.current_school.data.strip(),  # school 필드 사용
                birth_date=form.student_birthdate.data,
                phone=form.parent_contact.data.strip(),  # phone 필드 사용
                tier='B'  # 기본 등급
            )
            db.session.add(new_student)
            db.session.flush()  # student_id 생성

            # 3. 학생 프로필 생성 (설문 데이터만)
            reading_comp_value = competency_map.get(form.reading_competency.data, 3)  # 기본값 3 (보통)

            new_profile = StudentProfile(
                student_id=new_student.student_id,
                address=form.address.data.strip(),
                parent_contact=form.parent_contact.data.strip(),
                current_school=form.current_school.data.strip(),
                reading_experience=form.reading_experience.data,
                reading_competency=reading_comp_value,  # 1-5 숫자로 변환
                weekly_reading_amount=form.weekly_reading_amount.data,
                preferred_genres=json.dumps(preferred_genres) if preferred_genres else '[]',
                personality_traits=json.dumps(personality_traits) if personality_traits else '[]',
                main_improvement_goal=form.main_improvement_goal.data,
                preferred_class_style=form.preferred_class_style.data,
                teacher_request=form.teacher_request.data.strip() if form.teacher_request.data else None,
                referral_source=form.referral_source.data,
                education_info_needs=json.dumps(education_info_needs) if education_info_needs else '[]',
                academic_goals=json.dumps(academic_goals) if academic_goals else '[]',
                career_interests=json.dumps(career_interests) if career_interests else '[]',
                other_interests=form.other_interests.data.strip() if form.other_interests.data else None,
                sibling_info=form.sibling_info.data.strip() if form.sibling_info.data else None,
                created_by=current_user.user_id
            )
            db.session.add(new_profile)

            # 4. 학부모-학생 연결 (자동 연결)
            parent_link = ParentStudent(
                parent_id=current_user.user_id,
                student_id=new_student.student_id,
                is_active=True
            )
            db.session.add(parent_link)

            # 5. 관리자에게 알림
            admin_users = User.query.filter(User.role_level <= 2).all()  # admin, manager
            for admin in admin_users:
                notification = Notification(
                    user_id=admin.user_id,
                    notification_type='new_registration',
                    title='신규 학생 등록',
                    message=f'{current_user.name} 학부모가 신규 학생({form.student_name.data})을 등록했습니다.',
                    link_url=url_for('admin.student_profiles')
                )
                db.session.add(notification)

            db.session.commit()

            flash(f'{form.student_name.data} 학생이 성공적으로 등록되었습니다!', 'success')
            return redirect(url_for('parent.registration_complete', student_id=new_student.student_id))

    return render_template('parent/registration_survey.html', form=form)


@parent_bp.route('/registration-complete/<student_id>')
@login_required
@requires_role('parent', 'admin')
def registration_complete(student_id):
    """등록 완료 페이지"""
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (이 학생의 학부모인지)
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    return render_template('parent/registration_complete.html', student=student)


@parent_bp.route('/registration-link-existing', methods=['POST'])
@login_required
@requires_role('parent', 'admin')
def registration_link_existing():
    """기존 학생에 학부모 연결"""
    import json

    student_id = request.form.get('student_id')
    form_data_json = request.form.get('form_data')

    if not student_id:
        flash('학생 정보가 없습니다.', 'error')
        return redirect(url_for('parent.registration_survey'))

    student = Student.query.get_or_404(student_id)

    # 이미 연결되어 있는지 확인
    existing_link = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id
    ).first()

    if existing_link:
        if existing_link.is_active:
            flash(f'{student.name} 학생은 이미 연결되어 있습니다.', 'warning')
        else:
            # 비활성화된 연결을 다시 활성화
            existing_link.is_active = True
            db.session.commit()
            flash(f'{student.name} 학생과 다시 연결되었습니다.', 'success')
    else:
        # 새로운 연결 생성
        parent_link = ParentStudent(
            parent_id=current_user.user_id,
            student_id=student_id,
            is_active=True
        )
        db.session.add(parent_link)

        # 관리자에게 알림
        admin_users = User.query.filter(User.role_level <= 2).all()
        for admin in admin_users:
            notification = Notification(
                user_id=admin.user_id,
                notification_type='parent_link',
                title='학부모-학생 연결',
                message=f'{current_user.name} 학부모가 기존 학생({student.name})과 연결되었습니다.',
                link_url=url_for('admin.students')
            )
            db.session.add(notification)

        db.session.commit()
        flash(f'{student.name} 학생과 성공적으로 연결되었습니다!', 'success')

    return redirect(url_for('parent.child_detail', student_id=student_id))


@parent_bp.route('/registration-create-new', methods=['POST'])
@login_required
@requires_role('parent', 'admin')
def registration_create_new():
    """새 학생 강제 생성 (동명이인)"""
    import uuid
    import json
    from datetime import datetime

    form_data_json = request.form.get('form_data')
    force_create = request.form.get('force_create')

    if not form_data_json or force_create != 'true':
        flash('잘못된 요청입니다.', 'error')
        return redirect(url_for('parent.registration_survey'))

    # JSON 데이터 파싱
    try:
        form_data = json.loads(form_data_json)
    except:
        flash('데이터 파싱 오류가 발생했습니다.', 'error')
        return redirect(url_for('parent.registration_survey'))

    # 독서역량 변환
    competency_map = {
        '독서역량 매우 부족': 1,
        '독서역량 부족': 2,
        '독서역량 보통': 3,
        '독서역량 우수': 4,
        '독서역량 매우 우수': 5
    }

    # 1. 기본 선생님 할당
    default_teacher = User.query.filter(User.role_level <= 2).first()
    if not default_teacher:
        flash('시스템 오류: 관리자를 찾을 수 없습니다.', 'error')
        return redirect(url_for('parent.registration_survey'))

    # 2. 학생 생성
    new_student = Student(
        student_id=str(uuid.uuid4()),
        teacher_id=default_teacher.user_id,
        name=form_data['student_name'],
        grade=form_data['grade'],
        school=form_data['current_school'],
        birth_date=datetime.fromisoformat(form_data['student_birthdate']).date(),
        phone=form_data['parent_contact'],
        tier='B'
    )
    db.session.add(new_student)
    db.session.flush()

    # 3. 프로필 생성
    reading_comp_value = competency_map.get(form_data['reading_competency'], 3)

    new_profile = StudentProfile(
        student_id=new_student.student_id,
        address=form_data['address'],
        parent_contact=form_data['parent_contact'],
        current_school=form_data['current_school'],
        reading_experience=form_data['reading_experience'],
        reading_competency=reading_comp_value,
        weekly_reading_amount=form_data['weekly_reading_amount'],
        preferred_genres=json.dumps(form_data['preferred_genres']) if form_data.get('preferred_genres') else '[]',
        personality_traits=json.dumps(form_data['personality_traits']) if form_data.get('personality_traits') else '[]',
        main_improvement_goal=form_data['main_improvement_goal'],
        preferred_class_style=form_data['preferred_class_style'],
        teacher_request=form_data.get('teacher_request'),
        referral_source=form_data['referral_source'],
        education_info_needs=json.dumps(form_data['education_info_needs']) if form_data.get('education_info_needs') else '[]',
        academic_goals=json.dumps(form_data['academic_goals']) if form_data.get('academic_goals') else '[]',
        career_interests=json.dumps(form_data['career_interests']) if form_data.get('career_interests') else '[]',
        other_interests=form_data.get('other_interests'),
        sibling_info=form_data.get('sibling_info'),
        created_by=current_user.user_id
    )
    db.session.add(new_profile)

    # 4. 학부모-학생 연결
    parent_link = ParentStudent(
        parent_id=current_user.user_id,
        student_id=new_student.student_id,
        is_active=True
    )
    db.session.add(parent_link)

    # 5. 관리자에게 알림
    admin_users = User.query.filter(User.role_level <= 2).all()
    for admin in admin_users:
        notification = Notification(
            user_id=admin.user_id,
            notification_type='new_registration',
            title='신규 학생 등록 (동명이인)',
            message=f'{current_user.name} 학부모가 신규 학생({form_data["student_name"]})을 등록했습니다.',
            link_url=url_for('admin.student_profiles')
        )
        db.session.add(notification)

    db.session.commit()

    flash(f'{form_data["student_name"]} 학생이 성공적으로 등록되었습니다! (동명이인)', 'success')
    return redirect(url_for('parent.registration_complete', student_id=new_student.student_id))


# ==================== 상담 기록 조회 ====================

@parent_bp.route('/consultations')
@login_required
@requires_role('parent', 'admin')
def consultations_index():
    """상담 기록 - 자녀 선택"""
    # 내 자녀 목록
    parent_relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        is_active=True
    ).all()

    # 각 자녀의 정보와 상담 통계를 함께 저장
    children = []
    for pr in parent_relations:
        # 해당 자녀의 공유된 상담 기록 수
        shared_count = ConsultationRecord.query.filter_by(
            student_id=pr.student.student_id,
            share_with_parents=True
        ).count()

        # 최근 상담일
        latest_consultation = ConsultationRecord.query.filter_by(
            student_id=pr.student.student_id,
            share_with_parents=True
        ).order_by(ConsultationRecord.consultation_date.desc()).first()

        child_data = {
            'student': pr.student,
            'student_id': pr.student.student_id,
            'name': pr.student.name,
            'grade': pr.student.grade,
            'consultation_count': shared_count,
            'latest_date': latest_consultation.consultation_date if latest_consultation else None
        }
        children.append(child_data)

    return render_template('parent/consultations_index.html',
                         children=children)


@parent_bp.route('/consultations/<student_id>')
@login_required
@requires_role('parent', 'admin')
def consultations(student_id):
    """자녀의 상담 기록 목록"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    student = Student.query.get_or_404(student_id)

    # 검색 및 필터
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    # 이 자녀에 대한 공유된 상담 기록만 조회
    query = ConsultationRecord.query.filter_by(
        student_id=student_id,
        share_with_parents=True
    )

    if search:
        query = query.filter(ConsultationRecord.title.contains(search))

    if category:
        query = query.filter_by(major_category=category)

    consultations = query.order_by(ConsultationRecord.consultation_date.desc()).all()

    return render_template('parent/consultations.html',
                         student=student,
                         consultations=consultations,
                         search=search,
                         category=category)


@parent_bp.route('/consultations/<student_id>/<int:consultation_id>')
@login_required
@requires_role('parent', 'admin')
def view_consultation(student_id, consultation_id):
    """자녀의 상담 기록 상세 보기"""
    # 권한 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('parent.index'))

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    # 자녀와 매칭되는지, 공유되었는지 확인
    if consultation.student_id != int(student_id):
        flash('잘못된 접근입니다.', 'error')
        return redirect(url_for('parent.consultations_index'))

    if not consultation.share_with_parents and current_user.role != 'admin':
        flash('공유되지 않은 상담 기록입니다.', 'error')
        return redirect(url_for('parent.consultations', student_id=student_id))

    student = Student.query.get_or_404(student_id)

    return render_template('parent/consultation_detail.html',
                         student=student,
                         consultation=consultation)


@parent_bp.route('/weekly-evaluation')
@login_required
@requires_role('parent', 'admin')
def weekly_evaluation():
    """주간평가 자녀 선택 페이지"""
    from app.models.ace_evaluation import WeeklyEvaluation

    # 내 자녀 목록
    children = Student.query.join(ParentStudent).filter(
        ParentStudent.parent_id == current_user.user_id,
        ParentStudent.is_active == True
    ).all()

    # 각 자녀별 주간평가 통계
    children_stats = []
    for child in children:
        weekly_evals = WeeklyEvaluation.query.filter_by(student_id=child.student_id).all()

        if weekly_evals:
            avg_score = round(sum(e.score for e in weekly_evals) / len(weekly_evals), 1)
            avg_participation = round(sum(e.participation_score for e in weekly_evals) / len(weekly_evals), 1)
            avg_understanding = round(sum(e.understanding_score for e in weekly_evals) / len(weekly_evals), 1)
        else:
            avg_score = 0
            avg_participation = 0
            avg_understanding = 0

        children_stats.append({
            'student': child,
            'eval_count': len(weekly_evals),
            'avg_score': avg_score,
            'avg_participation': avg_participation,
            'avg_understanding': avg_understanding
        })

    return render_template('parent/weekly_evaluation/index.html',
                         children_stats=children_stats)


@parent_bp.route('/weekly-evaluation/<student_id>')
@login_required
@requires_role('parent', 'admin')
def weekly_evaluation_report(student_id):
    """자녀 주간평가 리포트"""
    from app.models.ace_evaluation import WeeklyEvaluation
    from datetime import date, timedelta
    from sqlalchemy import func

    # 자녀 확인
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id,
        is_active=True
    ).first()

    if not relation and current_user.role != 'admin':
        flash('해당 자녀의 정보를 조회할 권한이 없습니다.', 'error')
        return redirect(url_for('parent.weekly_evaluation'))

    student = Student.query.get_or_404(student_id)

    # 기간 필터링
    period = request.args.get('period', 'all')

    query = WeeklyEvaluation.query.filter_by(student_id=student_id)

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

    return render_template('parent/weekly_evaluation/report.html',
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
