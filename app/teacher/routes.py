# -*- coding: utf-8 -*-
"""강사 라우트"""
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime

from app.teacher import teacher_bp
from app.teacher.forms import TeacherFeedbackForm, SessionNoteForm
from app.models import (db, Course, CourseSession, Attendance, Student,
                       TeacherFeedback, User, ParentStudent, CourseEnrollment)
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.material import Material, MaterialDownload
from app.models import Notification
from app.models.student_caution import StudentCaution, CATEGORY_LABELS, SEVERITY_META
from app.models.session_adjustment import SessionAdjustment
from app.models.announcement import Announcement, AnnouncementRead
from app.models.class_board import ClassBoardPost, ClassBoardComment
from app.utils.decorators import requires_role
from app.utils.course_utils import update_enrollment_attendance_stats, get_course_statistics


def _send_feedback_email(parent, feedback):
    """피드백 이메일 발송. (성공여부, 사유) 튜플 반환"""
    from flask import current_app
    if not parent.email:
        return False, '학부모 이메일 미등록'
    if not current_app.config.get('MAIL_SERVER'):
        return False, '이메일 서버 미설정'
    try:
        from app.extensions import mail
        from flask_mail import Message
        content_preview = feedback.content[:300] + ('...' if len(feedback.content) > 300 else '')
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:'Noto Sans KR',Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f0f2f5;">
            <div style="background:linear-gradient(135deg,#1A2744,#1E3A5F);padding:30px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="color:white;margin:0;font-size:24px;">📚 모모의 책장</h1>
                <p style="color:rgba(255,255,255,0.7);margin:8px 0 0;font-size:13px;">MOMOAI v4.0 - 선생님 피드백</p>
            </div>
            <div style="background:white;padding:40px 30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                <h2 style="color:#1A2744;margin-top:0;">📬 피드백이 도착했습니다</h2>
                <p style="color:#475569;">안녕하세요, <strong>{parent.name}</strong>님!</p>
                <p style="color:#475569;">선생님으로부터 피드백이 전달되었습니다.</p>
                <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:20px;margin:20px 0;">
                    <p style="color:#64748B;font-size:13px;margin:0 0 8px;"><strong>제목:</strong> {feedback.title}</p>
                    <p style="color:#64748B;font-size:13px;margin:0 0 8px;"><strong>유형:</strong> {feedback.feedback_type}</p>
                    <hr style="border:none;border-top:1px solid #E2E8F0;margin:12px 0;">
                    <p style="color:#334155;font-size:14px;margin:0;white-space:pre-wrap;">{content_preview}</p>
                </div>
                <p style="color:#94A3B8;font-size:12px;text-align:center;margin:20px 0 0;">© 2026 MOMOAI - 모모의 책장. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        msg = Message(
            subject=f'[MOMOAI] 피드백: {feedback.title}',
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@momoai.kr'),
            recipients=[parent.email],
            html=html_body
        )
        mail.send(msg)
        return True, '발송 완료'
    except Exception as e:
        current_app.logger.error(f'피드백 이메일 발송 실패 ({parent.email}): {e}')
        return False, '전송 중 오류 발생'


def _send_feedback_sms(parent, feedback):
    """피드백 SMS 발송. (성공여부, 사유) 튜플 반환"""
    if not parent.phone:
        return False, '학부모 휴대폰 번호 미등록'
    from app.utils.sms import send_sms_message
    content_short = feedback.content[:60] + ('...' if len(feedback.content) > 60 else '')
    message = f"[MOMOAI 피드백]\n{feedback.title}\n\n{content_short}"
    return send_sms_message(parent.phone, message, title='MOMOAI 피드백')


@teacher_bp.route('/')
@login_required
@requires_role('teacher', 'admin')
def index():
    """강사 대시보드"""
    from sqlalchemy import func, extract, case
    from datetime import timedelta
    from app.models.essay import Essay
    import json

    # 내가 담당하는 수업 목록
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active')\
        .order_by(Course.start_date.desc()).all()

    # 오늘 수업
    today = datetime.utcnow().date()
    today_sessions = []
    for course in my_courses:
        sessions = CourseSession.query.filter_by(
            course_id=course.course_id,
            session_date=today
        ).all()
        today_sessions.extend(sessions)

    # 출석 체크 필요한 세션 (완료되었지만 출석 미체크)
    pending_attendance = CourseSession.query.join(Course).filter(
        Course.teacher_id == current_user.user_id,
        CourseSession.status == 'completed',
        CourseSession.attendance_checked == False
    ).order_by(CourseSession.session_date.desc()).limit(5).all()

    # 통계
    total_students = sum(c.enrolled_count for c in my_courses)
    total_sessions = sum(c.total_sessions for c in my_courses)

    # 차트 데이터: 내 수업별 수강생 수
    my_course_ids = [c.course_id for c in my_courses]
    course_enrollments = db.session.query(
        Course.course_name,
        func.count(CourseEnrollment.enrollment_id).label('count')
    ).join(CourseEnrollment, Course.course_id == CourseEnrollment.course_id)\
     .filter(
         Course.course_id.in_(my_course_ids),
         CourseEnrollment.status == 'active'
     ).group_by(Course.course_id, Course.course_name)\
     .order_by(func.count(CourseEnrollment.enrollment_id).desc()).all()

    course_labels = [row.course_name for row in course_enrollments]
    course_data = [row.count for row in course_enrollments]

    # 차트 데이터: 월별 첨삭 수 (내가 담당한 학생들)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    # 내 수업 학생들의 student_id 목록
    my_student_ids = []
    for course in my_courses:
        enrollments = CourseEnrollment.query.filter_by(course_id=course.course_id, status='active').all()
        my_student_ids.extend([e.student_id for e in enrollments])
    my_student_ids = list(set(my_student_ids))

    monthly_essays = db.session.query(
        extract('year', Essay.created_at).label('year'),
        extract('month', Essay.created_at).label('month'),
        func.count(Essay.essay_id).label('count')
    ).filter(
        Essay.created_at >= six_months_ago,
        Essay.student_id.in_(my_student_ids) if my_student_ids else False
    ).group_by('year', 'month')\
     .order_by('year', 'month').all()

    essay_labels = [f"{int(row.year)}-{int(row.month):02d}" for row in monthly_essays]
    essay_data = [row.count for row in monthly_essays]

    # 추가 차트 데이터 1: 월별 평균 출석률 추이 (내 수업 기준)
    monthly_attendance = db.session.query(
        extract('year', CourseSession.session_date).label('year'),
        extract('month', CourseSession.session_date).label('month'),
        func.count(Attendance.attendance_id).label('total_records'),
        func.sum(case((Attendance.status == 'present', 1), else_=0)).label('present_count')
    ).join(Attendance, CourseSession.session_id == Attendance.session_id)\
     .join(Course, CourseSession.course_id == Course.course_id)\
     .filter(
         Course.teacher_id == current_user.user_id,
         CourseSession.session_date >= six_months_ago
     ).group_by('year', 'month')\
     .order_by('year', 'month').all()

    attendance_labels = [f"{int(row.year)}-{int(row.month):02d}" for row in monthly_attendance]
    attendance_data = [
        round((row.present_count / row.total_records * 100), 1) if row.total_records > 0 else 0
        for row in monthly_attendance
    ]

    # 추가 차트 데이터 2: 학생별 출석률 Top 10
    student_attendance = db.session.query(
        Student.name,
        func.count(Attendance.attendance_id).label('total_sessions'),
        func.sum(case((Attendance.status == 'present', 1), else_=0)).label('present_count')
    ).join(CourseEnrollment, Student.student_id == CourseEnrollment.student_id)\
     .join(Attendance, CourseEnrollment.enrollment_id == Attendance.enrollment_id)\
     .join(CourseSession, Attendance.session_id == CourseSession.session_id)\
     .join(Course, CourseSession.course_id == Course.course_id)\
     .filter(Course.teacher_id == current_user.user_id)\
     .group_by(Student.student_id, Student.name)\
     .order_by(func.sum(case((Attendance.status == 'present', 1), else_=0)).desc())\
     .limit(10).all()

    student_names = []
    student_attendance_rates = []
    for row in student_attendance:
        if row.total_sessions > 0:
            rate = round((row.present_count / row.total_sessions * 100), 1)
            student_names.append(row.name)
            student_attendance_rates.append(rate)

    # 미해결 주의사항 학생 (내 담당 학생 중)
    active_caution_students = []
    if my_student_ids:
        from sqlalchemy import distinct
        caution_student_ids = db.session.query(distinct(StudentCaution.student_id)).filter(
            StudentCaution.student_id.in_(my_student_ids),
            StudentCaution.is_resolved == False
        ).all()
        caution_student_ids = [r[0] for r in caution_student_ids]
        for sid in caution_student_ids:
            st = Student.query.get(sid)
            if st:
                worst = StudentCaution.query.filter_by(student_id=sid, is_resolved=False)                    .order_by(db.case({'danger':0,'warning':1,'caution':2}, value=StudentCaution.severity)).first()
                active_caution_students.append({'student': st, 'worst': worst})

    return render_template('teacher/index.html',
                         my_courses=my_courses,
                         today_sessions=today_sessions,
                         pending_attendance=pending_attendance,
                         total_students=total_students,
                         total_sessions=total_sessions,
                         course_labels=json.dumps(course_labels),
                         course_data=json.dumps(course_data),
                         essay_labels=json.dumps(essay_labels),
                         essay_data=json.dumps(essay_data),
                         attendance_labels=json.dumps(attendance_labels),
                         attendance_data=json.dumps(attendance_data),
                         student_names=json.dumps(student_names),
                         student_attendance_rates=json.dumps(student_attendance_rates),
                         active_caution_students=active_caution_students)


@teacher_bp.route('/courses')
@login_required
@requires_role('teacher', 'admin')
def courses():
    """내 수업 목록"""
    # 필터
    status_filter = request.args.get('status', '').strip()

    query = Course.query.filter_by(teacher_id=current_user.user_id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    courses = query.order_by(Course.created_at.desc()).all()

    return render_template('teacher/courses.html',
                         courses=courses,
                         status_filter=status_filter)


@teacher_bp.route('/schedule')
@login_required
@requires_role('teacher', 'admin')
def schedule():
    """주간 시간표"""
    from datetime import timedelta

    # 현재 주의 월요일 찾기
    today = datetime.utcnow().date()
    weekday = today.weekday()  # 0=월요일, 6=일요일
    week_start = today - timedelta(days=weekday)  # 이번 주 월요일
    week_end = week_start + timedelta(days=6)  # 이번 주 일요일

    # 주간 이동 (쿼리 파라미터)
    week_offset = int(request.args.get('week', 0))
    week_start = week_start + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=6)

    # 내가 담당하는 수업의 세션 조회
    my_courses = Course.query.filter_by(
        teacher_id=current_user.user_id,
        status='active'
    ).all()
    my_course_ids = [c.course_id for c in my_courses]

    # 해당 주의 모든 세션
    sessions = CourseSession.query.filter(
        CourseSession.course_id.in_(my_course_ids),
        CourseSession.session_date >= week_start,
        CourseSession.session_date <= week_end
    ).order_by(CourseSession.session_date, CourseSession.start_time).all()

    # 요일별로 그룹화
    weekly_schedule = {i: [] for i in range(7)}  # 0=월요일 ~ 6=일요일
    for session in sessions:
        day_index = session.session_date.weekday()
        weekly_schedule[day_index].append(session)

    # 시간대 범위 (8:00 ~ 22:00)
    time_slots = []
    for hour in range(8, 22):
        time_slots.append(f"{hour:02d}:00")

    return render_template('teacher/schedule.html',
                         week_start=week_start,
                         week_end=week_end,
                         week_offset=week_offset,
                         weekly_schedule=weekly_schedule,
                         time_slots=time_slots,
                         today=today,
                         timedelta=timedelta)


@teacher_bp.route('/courses/<course_id>')
@login_required
@requires_role('teacher', 'admin')
def course_detail(course_id):
    """수업 상세"""
    course = Course.query.get_or_404(course_id)

    # 권한 확인 (본인이 담당하는 수업만)
    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.courses'))

    # 통계
    stats = get_course_statistics(course_id)

    # 수강생 목록
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()

    # 최근 세션 (최근 5개)
    recent_sessions = CourseSession.query.filter_by(course_id=course_id)\
        .order_by(CourseSession.session_date.desc()).limit(5).all()

    # 다음 예정 세션
    today = datetime.utcnow().date()
    upcoming_sessions = CourseSession.query.filter_by(course_id=course_id, status='scheduled')\
        .filter(CourseSession.session_date >= today)\
        .order_by(CourseSession.session_date.asc()).limit(3).all()

    return render_template('teacher/course_detail.html',
                         course=course,
                         stats=stats,
                         enrollments=enrollments,
                         recent_sessions=recent_sessions,
                         upcoming_sessions=upcoming_sessions)


@teacher_bp.route('/courses/<course_id>/sessions')
@login_required
@requires_role('teacher', 'admin')
def course_sessions(course_id):
    """수업 세션 목록"""
    course = Course.query.get_or_404(course_id)

    # 권한 확인
    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.courses'))

    sessions = CourseSession.query.filter_by(course_id=course_id)\
        .order_by(CourseSession.session_number.asc()).all()

    return render_template('teacher/course_sessions.html',
                         course=course,
                         sessions=sessions)


@teacher_bp.route('/attendance')
@login_required
@requires_role('teacher', 'admin')
def attendance_list():
    """출석 체크할 세션 목록"""
    from datetime import timedelta

    # 필터 파라미터
    search_mode = request.args.get('search', '').strip()
    course_filter = request.args.get('course_id', '').strip()
    teacher_filter = request.args.get('teacher_id', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    status_filter = request.args.get('status', '').strip()

    # 강사의 수업 조회 (관리자는 전체 또는 선택한 강사)
    if current_user.is_admin:
        if teacher_filter:
            courses = Course.query.filter_by(
                teacher_id=teacher_filter,
                status='active'
            ).order_by(Course.course_name).all()
        else:
            courses = Course.query.filter_by(status='active').order_by(Course.course_name).all()
    else:
        courses = Course.query.filter_by(
            teacher_id=current_user.user_id,
            status='active'
        ).order_by(Course.course_name).all()

    course_ids = [c.course_id for c in courses]

    # 보강수업 / 일반수업 분리
    makeup_course_ids = [c.course_id for c in courses if c.course_type == '보강수업']
    regular_course_ids = [c.course_id for c in courses if c.course_type != '보강수업']

    # 강사 목록 로드 (관리자만)
    teachers = []
    if current_user.is_admin:
        teachers = User.query.filter_by(role='teacher', is_active=True).order_by(User.name).all()

    # 오늘 날짜
    today = datetime.utcnow().date()

    if not course_ids:
        return render_template('teacher/attendance_list.html',
                             courses=courses,
                             teachers=teachers,
                             today=today,
                             past_sessions=[],
                             attendance_map={},
                             makeup_sessions=[],
                             course_filter=course_filter,
                             teacher_filter=teacher_filter,
                             date_from=date_from,
                             date_to=date_to)

    # 보강수업 세션 (과거 30일 ~ 미래 90일, 날짜순)
    makeup_sessions = []
    if makeup_course_ids:
        makeup_sessions = CourseSession.query.filter(
            CourseSession.course_id.in_(makeup_course_ids),
            CourseSession.session_date >= today - timedelta(days=30),
            CourseSession.session_date <= today + timedelta(days=90)
        ).order_by(CourseSession.session_date, CourseSession.start_time).all()

    # 오늘 포함 과거 세션 전체, 최신순 (limit 100)
    past_query = CourseSession.query.filter(
        CourseSession.course_id.in_(regular_course_ids),
        CourseSession.session_date <= today
    )

    # 필터 적용
    if course_filter:
        past_query = past_query.filter(CourseSession.course_id == course_filter)
    if date_from:
        past_query = past_query.filter(CourseSession.session_date >= date_from)
    if date_to:
        past_query = past_query.filter(CourseSession.session_date <= date_to)

    past_sessions = past_query.order_by(
        CourseSession.session_date.desc(),
        CourseSession.start_time.desc()
    ).limit(100).all() if regular_course_ids else []

    # 각 세션의 출결 레코드를 딕셔너리로 미리 로드 {session_id: [attendance, ...]}
    from collections import defaultdict
    attendance_map = defaultdict(list)
    essay_map = {}    # {(session_id, student_id): essay}
    result_map = {}   # {essay_id: EssayResult}

    if past_sessions:
        session_ids = [s.session_id for s in past_sessions]
        all_attendances = Attendance.query.filter(
            Attendance.session_id.in_(session_ids)
        ).join(Student).order_by(Student.name).all()
        for a in all_attendances:
            attendance_map[a.session_id].append(a)

        # 학부모 전화번호 맵 {attendance_id: [phones]}
        parent_phones = {}
        for a in all_attendances:
            parents = ParentStudent.query.filter_by(student_id=a.student.student_id, is_active=True).all()
            phones = [ps.parent.phone for ps in parents if ps.parent and ps.parent.phone]
            if phones:
                parent_phones[str(a.attendance_id)] = phones

        # 해당 세션에 배정된 글쓰기와 점수 로드 (컬럼 없으면 무시)
        try:
            from app.models.essay import Essay, EssayResult
            essays_in_sessions = Essay.query.filter(
                Essay.session_id.in_(session_ids)
            ).all()
            for e in essays_in_sessions:
                essay_map[(e.session_id, e.student_id)] = e

            essay_ids = [e.essay_id for e in essays_in_sessions]
            if essay_ids:
                results = EssayResult.query.filter(
                    EssayResult.essay_id.in_(essay_ids)
                ).all()
                result_map = {r.essay_id: r for r in results}
        except Exception:
            pass  # DB 컬럼 미생성 시 essay 데이터 없이 진행

    return render_template('teacher/attendance_list.html',
                         courses=courses,
                         teachers=teachers,
                         today=today,
                         past_sessions=past_sessions,
                         attendance_map=attendance_map,
                         essay_map=essay_map,
                         result_map=result_map,
                         makeup_sessions=makeup_sessions,
                         course_filter=course_filter,
                         teacher_filter=teacher_filter,
                         date_from=date_from,
                         date_to=date_to,
                         parent_phones=parent_phones if past_sessions else {})


@teacher_bp.route('/sessions/<session_id>/attendance')
@login_required
@requires_role('teacher', 'admin')
def check_attendance(session_id):
    """출석 체크"""
    session = CourseSession.query.get_or_404(session_id)
    course = session.course

    # 권한 확인
    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.courses'))

    # 출석 레코드 조회
    attendance_records = Attendance.query.filter_by(session_id=session_id)\
        .join(Student)\
        .order_by(Student.name.asc()).all()

    # 세션 메모 폼
    note_form = SessionNoteForm(obj=session)

    # 학생별 학부모 전화번호 맵
    parent_phones = {}
    for att in attendance_records:
        sid = att.student.student_id
        parents = ParentStudent.query.filter_by(student_id=sid, is_active=True).all()
        phones = [ps.parent.phone for ps in parents if ps.parent and ps.parent.phone]
        if phones:
            parent_phones[str(att.attendance_id)] = phones

    return render_template('teacher/check_attendance.html',
                         session=session,
                         course=course,
                         attendance_records=attendance_records,
                         note_form=note_form,
                         parent_phones=parent_phones)


@teacher_bp.route('/api/attendance/<attendance_id>', methods=['PATCH'])
@login_required
@requires_role('teacher', 'admin')
def update_attendance(attendance_id):
    """출석 상태 업데이트 API"""
    attendance = Attendance.query.get_or_404(attendance_id)
    session = attendance.session
    course = session.course

    # 권한 확인
    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json
    new_status = data.get('status')
    notes = data.get('notes')  # None이면 기존 notes 유지
    participation_score = data.get('participation_score')
    comprehension_score = data.get('comprehension_score')

    # status는 선택적 — 없으면 기존 값 유지
    if new_status is not None:
        if new_status not in ['present', 'absent', 'late', 'excused']:
            return jsonify({'success': False, 'message': '잘못된 상태값입니다.'}), 400
        attendance.status = new_status

    if notes is not None:
        attendance.notes = notes
    if participation_score is not None:
        attendance.participation_score = int(participation_score)
    if comprehension_score is not None:
        attendance.comprehension_score = int(comprehension_score)

    # 점수나 상태 변경이 있을 때만 checked_at 업데이트
    if new_status is not None or participation_score is not None or comprehension_score is not None:
        attendance.checked_at = datetime.utcnow()
        attendance.checked_by = current_user.user_id

    db.session.commit()

    # 출석 통계 업데이트
    update_enrollment_attendance_stats(attendance.enrollment_id)
    db.session.commit()

    # 결석/지각 즉시 알림 → 학부모 Push
    if new_status in ('absent', 'late'):
        try:
            from app.models.notification import Notification
            from app.utils.push_utils import send_push_to_user
            student = attendance.student
            status_label = '결석' if new_status == 'absent' else '지각'
            date_str = session.session_date.strftime('%m/%d')
            msg = f'{date_str} {course.course_name} 수업에 {status_label} 처리되었습니다.'
            parents = ParentStudent.query.filter_by(
                student_id=student.student_id, is_active=True
            ).all()
            for ps in parents:
                db.session.add(Notification(
                    user_id=ps.parent_id,
                    notification_type='attendance_absent',
                    title=f'{student.name} 학생 {status_label} 알림',
                    message=msg,
                    link_url='/parent/attendance'
                ))
                send_push_to_user(
                    user_id=ps.parent_id,
                    title=f'{student.name} 학생 {status_label} 알림',
                    body=msg,
                    url='/parent/attendance'
                )
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(f'[Push] 결석 알림 오류: {e}')

    return jsonify({
        'success': True,
        'attendance_id': attendance_id,
        'status': attendance.status
    })


@teacher_bp.route('/api/attendance/<attendance_id>/excused', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def mark_excused(attendance_id):
    """인정결석 처리 + SessionAdjustment 생성"""
    from flask import jsonify, request

    attendance = Attendance.query.get(attendance_id)
    if not attendance:
        return jsonify({'success': False, 'message': '출석 기록을 찾을 수 없습니다.'}), 404

    # 이미 인정결석이고 조정 레코드도 생성된 경우 중복 방지
    if attendance.status == 'excused' and attendance.adjustment_created:
        return jsonify({'success': True, 'message': '이미 인정결석 처리되었습니다.'})

    data = request.get_json() or {}
    reason = data.get('reason', '').strip()

    # 출석 상태 업데이트
    attendance.status = 'excused'

    # SessionAdjustment 생성 (관리자 분류 대기)
    if not attendance.adjustment_created:
        adjustment = SessionAdjustment(
            student_id=attendance.student_id,
            enrollment_id=attendance.enrollment_id,
            attendance_id=attendance_id,
            adjustment_type=None,         # 관리자가 이월/무료수업 분류 예정
            sessions_count=1,
            reason=reason or None,
            source='teacher_excused',
            status='pending_review',
            created_by=current_user.user_id
        )
        db.session.add(adjustment)
        attendance.adjustment_created = True

    db.session.commit()
    return jsonify({'success': True, 'message': '인정결석으로 처리되었습니다.'})


@teacher_bp.route('/api/attendance/<attendance_id>/send-late-sms', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def send_late_sms(attendance_id):
    """지각 처리 시 학부모 SMS 발송"""
    from app.utils.sms import send_sms_message
    from app.models.message import Message, MessageRecipient
    import uuid as _uuid

    attendance = Attendance.query.get_or_404(attendance_id)
    session_obj = attendance.session
    course = session_obj.course
    student = attendance.student

    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    parents = ParentStudent.query.filter_by(student_id=student.student_id, is_active=True).all()
    parent_users = [ps.parent for ps in parents if ps.parent and ps.parent.phone]

    if not parent_users:
        return jsonify({'success': False, 'message': '등록된 학부모 전화번호가 없습니다.'})

    date_str = session_obj.session_date.strftime('%Y년 %m월 %d일')
    time_str = session_obj.start_time.strftime('%H:%M') if session_obj.start_time else ''
    msg = (
        f'[MOMOAI] {student.name} 학생 지각 안내\n'
        f'{date_str} {time_str} {course.course_name} 수업에\n'
        f'학생이 참여하지 않고 있어 확인을 부탁드립니다.\n'
        f'문의: {current_user.name} 강사'
    )

    sent, failed = [], []
    for parent in parent_users:
        ok, reason = send_sms_message(parent.phone, msg)
        if ok:
            sent.append(parent.name)
        else:
            failed.append(f'{parent.name}({reason})')

    # 발송 이력 저장
    if sent:
        try:
            log_msg = Message(
                message_id=str(_uuid.uuid4()),
                sender_id=current_user.user_id,
                content=msg,
                message_type='SMS',
                total_recipients=len(sent)
            )
            db.session.add(log_msg)
            for parent in parent_users:
                if parent.name in sent:
                    db.session.add(MessageRecipient(
                        message_id=log_msg.message_id,
                        recipient_id=parent.user_id,
                        phone_number=parent.phone
                    ))
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(f'SMS 이력 저장 오류: {e}')

    result_msg = f'{len(sent)}명 발송 완료'
    if failed:
        result_msg += f', 실패: {", ".join(failed)}'

    return jsonify({'success': True, 'message': result_msg, 'sent': sent, 'failed': failed})


@teacher_bp.route('/api/essay/<essay_id>/assign-session', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def assign_essay_session(essay_id):
    """Essay를 특정 세션에 수동 배정 (또는 배정 해제)"""
    from app.models.essay import Essay
    essay = Essay.query.get_or_404(essay_id)
    data = request.json or {}
    session_id = data.get('session_id')  # None이면 배정 해제

    if session_id:
        session = CourseSession.query.get_or_404(session_id)
        if session.course.teacher_id != current_user.user_id and not current_user.is_admin:
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
        essay.session_id = session_id
        essay.course_id = session.course_id
        essay.session_assigned_auto = False
    else:
        essay.session_id = None
        essay.session_assigned_auto = False

    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/api/student-essays')
@login_required
@requires_role('teacher', 'admin')
def get_student_essays_for_assign():
    """특정 학생의 글쓰기 목록 반환 (세션 배정용)"""
    from app.models.essay import Essay, EssayResult
    student_id = request.args.get('student_id')
    course_id = request.args.get('course_id')

    if not student_id:
        return jsonify({'essays': []})

    query = Essay.query.filter_by(student_id=student_id)
    if course_id:
        # 해당 수업 글 또는 아직 배정 안 된 글
        from sqlalchemy import or_
        query = query.filter(
            or_(Essay.course_id == course_id, Essay.course_id.is_(None))
        )

    essays = query.order_by(Essay.created_at.desc()).limit(30).all()

    result_ids = [e.essay_id for e in essays]
    results = {}
    if result_ids:
        for r in EssayResult.query.filter(EssayResult.essay_id.in_(result_ids)).all():
            results[r.essay_id] = r

    data = []
    for e in essays:
        r = results.get(e.essay_id)
        data.append({
            'essay_id': e.essay_id,
            'title': e.title or '(제목 없음)',
            'created_at': e.created_at.strftime('%Y-%m-%d') if e.created_at else '-',
            'status': e.status,
            'total_score': float(r.total_score) if r and r.total_score else None,
            'final_grade': r.final_grade if r else None,
            'session_id': e.session_id,
            'session_assigned_auto': e.session_assigned_auto,
        })
    return jsonify({'essays': data})


@teacher_bp.route('/api/sessions/<session_id>/complete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def api_complete_session(session_id):
    """세션 출석 완료 토글 (AJAX용, JSON 반환)"""
    session = CourseSession.query.get_or_404(session_id)

    if session.course.teacher_id != current_user.user_id and not current_user.is_admin:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.json or {}
    checked = data.get('checked', True)

    session.attendance_checked = checked
    if checked:
        session.attendance_checked_at = datetime.utcnow()
        session.attendance_checked_by = current_user.user_id
        session.status = 'completed'
    else:
        session.status = 'scheduled'

    db.session.commit()
    return jsonify({'success': True, 'session_id': session_id, 'checked': checked})


@teacher_bp.route('/sessions/<session_id>/complete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def complete_session(session_id):
    """세션 출석 체크 완료"""
    session = CourseSession.query.get_or_404(session_id)
    course = session.course

    # 권한 확인
    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.courses'))

    # 세션 메모 업데이트
    topic = request.form.get('topic', '').strip()
    description = request.form.get('description', '').strip()

    if topic:
        session.topic = topic
    if description:
        session.description = description

    # 출석 체크 완료 표시
    session.attendance_checked = True
    session.attendance_checked_at = datetime.utcnow()
    session.attendance_checked_by = current_user.user_id
    session.status = 'completed'

    db.session.commit()

    flash('출석 체크가 완료되었습니다.', 'success')
    return redirect(url_for('teacher.course_detail', course_id=course.course_id))


@teacher_bp.route('/students')
@login_required
@requires_role('teacher', 'admin')
def students():
    """내 학생 목록"""
    # 검색 필터
    search = request.args.get('search', '').strip()
    grade_filter = request.args.get('grade', '').strip()
    course_type_filter = request.args.get('course_type', '').strip()

    # 내가 담당하는 수업의 모든 학생
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id).all()
    course_ids = [c.course_id for c in my_courses]

    # 수업 형태 필터 적용
    if course_type_filter:
        my_courses = [c for c in my_courses if c.course_type == course_type_filter]
        course_ids = [c.course_id for c in my_courses]

    enrollments = CourseEnrollment.query.filter(
        CourseEnrollment.course_id.in_(course_ids),
        CourseEnrollment.status == 'active'
    ).all()

    # 학생별로 그룹화
    students_dict = {}
    for enrollment in enrollments:
        student_id = enrollment.student_id
        student = enrollment.student

        # 이름/ID 검색 필터
        if search and search.lower() not in student.name.lower() and search not in student.student_id:
            continue

        # 학년 필터
        if grade_filter and student.grade != grade_filter:
            continue

        if student_id not in students_dict:
            students_dict[student_id] = {
                'student': student,
                'courses': [],
                'total_attendance_rate': 0,
                'enrollment_count': 0
            }
        students_dict[student_id]['courses'].append(enrollment.course)
        students_dict[student_id]['total_attendance_rate'] += enrollment.attendance_rate
        students_dict[student_id]['enrollment_count'] += 1

    # 평균 출석률 계산
    students_list = []
    for student_id, data in students_dict.items():
        if data['enrollment_count'] > 0:
            data['avg_attendance_rate'] = data['total_attendance_rate'] / data['enrollment_count']
        else:
            data['avg_attendance_rate'] = 0
        students_list.append(data)

    # 이름순 정렬
    students_list.sort(key=lambda x: x['student'].name)

    # 학년 목록 (드롭다운용)
    grades = ['초1', '초2', '초3', '초4', '초5', '초6',
              '중1', '중2', '중3',
              '고1', '고2', '고3']

    # 수업 형태 목록
    course_types = ['베이직', '프리미엄', '정규반', '하크니스']

    return render_template('teacher/students.html',
                         students=students_list,
                         search=search,
                         grade_filter=grade_filter,
                         course_type_filter=course_type_filter,
                         grades=grades,
                         course_types=course_types)


@teacher_bp.route('/students/<student_id>')
@login_required
@requires_role('teacher', 'admin')
def student_detail(student_id):
    """학생 상세 - 탭 기반 통합 페이지"""
    from app.models.student_profile import StudentProfile
    from app.models.consultation import ConsultationRecord
    from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType

    student = Student.query.get_or_404(student_id)

    # 이 학생의 수강 내역 (내가 담당하는 수업만)
    enrollments = CourseEnrollment.query.join(Course).filter(
        CourseEnrollment.student_id == student_id,
        Course.teacher_id == current_user.user_id
    ).all()

    if not enrollments and current_user.role not in ['admin', 'master_admin']:
        flash('이 학생을 담당하고 있지 않습니다.', 'error')
        return redirect(url_for('teacher.students'))

    # 학부모 정보
    parent_relations = ParentStudent.query.filter_by(student_id=student_id, is_active=True).all()
    parents = [pr.parent for pr in parent_relations]

    # 내가 작성한 피드백
    feedbacks = TeacherFeedback.query.filter_by(
        student_id=student_id,
        teacher_id=current_user.user_id
    ).order_by(TeacherFeedback.created_at.desc()).all()

    # 학생 프로필 (기초조사)
    profile = StudentProfile.query.filter_by(student_id=student_id).first()

    # MBTI 최신 결과
    mbti_result = ReadingMBTIResult.query.filter_by(student_id=student_id)\
        .order_by(ReadingMBTIResult.created_at.desc())\
        .first()

    mbti_type = None
    if mbti_result:
        mbti_type = ReadingMBTIType.query.get(mbti_result.type_id)

    # 상담 이력 (본인 작성 + 공유받은 것)
    consultations = ConsultationRecord.query.filter_by(student_id=student_id)\
        .filter(
            (ConsultationRecord.counselor_id == current_user.user_id) |
            (ConsultationRecord.reference_teachers.like(f'%{current_user.user_id}%'))
        )\
        .order_by(ConsultationRecord.consultation_date.desc())\
        .limit(10)\
        .all()

    # AI 인사이트 생성
    from app.utils.student_insights import generate_student_insights
    insights = generate_student_insights(
        student, enrollments, profile, mbti_result, mbti_type, consultations, feedbacks
    )

    # 주의사항 이력
    cautions = StudentCaution.query.filter_by(student_id=student_id)        .order_by(StudentCaution.is_resolved.asc(), StudentCaution.created_at.desc()).all()
    active_cautions = [c for c in cautions if not c.is_resolved]

    return render_template('teacher/student_detail.html',
                         student=student,
                         enrollments=enrollments,
                         parents=parents,
                         feedbacks=feedbacks,
                         profile=profile,
                         mbti_result=mbti_result,
                         mbti_type=mbti_type,
                         consultations=consultations,
                         insights=insights,
                         cautions=cautions,
                         active_cautions=active_cautions,
                         category_labels=CATEGORY_LABELS,
                         severity_meta=SEVERITY_META)


@teacher_bp.route('/feedback/new', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def create_feedback():
    """피드백 작성"""
    form = TeacherFeedbackForm()

    # 학생 목록 로드 (내가 담당하는 학생만)
    student_id = request.args.get('student_id')
    course_id = request.args.get('course_id')

    if student_id:
        # 특정 학생 선택됨
        students = [Student.query.get(student_id)]
    elif course_id:
        # 특정 수업의 학생들
        enrollments = CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()
        students = [e.student for e in enrollments]
    else:
        # 내가 담당하는 모든 학생
        my_courses = Course.query.filter_by(teacher_id=current_user.user_id).all()
        course_ids = [c.course_id for c in my_courses]
        enrollments = CourseEnrollment.query.filter(
            CourseEnrollment.course_id.in_(course_ids),
            CourseEnrollment.status == 'active'
        ).all()
        students = list(set([e.student for e in enrollments]))

    form.student_id.choices = [('', '-- 학생 선택 --')] + [
        (s.student_id, s.name) for s in sorted(students, key=lambda x: x.name)
    ]

    # 선택된 학생의 학부모 로드
    if request.method == 'GET' and student_id:
        form.student_id.data = student_id

    # POST 요청 시에도 선택된 학생이 있으면 학부모 목록 로드
    selected_student_id = student_id or form.student_id.data
    if selected_student_id:
        parent_relations = ParentStudent.query.filter_by(student_id=selected_student_id, is_active=True).all()
        parents = [pr.parent for pr in parent_relations]
        form.parent_id.choices = [('', '-- 학부모 선택 --')] + [
            (p.user_id, f"{p.name} ({p.email})") for p in parents
        ]
    else:
        form.parent_id.choices = [('', '-- 먼저 학생을 선택하세요 --')]

    if form.validate_on_submit():
        feedback = TeacherFeedback(
            student_id=form.student_id.data,
            teacher_id=current_user.user_id,
            parent_id=form.parent_id.data,
            feedback_type=form.feedback_type.data,
            priority=form.priority.data,
            title=form.title.data,
            content=form.content.data,
            hidden_from_student=True  # 항상 학생 비공개
        )

        # course_id가 있으면 연결
        if course_id:
            feedback.course_id = course_id

        db.session.add(feedback)
        db.session.commit()

        # 학부모에게 알림 전송
        if feedback.parent_id:
            Notification.create_notification(
                user_id=feedback.parent_id,
                notification_type='teacher_feedback',
                title='선생님 피드백이 도착했습니다',
                message=f'[{feedback.feedback_type}] {feedback.title}',
                link_url=url_for('parent.all_feedback')
            )

            # 이메일/SMS 발송 (선택 시)
            parent = User.query.get(feedback.parent_id)
            if parent:
                send_email = request.form.get('send_email') == '1'
                send_sms = request.form.get('send_sms') == '1'
                if send_email:
                    ok, reason = _send_feedback_email(parent, feedback)
                    if ok:
                        flash('이메일 발송 완료', 'success')
                    else:
                        flash(f'이메일 발송 실패 ({reason})', 'warning')
                if send_sms:
                    ok, reason = _send_feedback_sms(parent, feedback)
                    if ok:
                        flash('SMS 발송 완료', 'success')
                    else:
                        flash(f'SMS 발송 실패 ({reason})', 'warning')

        flash('피드백이 전송되었습니다.', 'success')
        return redirect(url_for('teacher.feedbacks'))

    return render_template('teacher/feedback_form.html',
                         form=form,
                         student_id=student_id,
                         course_id=course_id)


@teacher_bp.route('/api/students/<student_id>/parents', methods=['GET'])
@login_required
@requires_role('teacher', 'admin')
def get_student_parents(student_id):
    """학생의 학부모 목록 조회 API"""
    parent_relations = ParentStudent.query.filter_by(student_id=student_id, is_active=True).all()
    parents = [pr.parent for pr in parent_relations]

    return jsonify({
        'success': True,
        'parents': [
            {'user_id': p.user_id, 'name': p.name, 'email': p.email}
            for p in parents
        ]
    })


@teacher_bp.route('/feedback')
@login_required
@requires_role('teacher', 'admin')
def feedbacks():
    """내가 작성한 피드백 목록"""
    feedbacks = TeacherFeedback.query.filter_by(teacher_id=current_user.user_id)\
        .order_by(TeacherFeedback.created_at.desc()).all()

    return render_template('teacher/feedbacks.html',
                         feedbacks=feedbacks)


@teacher_bp.route('/feedback/<feedback_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def edit_feedback(feedback_id):
    """피드백 수정"""
    feedback = TeacherFeedback.query.get_or_404(feedback_id)

    if feedback.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('수정 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.feedbacks'))

    form = TeacherFeedbackForm(obj=feedback)

    # 학생 목록 (작성자 본인의 학생)
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id).all()
    course_ids = [c.course_id for c in my_courses]
    enrollments = CourseEnrollment.query.filter(
        CourseEnrollment.course_id.in_(course_ids),
        CourseEnrollment.status == 'active'
    ).all()
    students = list(set([e.student for e in enrollments]))
    # 원래 학생이 목록에 없을 경우 추가
    if feedback.student and feedback.student not in students:
        students.append(feedback.student)
    form.student_id.choices = [
        (s.student_id, s.name) for s in sorted(students, key=lambda x: x.name)
    ]

    # 학부모 목록
    parent_relations = ParentStudent.query.filter_by(
        student_id=feedback.student_id, is_active=True
    ).all()
    parents = [pr.parent for pr in parent_relations]
    form.parent_id.choices = [('', '-- 학부모 선택 --')] + [
        (p.user_id, f"{p.name} ({p.email})") for p in parents
    ]

    if form.validate_on_submit():
        feedback.feedback_type = form.feedback_type.data
        feedback.priority = form.priority.data
        feedback.title = form.title.data
        feedback.content = form.content.data
        feedback.updated_at = datetime.utcnow()
        db.session.commit()
        flash('피드백이 수정되었습니다.', 'success')
        return redirect(url_for('teacher.feedbacks'))

    return render_template('teacher/feedback_form.html',
                           form=form,
                           feedback=feedback,
                           edit_mode=True)


@teacher_bp.route('/feedback/<feedback_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_feedback(feedback_id):
    """피드백 삭제"""
    feedback = TeacherFeedback.query.get_or_404(feedback_id)

    if feedback.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.feedbacks'))

    db.session.delete(feedback)
    db.session.commit()
    flash('피드백이 삭제되었습니다.', 'success')
    return redirect(url_for('teacher.feedbacks'))


# ==================== 상담 기록 ====================

@teacher_bp.route('/consultations')
@login_required
@requires_role('teacher', 'admin')
def consultations():
    """상담 기록 목록"""
    from app.models.consultation import ConsultationRecord

    # 내가 작성한 상담 기록 + 참고인으로 설정된 기록
    my_consultations = ConsultationRecord.query.filter_by(counselor_id=current_user.user_id)\
        .order_by(ConsultationRecord.consultation_date.desc()).all()

    # 참고인으로 설정된 기록 찾기
    shared_consultations = ConsultationRecord.query.filter(
        ConsultationRecord.counselor_id != current_user.user_id
    ).all()

    # 나에게 공유된 것만 필터링
    shared_to_me = [c for c in shared_consultations if current_user.user_id in c.reference_teacher_ids]

    return render_template('teacher/consultations.html',
                         my_consultations=my_consultations,
                         shared_consultations=shared_to_me)


@teacher_bp.route('/consultations/create', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def create_consultation():
    """상담 기록 작성"""
    import traceback
    try:
        from app.models.consultation import ConsultationRecord
        from app.teacher.forms import ConsultationRecordForm

        form = ConsultationRecordForm()

        # 상담자 선택지 (강사 본인으로 기본 설정, 관리자는 다른 강사 선택 가능)
        if current_user.role in ['admin', 'master_admin']:
            teachers = User.query.filter(User.role.in_(['teacher', 'admin', 'master_admin']))\
                .order_by(User.name).all()
            form.counselor_id.choices = [(t.user_id, t.name) for t in teachers]
        else:
            form.counselor_id.choices = [(current_user.user_id, current_user.name)]

        # 학생 선택지
        if current_user.role in ['admin', 'master_admin']:
            students = Student.query.order_by(Student.name).all()
        else:
            # 강사는 자신이 가르치는 학생만
            enrollments = db.session.query(CourseEnrollment).join(Course).filter(
                Course.teacher_id == current_user.user_id,
                CourseEnrollment.status == 'active'
            ).all()
            student_ids = list(set([e.student_id for e in enrollments]))
            students = Student.query.filter(Student.student_id.in_(student_ids)).order_by(Student.name).all()

        form.student_id.choices = [('', '-- 학생 선택 --')] + [(s.student_id, f"{s.name} ({s.student_id[:8]})") for s in students]

        if request.method == 'GET':
            form.counselor_id.data = current_user.user_id

        if form.validate_on_submit():
            counselor_id = form.counselor_id.data if current_user.role in ['admin', 'master_admin'] else current_user.user_id
            student = Student.query.get(form.student_id.data)

            auto_title = f"[{form.major_category.data}] {student.name} - {form.consultation_date.data.strftime('%Y-%m-%d')}"
            if form.sub_category.data:
                auto_title = f"[{form.major_category.data}] {student.name} ({form.sub_category.data}) - {form.consultation_date.data.strftime('%Y-%m-%d')}"

            consultation = ConsultationRecord(
                consultation_date=form.consultation_date.data,
                counselor_id=counselor_id,
                student_id=form.student_id.data,
                major_category=form.major_category.data,
                sub_category=form.sub_category.data if form.sub_category.data else None,
                title=auto_title,
                content=form.content.data
            )
            db.session.add(consultation)
            db.session.flush()  # consultation_id 확보

            # ⚠️ 주의사항으로 함께 등록
            if request.form.get('register_caution'):
                caution = StudentCaution(
                    student_id=form.student_id.data,
                    author_id=current_user.user_id,
                    category=request.form.get('caution_category', 'consultation_note'),
                    severity=request.form.get('caution_severity', 'caution'),
                    title=auto_title,
                    content=form.content.data,
                    consultation_id=consultation.consultation_id,
                )
                db.session.add(caution)

            db.session.commit()

            flash('상담 기록이 저장되었습니다.', 'success')
            return redirect(url_for('teacher.consultations'))

        if request.method == 'POST':
            for field_name, errors in form.errors.items():
                for error in errors:
                    flash(f'{field_name}: {error}', 'danger')

        return render_template('teacher/consultation_form.html',
                             form=form,
                             is_admin=current_user.role in ['admin', 'master_admin'])

    except Exception as e:
        err = traceback.format_exc()
        current_app.logger.error(f'create_consultation error: {err}')
        flash(f'오류: {str(e)}', 'error')
        return f'<pre style="color:red">{err}</pre>', 500


@teacher_bp.route('/consultations/<int:consultation_id>')
@login_required
@requires_role('teacher', 'admin')
def consultation_detail(consultation_id):
    """상담 기록 상세"""
    from app.models.consultation import ConsultationRecord

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    # 권한 확인
    if not consultation.can_view(current_user.user_id, current_user.role):
        flash('이 상담 기록을 볼 권한이 없습니다.', 'danger')
        return redirect(url_for('teacher.consultations'))

    # 참고인 정보 가져오기
    reference_teachers = []
    if consultation.reference_teacher_ids:
        reference_teachers = User.query.filter(
            User.user_id.in_(consultation.reference_teacher_ids)
        ).all()

    return render_template('teacher/consultation_detail.html',
                         consultation=consultation,
                         reference_teachers=reference_teachers)


@teacher_bp.route('/consultations/<int:consultation_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def edit_consultation(consultation_id):
    """상담 기록 수정"""
    from app.models.consultation import ConsultationRecord
    from app.teacher.forms import ConsultationRecordForm

    consultation = ConsultationRecord.query.get_or_404(consultation_id)

    # 권한 확인 (작성자 또는 관리자만)
    if consultation.counselor_id != current_user.user_id and current_user.role not in ['admin', 'master_admin']:
        flash('이 상담 기록을 수정할 권한이 없습니다.', 'danger')
        return redirect(url_for('teacher.consultations'))

    form = ConsultationRecordForm(obj=consultation)

    # 상담자 선택지
    if current_user.role in ['admin', 'master_admin']:
        teachers = User.query.filter(User.role.in_(['teacher', 'admin', 'master_admin']))\
            .order_by(User.name).all()
        form.counselor_id.choices = [(t.user_id, t.name) for t in teachers]
    else:
        form.counselor_id.choices = [(current_user.user_id, current_user.name)]

    # 학생 선택지
    if current_user.role in ['admin', 'master_admin']:
        students = Student.query.filter_by(status='active').order_by(Student.name).all()
    else:
        from app.models.course import CourseEnrollment
        enrollments = db.session.query(CourseEnrollment).join(Course).filter(
            Course.teacher_id == current_user.user_id,
            CourseEnrollment.status == 'active'
        ).all()
        student_ids = list(set([e.student_id for e in enrollments]))
        students = Student.query.filter(Student.student_id.in_(student_ids)).order_by(Student.name).all()

    form.student_id.choices = [('', '-- 학생 선택 --')] + [(s.student_id, f"{s.name} ({s.student_id[:8]})") for s in students]

    if form.validate_on_submit():
        # 강사는 자신만 상담자로 설정 가능
        counselor_id = form.counselor_id.data if current_user.role in ['admin', 'master_admin'] else current_user.user_id

        # 학생 정보 가져오기
        student = Student.query.get(form.student_id.data)

        # 제목 자동 생성: [대분류] 학생명 - 날짜
        auto_title = f"[{form.major_category.data}] {student.name} - {form.consultation_date.data.strftime('%Y-%m-%d')}"
        if form.sub_category.data:
            auto_title = f"[{form.major_category.data}] {student.name} ({form.sub_category.data}) - {form.consultation_date.data.strftime('%Y-%m-%d')}"

        consultation.consultation_date = form.consultation_date.data
        consultation.counselor_id = counselor_id
        consultation.student_id = form.student_id.data
        consultation.major_category = form.major_category.data
        consultation.sub_category = form.sub_category.data if form.sub_category.data else None
        consultation.title = auto_title
        consultation.content = form.content.data

        db.session.commit()

        flash('상담 기록이 수정되었습니다.', 'success')
        return redirect(url_for('teacher.consultation_detail', consultation_id=consultation_id))

    return render_template('teacher/consultation_form.html',
                         form=form,
                         consultation=consultation,
                         is_admin=current_user.role in ['admin', 'master_admin'])


@teacher_bp.route('/api/consultation-subcategories/<major_category>')
@login_required
@requires_role('teacher', 'admin')
def get_consultation_subcategories(major_category):
    """대분류에 따른 소분류 반환"""
    subcategories = {
        '신규상담': ['초기면담', '레벨테스트', '커리큘럼 안내', '학습목표 설정'],
        '퇴원상담': ['수강종료', '전원', '환불', '기타'],
        '분기별상담': ['1분기', '2분기', '3분기', '4분기', '중간점검'],
        '진로진학상담': ['대입상담', '유학상담', '진로탐색', '학과선택'],
        '기타': ['학습고민', '행동문제', '가정문제', '기타']
    }

    return jsonify({
        'success': True,
        'subcategories': subcategories.get(major_category, [])
    })


# ==================== 과제 관리 ====================

@teacher_bp.route('/assignments')
@login_required
@requires_role('teacher', 'admin')
def assignments():
    """과제 목록 — 내가 등록한 과제 + 학생 글쓰기(첨삭) 과제"""
    from app.models.essay import Essay

    # ── 섹션 1: 내가 등록한 정식 과제 ──────────────────────────────
    my_assignments = Assignment.query.filter_by(teacher_id=current_user.user_id)\
        .order_by(Assignment.due_date.desc()).all()

    pending_count = 0
    for a in my_assignments:
        pending_count += AssignmentSubmission.query.filter_by(
            assignment_id=a.assignment_id, status='submitted'
        ).count()

    # ── 섹션 2: 내 담당 학생들의 글쓰기(첨삭) 과제 ─────────────────
    # 내 수업 수강생 student_id 목록
    my_course_ids = [c.course_id for c in
                     Course.query.filter_by(teacher_id=current_user.user_id, status='active').all()]
    enrolled_student_ids = []
    if my_course_ids:
        enrolled_student_ids = [
            e.student_id for e in
            CourseEnrollment.query.filter(
                CourseEnrollment.course_id.in_(my_course_ids),
                CourseEnrollment.status == 'active'
            ).all()
        ]

    # student.teacher_id 직접 배정된 학생 + 내 수업 수강생
    direct_student_ids = [
        s.student_id for s in Student.query.filter_by(teacher_id=current_user.user_id).all()
    ]
    all_student_ids = list(set(enrolled_student_ids + direct_student_ids))

    writing_essays = []
    if all_student_ids:
        writing_essays = Essay.query.filter(
            Essay.student_id.in_(all_student_ids)
        ).order_by(Essay.created_at.desc()).limit(100).all()

    # 첨삭 대기(미완료) / 완료 분리
    essays_pending   = [e for e in writing_essays if e.status not in ('completed', 'failed')]
    essays_completed = [e for e in writing_essays if e.status == 'completed']

    return render_template('teacher/assignments.html',
                           assignments=my_assignments,
                           pending_count=pending_count,
                           essays_pending=essays_pending,
                           essays_completed=essays_completed)


@teacher_bp.route('/assignments/new', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def create_assignment():
    """과제 생성"""
    if request.method == 'POST':
        # 내가 담당하는 수업만 선택 가능
        course_id = request.form.get('course_id') or None
        target_student_id = request.form.get('target_student_id') or None

        course = None
        if course_id:
            course = Course.query.get(course_id)
            if course and course.teacher_id != current_user.user_id:
                flash('권한이 없습니다.', 'error')
                return redirect(url_for('teacher.assignments'))

        assignment = Assignment(
            teacher_id=current_user.user_id,
            course_id=course_id,
            target_student_id=target_student_id,
            title=request.form['title'],
            description=request.form['description'],
            assignment_type=request.form.get('assignment_type', 'essay'),
            difficulty=request.form.get('difficulty', 'medium'),
            max_score=int(request.form.get('max_score', 100)),
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%dT%H:%M'),
            late_submission_allowed=request.form.get('late_submission_allowed') == 'on',
            late_penalty_percent=int(request.form.get('late_penalty_percent', 10)),
            submission_type=request.form.get('submission_type', 'text'),
            status='active',
            is_published=True
        )

        db.session.add(assignment)
        db.session.flush()

        # 알림 발송
        if course_id and course:
            if target_student_id:
                # 개별 학생에게만
                target_student = Student.query.get(target_student_id)
                if target_student and target_student.user_id:
                    db.session.add(Notification(
                        user_id=target_student.user_id,
                        notification_type='assignment',
                        title=f'새 과제: {assignment.title}',
                        message=f'{course.course_name} 수업의 새 과제가 등록되었습니다. 마감: {assignment.due_date.strftime("%m/%d %H:%M")}',
                        link_url=f'/student/assignments/{assignment.assignment_id}',
                        related_entity_type='assignment',
                        related_entity_id=assignment.assignment_id
                    ))
            else:
                # 수업 전체 학생에게
                enrollments = CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()
                for enrollment in enrollments:
                    if enrollment.student.user_id:
                        db.session.add(Notification(
                            user_id=enrollment.student.user_id,
                            notification_type='assignment',
                            title=f'새 과제: {assignment.title}',
                            message=f'{course.course_name} 수업의 새 과제가 등록되었습니다. 마감: {assignment.due_date.strftime("%m/%d %H:%M")}',
                            link_url=f'/student/assignments/{assignment.assignment_id}',
                            related_entity_type='assignment',
                            related_entity_id=assignment.assignment_id
                        ))

        db.session.commit()

        flash(f'과제 "{assignment.title}"이(가) 등록되었습니다.', 'success')
        return redirect(url_for('teacher.assignment_detail', assignment_id=assignment.assignment_id))

    # GET - 폼 표시
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active').all()

    # 수업별 학생 목록 (JSON)
    import json
    course_students = {}
    for course in my_courses:
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.course_id, status='active'
        ).all()
        course_students[course.course_id] = [
            {'student_id': e.student.student_id, 'name': e.student.name, 'grade': e.student.grade}
            for e in enrollments if e.student
        ]

    return render_template('teacher/assignment_form.html',
                         courses=my_courses,
                         course_students_json=json.dumps(course_students, ensure_ascii=False),
                         is_edit=False)


@teacher_bp.route('/assignments/<assignment_id>')
@login_required
@requires_role('teacher', 'admin')
def assignment_detail(assignment_id):
    """과제 상세"""
    assignment = Assignment.query.get_or_404(assignment_id)

    # 권한 확인
    if assignment.teacher_id != current_user.user_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.assignments'))

    # 제출물 목록
    submissions = AssignmentSubmission.query.filter_by(assignment_id=assignment_id)\
        .order_by(AssignmentSubmission.submitted_at.desc()).all()

    # 통계
    total_students = len(assignment.course.enrollments) if assignment.course else 0
    submitted_count = len([s for s in submissions if s.is_submitted])
    graded_count = len([s for s in submissions if s.is_graded])

    return render_template('teacher/assignment_detail.html',
                         assignment=assignment,
                         submissions=submissions,
                         total_students=total_students,
                         submitted_count=submitted_count,
                         graded_count=graded_count)


@teacher_bp.route('/assignments/<assignment_id>/submissions/<submission_id>/grade', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def grade_submission(assignment_id, submission_id):
    """과제 채점"""
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    assignment = submission.assignment

    # 권한 확인
    if assignment.teacher_id != current_user.user_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.assignments'))

    if request.method == 'POST':
        score = int(request.form['score'])
        feedback = request.form['feedback']

        # 채점 처리
        submission.grade(score, feedback, current_user.user_id)

        # 학생에게 알림
        if submission.student.user_id:
            notification = Notification(
                user_id=submission.student.user_id,
                notification_type='assignment_graded',
                title=f'과제 채점 완료: {assignment.title}',
                message=f'과제가 채점되었습니다. 점수: {score}/{assignment.max_score}점',
                link_url=f'/student/assignments/{assignment_id}',
                related_entity_type='assignment',
                related_entity_id=assignment_id
            )
            db.session.add(notification)

        db.session.commit()

        flash('채점이 완료되었습니다.', 'success')
        return redirect(url_for('teacher.assignment_detail', assignment_id=assignment_id))

    # 해당 학생의 다른 채점 완료 이력 (현재 과제 제외, 최신 10개)
    feedback_history = AssignmentSubmission.query.join(
        Assignment, AssignmentSubmission.assignment_id == Assignment.assignment_id
    ).filter(
        AssignmentSubmission.student_id == submission.student_id,
        Assignment.teacher_id == current_user.user_id,
        AssignmentSubmission.status == 'graded',
        AssignmentSubmission.submission_id != submission.submission_id
    ).order_by(AssignmentSubmission.graded_at.desc()).limit(10).all()

    return render_template('teacher/grade_submission.html',
                         submission=submission,
                         assignment=assignment,
                         feedback_history=feedback_history)


@teacher_bp.route('/assignments/<assignment_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_assignment(assignment_id):
    """과제 삭제"""
    assignment = Assignment.query.get_or_404(assignment_id)

    # 권한 확인
    if assignment.teacher_id != current_user.user_id:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.assignments'))

    db.session.delete(assignment)
    db.session.commit()

    flash('과제가 삭제되었습니다.', 'info')
    return redirect(url_for('teacher.assignments'))


@teacher_bp.route('/assignments/submissions/<submission_id>/download')
@login_required
@requires_role('teacher', 'admin')
def download_submission_file(submission_id):
    """제출된 과제 파일 다운로드"""
    from flask import current_app, send_from_directory
    import os

    submission = AssignmentSubmission.query.get_or_404(submission_id)
    assignment = submission.assignment

    # 권한 확인 (담당 강사만)
    if assignment.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.assignments'))

    if not submission.file_path:
        flash('첨부된 파일이 없습니다.', 'error')
        return redirect(url_for('teacher.grade_submission',
                               assignment_id=assignment.assignment_id,
                               submission_id=submission_id))

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


# ==================== 학습 자료 관리 ====================

@teacher_bp.route('/materials')
@login_required
@requires_role('teacher', 'admin')
def materials():
    """학습 자료 목록"""
    from flask import current_app

    # 내가 업로드한 자료
    my_materials = Material.query.filter_by(uploaded_by=current_user.user_id)\
        .order_by(Material.created_at.desc()).all()

    # 통계
    total_downloads = sum(m.download_count for m in my_materials)

    return render_template('teacher/materials.html',
                         materials=my_materials,
                         total_downloads=total_downloads)


@teacher_bp.route('/materials/new', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def upload_material():
    """학습 자료 업로드"""
    from flask import current_app
    from werkzeug.utils import secure_filename
    import os

    if request.method == 'POST':
        # 파일 체크
        if 'file' not in request.files:
            flash('파일이 선택되지 않았습니다.', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('파일이 선택되지 않았습니다.', 'error')
            return redirect(request.url)

        # 파일 확장자 체크
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

        from config import ALLOWED_MATERIAL_EXTENSIONS
        if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
            flash(f'허용되지 않는 파일 형식입니다. 허용: {", ".join(ALLOWED_MATERIAL_EXTENSIONS)}', 'error')
            return redirect(request.url)

        # 파일 저장
        import uuid
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        materials_folder = current_app.config['MATERIALS_FOLDER']
        os.makedirs(materials_folder, exist_ok=True)
        file_path = os.path.join(materials_folder, unique_filename)
        try:
            file.save(file_path)
        except Exception as e:
            flash(f'파일 저장 중 오류가 발생했습니다: {str(e)}', 'error')
            return redirect(request.url)

        # 파일 크기
        file_size = os.path.getsize(file_path)

        # 데이터베이스에 저장
        material = Material(
            title=request.form['title'],
            description=request.form.get('description', ''),
            file_name=filename,
            file_path=unique_filename,
            file_size=file_size,
            file_type=file_ext,
            category=request.form.get('category', 'general'),
            tags=request.form.get('tags', ''),
            course_id=request.form.get('course_id') if request.form.get('course_id') else None,
            uploaded_by=current_user.user_id,
            access_level=request.form.get('access_level', 'all'),
            tier_restriction=request.form.get('tier_restriction', ''),
            is_published=request.form.get('is_published') == 'on'
        )

        db.session.add(material)
        db.session.commit()

        flash(f'"{material.title}" 자료가 업로드되었습니다.', 'success')
        return redirect(url_for('teacher.materials'))

    # GET - 폼 표시
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active').all()

    return render_template('teacher/material_form.html',
                         courses=my_courses,
                         is_edit=False)


@teacher_bp.route('/materials/<material_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def edit_material(material_id):
    """학습 자료 수정"""
    material = Material.query.get_or_404(material_id)

    # 권한 확인
    if material.uploaded_by != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.materials'))

    if request.method == 'POST':
        material.title = request.form['title']
        material.description = request.form.get('description', '')
        material.category = request.form.get('category', 'general')
        material.tags = request.form.get('tags', '')
        material.course_id = request.form.get('course_id') if request.form.get('course_id') else None
        material.access_level = request.form.get('access_level', 'all')
        material.tier_restriction = request.form.get('tier_restriction', '')
        material.is_published = request.form.get('is_published') == 'on'
        material.updated_at = datetime.utcnow()

        db.session.commit()

        flash('자료 정보가 수정되었습니다.', 'success')
        return redirect(url_for('teacher.materials'))

    # GET
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active').all()

    return render_template('teacher/material_form.html',
                         material=material,
                         courses=my_courses,
                         is_edit=True)


@teacher_bp.route('/materials/<material_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_material(material_id):
    """학습 자료 삭제"""
    from flask import current_app
    import os

    material = Material.query.get_or_404(material_id)

    # 권한 확인
    if material.uploaded_by != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.materials'))

    # 파일 삭제
    file_path = os.path.join(current_app.config['MATERIALS_FOLDER'], material.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(material)
    db.session.commit()

    flash('자료가 삭제되었습니다.', 'info')
    return redirect(url_for('teacher.materials'))


# ==================== 수업 공지/과제 메시지 ====================

@teacher_bp.route('/class-messages')
@login_required
@requires_role('teacher', 'admin')
def class_messages():
    """수업 공지/과제 메시지 메인 페이지"""
    # 내가 담당하는 수업 목록
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active')\
        .order_by(Course.start_date.desc()).all()

    # 내가 담당하는 학생 목록
    course_ids = [c.course_id for c in my_courses]
    enrollments = CourseEnrollment.query.filter(
        CourseEnrollment.course_id.in_(course_ids),
        CourseEnrollment.status == 'active'
    ).all()

    # 학생 중복 제거
    students_dict = {}
    for enrollment in enrollments:
        student_id = enrollment.student_id
        if student_id not in students_dict:
            students_dict[student_id] = enrollment.student

    students = list(students_dict.values())
    students.sort(key=lambda x: x.name)

    # 최근 발송한 메시지 (내가 발송한 것만, 학생에게 보낸 것만 표시하여 중복 제거)
    recent_messages = Notification.query.join(User, Notification.user_id == User.user_id).filter(
        Notification.notification_type.in_(['class_announcement', 'homework_assignment']),
        Notification.related_user_id == current_user.user_id,
        User.role == 'student'  # 학생에게 보낸 것만 (학부모 중복 제거)
    ).order_by(Notification.created_at.desc()).limit(20).all()

    # 수신자 이름+학년 사전 (user_id → "이름 (학년)")
    student_info_map = {}
    for msg in recent_messages:
        if msg.user_id and msg.user_id not in student_info_map:
            st = Student.query.filter_by(user_id=msg.user_id).first()
            if st:
                student_info_map[msg.user_id] = f"{st.name} ({st.grade})"
            elif msg.user:
                student_info_map[msg.user_id] = msg.user.name
            else:
                student_info_map[msg.user_id] = '알 수 없음'

    return render_template('teacher/class_messages.html',
                         courses=my_courses,
                         students=students,
                         recent_messages=recent_messages,
                         student_info_map=student_info_map)


@teacher_bp.route('/class-messages/send-to-course', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def send_course_message():
    """반 전체에 공지 발송"""
    from werkzeug.utils import secure_filename
    import uuid as _uuid

    course_id = request.form.get('course_id')
    message_type = request.form.get('message_type', 'announcement')
    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    send_to_parents = request.form.get('send_to_parents') == '1'

    if not all([course_id, title, message]):
        flash('모든 필드를 입력해주세요.', 'error')
        return redirect(url_for('teacher.class_messages'))

    course = Course.query.get_or_404(course_id)

    if course.teacher_id != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    # 첨부파일 처리
    attachment_url = None
    attachment_name = None
    upload_file = request.files.get('attachment')
    if upload_file and upload_file.filename:
        allowed_ext = {'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'hwp', 'zip', 'mp4', 'mp3'}
        ext = os.path.splitext(secure_filename(upload_file.filename))[1].lstrip('.').lower()
        if ext in allowed_ext:
            save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'class_messages')
            os.makedirs(save_dir, exist_ok=True)
            unique_name = f"{_uuid.uuid4().hex}.{ext}"
            upload_file.save(os.path.join(save_dir, unique_name))
            attachment_url = f"class_messages/{unique_name}"
            attachment_name = upload_file.filename

    enrollments = CourseEnrollment.query.filter_by(course_id=course_id, status='active').all()
    notification_type = 'class_announcement' if message_type == 'announcement' else 'homework_assignment'
    notification_title = f"[{course.course_name}] {title}"

    sent_count = 0
    parent_count = 0
    for enrollment in enrollments:
        student_notification = Notification(
            user_id=enrollment.student.user_id,
            notification_type=notification_type,
            title=notification_title,
            message=message,
            related_user_id=current_user.user_id,
            related_entity_type='course',
            related_entity_id=course_id,
            attachment_url=attachment_url,
            attachment_name=attachment_name
        )
        db.session.add(student_notification)
        sent_count += 1

        if send_to_parents:
            parent_relations = ParentStudent.query.filter_by(student_id=enrollment.student_id, is_active=True).all()
            for pr in parent_relations:
                parent_notification = Notification(
                    user_id=pr.parent_id,
                    notification_type=notification_type,
                    title=f"[{enrollment.student.name}] {notification_title}",
                    message=message,
                    related_user_id=current_user.user_id,
                    related_entity_type='course',
                    related_entity_id=course_id,
                    attachment_url=attachment_url,
                    attachment_name=attachment_name
                )
                db.session.add(parent_notification)
                parent_count += 1

    db.session.commit()

    message_type_korean = '수업 공지' if message_type == 'announcement' else '과제'
    if send_to_parents:
        flash(f'{message_type_korean}가 {sent_count}명의 학생과 {parent_count}명의 학부모에게 발송되었습니다.', 'success')
    else:
        flash(f'{message_type_korean}가 {sent_count}명의 학생에게 발송되었습니다.', 'success')
    return redirect(url_for('teacher.class_messages'))


@teacher_bp.route('/class-messages/send-to-student', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def send_student_message():
    """개별 학생에게 과제/메시지 발송"""
    from werkzeug.utils import secure_filename
    import uuid as _uuid

    student_id = request.form.get('student_id')
    message_type = request.form.get('message_type', 'homework')
    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    send_to_parents = request.form.get('send_to_parents') == '1'

    if not all([student_id, title, message]):
        flash('모든 필드를 입력해주세요.', 'error')
        return redirect(url_for('teacher.class_messages'))

    student = Student.query.get_or_404(student_id)

    enrollments = CourseEnrollment.query.join(Course).filter(
        CourseEnrollment.student_id == student_id,
        Course.teacher_id == current_user.user_id,
        CourseEnrollment.status == 'active'
    ).all()

    if not enrollments and not current_user.is_admin:
        flash('이 학생을 담당하고 있지 않습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    # 첨부파일 처리
    attachment_url = None
    attachment_name = None
    upload_file = request.files.get('attachment')
    if upload_file and upload_file.filename:
        allowed_ext = {'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'hwp', 'zip', 'mp4', 'mp3'}
        ext = os.path.splitext(secure_filename(upload_file.filename))[1].lstrip('.').lower()
        if ext in allowed_ext:
            save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'class_messages')
            os.makedirs(save_dir, exist_ok=True)
            unique_name = f"{_uuid.uuid4().hex}.{ext}"
            upload_file.save(os.path.join(save_dir, unique_name))
            attachment_url = f"class_messages/{unique_name}"
            attachment_name = upload_file.filename

    notification_type = 'homework_assignment' if message_type == 'homework' else 'class_announcement'

    student_notification = Notification(
        user_id=student.user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_user_id=current_user.user_id,
        related_entity_type='student',
        related_entity_id=student_id,
        attachment_url=attachment_url,
        attachment_name=attachment_name
    )
    db.session.add(student_notification)

    parent_count = 0
    if send_to_parents:
        parent_relations = ParentStudent.query.filter_by(student_id=student_id, is_active=True).all()
        for pr in parent_relations:
            parent_notification = Notification(
                user_id=pr.parent_id,
                notification_type=notification_type,
                title=f"[{student.name}] {title}",
                message=message,
                related_user_id=current_user.user_id,
                related_entity_type='student',
                related_entity_id=student_id,
                attachment_url=attachment_url,
                attachment_name=attachment_name
            )
            db.session.add(parent_notification)
            parent_count += 1

    db.session.commit()

    message_type_korean = '과제' if message_type == 'homework' else '메시지'
    if send_to_parents and parent_count > 0:
        flash(f'{message_type_korean}가 {student.name} 학생과 {parent_count}명의 학부모에게 발송되었습니다.', 'success')
    else:
        flash(f'{message_type_korean}가 {student.name} 학생에게 발송되었습니다.', 'success')
    return redirect(url_for('teacher.class_messages'))


@teacher_bp.route('/class-messages/<notification_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def edit_class_message(notification_id):
    """과제/공지 메시지 수정 — 같은 배치(발송자+유형+대상+5분 이내)를 일괄 수정"""
    from datetime import timedelta

    notif = Notification.query.get_or_404(notification_id)

    if notif.related_user_id != current_user.user_id and not current_user.is_admin:
        flash('수정 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    if request.method == 'POST':
        new_title_raw = request.form.get('title', '').strip()
        new_message   = request.form.get('message', '').strip()

        if not new_title_raw or not new_message:
            flash('제목과 내용을 입력해주세요.', 'error')
            return render_template('teacher/class_message_edit.html', notif=notif)

        # 같은 배치: 동일 발송자 + 유형 + 대상 entity + 5분 이내 생성
        window_start = notif.created_at - timedelta(minutes=5)
        window_end   = notif.created_at + timedelta(minutes=5)
        batch = Notification.query.filter(
            Notification.related_user_id == current_user.user_id,
            Notification.notification_type == notif.notification_type,
            Notification.related_entity_id == notif.related_entity_id,
            Notification.created_at >= window_start,
            Notification.created_at <= window_end,
        ).all()

        # 배치 전체의 title 접두어(수업명/학생명 부분)는 유지하고, 사용자가 입력한 제목만 교체
        # 원본 title에서 '] ' 이후 부분이 사용자 입력 제목
        for n in batch:
            if '] ' in n.title:
                prefix = n.title[:n.title.index('] ') + 2]
                n.title = prefix + new_title_raw
            else:
                n.title = new_title_raw
            n.message = new_message

        db.session.commit()
        flash(f'메시지가 수정되었습니다. ({len(batch)}명 대상)', 'success')
        return redirect(url_for('teacher.class_messages'))

    return render_template('teacher/class_message_edit.html', notif=notif)


@teacher_bp.route('/class-messages/<notification_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_class_message(notification_id):
    """과제/공지 메시지 삭제 — 같은 배치 일괄 삭제"""
    from datetime import timedelta

    notif = Notification.query.get_or_404(notification_id)

    if notif.related_user_id != current_user.user_id and not current_user.is_admin:
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    window_start = notif.created_at - timedelta(minutes=5)
    window_end   = notif.created_at + timedelta(minutes=5)
    batch = Notification.query.filter(
        Notification.related_user_id == current_user.user_id,
        Notification.notification_type == notif.notification_type,
        Notification.related_entity_id == notif.related_entity_id,
        Notification.created_at >= window_start,
        Notification.created_at <= window_end,
    ).all()

    count = len(batch)
    for n in batch:
        db.session.delete(n)
    db.session.commit()

    flash(f'메시지가 삭제되었습니다. ({count}명 대상)', 'success')
    return redirect(url_for('teacher.class_messages'))


@teacher_bp.route('/class-messages/<notification_id>')
@login_required
@requires_role('teacher', 'admin')
def class_message_detail(notification_id):
    """과제/공지 메시지 상세 — 답글 스레드 보기"""
    from app.models.notification_reply import NotificationReply

    notification = Notification.query.get_or_404(notification_id)

    # 본인이 발송한 메시지만 조회 가능
    if notification.related_user_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    replies = NotificationReply.query.filter_by(
        notification_id=notification_id
    ).order_by(NotificationReply.created_at.asc()).all()

    return render_template('teacher/class_message_detail.html',
                           notification=notification,
                           replies=replies)


@teacher_bp.route('/class-messages/attachment/<notification_id>')
@login_required
def download_class_message_attachment(notification_id):
    """수업 메시지 첨부파일 다운로드"""
    notif = Notification.query.get_or_404(notification_id)
    if not notif.attachment_url:
        flash('첨부파일이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_dir = os.path.dirname(os.path.join(upload_folder, notif.attachment_url))
    file_name = os.path.basename(notif.attachment_url)
    return send_from_directory(file_dir, file_name, as_attachment=True,
                               download_name=notif.attachment_name or file_name)



@teacher_bp.route('/class-messages/<notification_id>/reply', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def reply_to_class_message(notification_id):
    """과제/공지 메시지에 강사 답글 달기"""
    from app.models.notification_reply import NotificationReply

    notification = Notification.query.get_or_404(notification_id)

    # 본인이 발송한 메시지만
    if notification.related_user_id != current_user.user_id and not current_user.is_admin:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_messages'))

    content = request.form.get('content', '').strip()
    if not content:
        flash('답글 내용을 입력해주세요.', 'error')
        return redirect(url_for('teacher.class_message_detail', notification_id=notification_id))

    # 답글 저장
    reply = NotificationReply(
        notification_id=notification_id,
        author_id=current_user.user_id,
        content=content
    )
    db.session.add(reply)

    # 학생에게 알림 발송
    student_notification = Notification(
        user_id=notification.user_id,
        notification_type='homework_reply',
        title=f'[답글] {notification.title}',
        message=f'강사님이 답글을 달았습니다: {content[:50]}{"..." if len(content) > 50 else ""}',
        related_user_id=current_user.user_id,
        related_entity_type='notification',
        related_entity_id=notification_id,
        link_url='/student/homework'
    )
    db.session.add(student_notification)
    db.session.commit()

    flash('답글이 등록되었습니다.', 'success')
    return redirect(url_for('teacher.class_message_detail', notification_id=notification_id))


# ==================== 강사 게시판 ====================

@teacher_bp.route('/board')
@login_required
@requires_role('teacher', 'admin')
def board():
    """강사 게시판 목록"""
    from app.models.teacher_board import TeacherBoard

    # 페이지네이션
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 검색
    search_query = request.args.get('q', '').strip()

    # 쿼리 생성
    query = TeacherBoard.query

    if search_query:
        query = query.filter(
            db.or_(
                TeacherBoard.title.contains(search_query),
                TeacherBoard.content.contains(search_query)
            )
        )

    # 정렬: 공지사항 우선, 최신순
    query = query.order_by(
        TeacherBoard.is_notice.desc(),
        TeacherBoard.created_at.desc()
    )

    # 페이지네이션
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    boards = pagination.items

    return render_template('teacher/board/list.html',
                         boards=boards,
                         pagination=pagination,
                         search_query=search_query)


@teacher_bp.route('/board/<board_id>')
@login_required
@requires_role('teacher', 'admin')
def board_detail(board_id):
    """강사 게시판 상세"""
    from app.models.teacher_board import TeacherBoard

    board = TeacherBoard.query.get_or_404(board_id)

    # 조회수 증가 (본인 글 제외)
    if board.author_id != current_user.user_id:
        board.view_count += 1
        db.session.commit()

    return render_template('teacher/board/detail.html', board=board)


@teacher_bp.route('/board/new', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def board_new():
    """강사 게시판 글 작성"""
    from app.models.teacher_board import TeacherBoard, TeacherBoardAttachment
    from werkzeug.utils import secure_filename
    import os
    import uuid as uuid_module

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_notice = request.form.get('is_notice') == 'on'

        if not title or not content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return redirect(url_for('teacher.board_new'))

        # 공지사항은 관리자만 가능
        if is_notice and not current_user.is_admin:
            is_notice = False

        # 게시글 생성
        board = TeacherBoard(
            author_id=current_user.user_id,
            title=title,
            content=content,
            is_notice=is_notice
        )
        db.session.add(board)
        db.session.flush()

        # 첨부파일 처리 (최대 10개)
        files = request.files.getlist('attachments')
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'teacher_board')
        os.makedirs(upload_folder, exist_ok=True)

        uploaded_count = 0
        for file in files[:10]:  # 최대 10개
            if file and file.filename:
                original_filename = secure_filename(file.filename)
                ext = os.path.splitext(original_filename)[1].lower()
                stored_filename = f"{uuid_module.uuid4().hex}{ext}"
                file_path = os.path.join(upload_folder, stored_filename)

                file.save(file_path)

                file_size = os.path.getsize(file_path)
                file_type = ext.lstrip('.')
                is_image = file_type in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']

                attachment = TeacherBoardAttachment(
                    board_id=board.board_id,
                    original_filename=original_filename,
                    stored_filename=stored_filename,
                    file_path=os.path.join('teacher_board', stored_filename),
                    file_size=file_size,
                    file_type=file_type,
                    is_image=is_image,
                    uploaded_by=current_user.user_id
                )
                db.session.add(attachment)
                uploaded_count += 1

        db.session.commit()

        flash(f'게시글이 등록되었습니다. (첨부파일 {uploaded_count}개)', 'success')
        return redirect(url_for('teacher.board_detail', board_id=board.board_id))

    return render_template('teacher/board/form.html', board=None)


@teacher_bp.route('/board/<board_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def board_edit(board_id):
    """강사 게시판 글 수정"""
    from app.models.teacher_board import TeacherBoard, TeacherBoardAttachment
    from werkzeug.utils import secure_filename
    import os
    import uuid as uuid_module

    board = TeacherBoard.query.get_or_404(board_id)

    # 본인 글이거나 관리자만 수정 가능
    if board.author_id != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.board_detail', board_id=board_id))

    if request.method == 'POST':
        board.title = request.form.get('title', '').strip()
        board.content = request.form.get('content', '').strip()
        is_notice = request.form.get('is_notice') == 'on'

        if not board.title or not board.content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return render_template('teacher/board/form.html', board=board)

        # 공지사항은 관리자만 설정 가능
        if current_user.is_admin:
            board.is_notice = is_notice

        # 기존 첨부파일 삭제 처리
        delete_attachments = request.form.getlist('delete_attachments')
        for attachment_id in delete_attachments:
            attachment = TeacherBoardAttachment.query.get(attachment_id)
            if attachment and attachment.board_id == board_id:
                # 파일 삭제
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(attachment)

        # 새 첨부파일 추가 (현재 개수 + 새 파일 <= 10개)
        current_count = board.attachments.count()
        files = request.files.getlist('attachments')
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'teacher_board')
        os.makedirs(upload_folder, exist_ok=True)

        uploaded_count = 0
        remaining_slots = 10 - current_count
        for file in files[:remaining_slots]:
            if file and file.filename:
                original_filename = secure_filename(file.filename)
                ext = os.path.splitext(original_filename)[1].lower()
                stored_filename = f"{uuid_module.uuid4().hex}{ext}"
                file_path = os.path.join(upload_folder, stored_filename)

                file.save(file_path)

                file_size = os.path.getsize(file_path)
                file_type = ext.lstrip('.')
                is_image = file_type in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']

                attachment = TeacherBoardAttachment(
                    board_id=board.board_id,
                    original_filename=original_filename,
                    stored_filename=stored_filename,
                    file_path=os.path.join('teacher_board', stored_filename),
                    file_size=file_size,
                    file_type=file_type,
                    is_image=is_image,
                    uploaded_by=current_user.user_id
                )
                db.session.add(attachment)
                uploaded_count += 1

        db.session.commit()

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('teacher.board_detail', board_id=board_id))

    return render_template('teacher/board/form.html', board=board)


@teacher_bp.route('/board/<board_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def board_delete(board_id):
    """강사 게시판 글 삭제"""
    from app.models.teacher_board import TeacherBoard
    import os

    board = TeacherBoard.query.get_or_404(board_id)

    # 본인 글이거나 관리자만 삭제 가능
    if board.author_id != current_user.user_id and not current_user.is_admin:
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.board_detail', board_id=board_id))

    # 첨부파일 삭제
    for attachment in board.attachments:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(board)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('teacher.board'))


@teacher_bp.route('/board/attachment/<attachment_id>/download')
@login_required
@requires_role('teacher', 'admin')
def board_attachment_download(attachment_id):
    """첨부파일 다운로드"""
    from app.models.teacher_board import TeacherBoardAttachment
    from flask import send_file
    import os

    attachment = TeacherBoardAttachment.query.get_or_404(attachment_id)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)

    if not os.path.exists(file_path):
        flash('파일을 찾을 수 없습니다.', 'error')
        return redirect(url_for('teacher.board'))

    return send_file(
        file_path,
        as_attachment=True,
        download_name=attachment.original_filename
    )


@teacher_bp.route('/board/upload-image', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def board_upload_image():
    """에디터에서 이미지 업로드 (클립보드 붙여넣기 포함)"""
    from werkzeug.utils import secure_filename
    import os
    import uuid as uuid_module

    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '이미지가 없습니다.'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'success': False, 'message': '유효하지 않은 파일입니다.'}), 400

    # 파일 형식 확인
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        return jsonify({'success': False, 'message': '이미지 파일만 업로드 가능합니다.'}), 400

    # 파일 저장
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'teacher_board', 'images')
    os.makedirs(upload_folder, exist_ok=True)

    stored_filename = f"{uuid_module.uuid4().hex}{ext}"
    file_path = os.path.join(upload_folder, stored_filename)
    file.save(file_path)

    # URL 생성
    image_url = f"/uploads/teacher_board/images/{stored_filename}"

    return jsonify({
        'success': True,
        'url': image_url,
        'filename': stored_filename
    })


# ==================== 공지사항 ====================

@teacher_bp.route('/announcements')
@login_required
@requires_role('teacher', 'admin')
def announcements():
    """공지사항 목록"""
    # 강사에게 표시할 공지사항 조회
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
            if 'all' in target_roles or 'teacher' in target_roles:
                visible_announcements.append(announcement)

    # 읽음 상태 추가
    announcements_with_status = []
    for announcement in visible_announcements:
        is_read = announcement.is_read_by(current_user.user_id)
        announcements_with_status.append({
            'announcement': announcement,
            'is_read': is_read
        })

    return render_template('teacher/announcements.html',
                         announcements=announcements_with_status)


@teacher_bp.route('/announcements/<announcement_id>')
@login_required
@requires_role('teacher', 'admin')
def view_announcement(announcement_id):
    """공지사항 상세"""
    announcement = Announcement.query.get_or_404(announcement_id)

    # 권한 확인
    if not announcement.is_active:
        flash('해당 공지사항을 볼 수 없습니다.', 'error')
        return redirect(url_for('teacher.announcements'))

    target_roles = announcement.target_roles_list
    if 'all' not in target_roles and 'teacher' not in target_roles:
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.announcements'))

    # 읽음 처리
    announcement.mark_as_read_by(current_user.user_id)
    db.session.commit()

    return render_template('teacher/view_announcement.html',
                         announcement=announcement)


# ==================== 클래스 게시판 ====================

@teacher_bp.route('/class-board')
@login_required
@requires_role('teacher', 'admin')
def class_board():
    """내 수업 목록 (클래스 게시판용)"""
    # 내가 담당하는 수업 목록
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id, status='active')\
        .order_by(Course.start_date.desc()).all()

    # 각 수업별 게시글 통계
    courses_with_stats = []
    for course in my_courses:
        post_count = ClassBoardPost.query.filter_by(course_id=course.course_id).count()
        latest_post = ClassBoardPost.query.filter_by(
            course_id=course.course_id
        ).order_by(ClassBoardPost.created_at.desc()).first()

        courses_with_stats.append({
            'course': course,
            'post_count': post_count,
            'latest_post': latest_post
        })

    return render_template('teacher/class_board.html',
                         courses_with_stats=courses_with_stats)


@teacher_bp.route('/class-board/<course_id>')
@login_required
@requires_role('teacher', 'admin')
def class_board_posts(course_id):
    """수업 게시판 게시글 목록"""
    course = Course.query.get_or_404(course_id)

    # 권한 확인 (담당 강사만)
    if course.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board'))

    # 게시글 목록 조회 (공지사항 고정 후 최신순)
    posts = ClassBoardPost.query.filter_by(
        course_id=course_id
    ).order_by(
        ClassBoardPost.is_pinned.desc(),
        ClassBoardPost.created_at.desc()
    ).all()

    return render_template('teacher/class_board_posts.html',
                         course=course,
                         posts=posts)


@teacher_bp.route('/class-board/<course_id>/new', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def create_class_board_post(course_id):
    """게시글 작성"""
    course = Course.query.get_or_404(course_id)

    # 권한 확인
    if course.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'notice')
        is_pinned = request.form.get('is_pinned') == 'on'
        is_notice = request.form.get('is_notice') == 'on'

        if not title or not content:
            flash('제목과 내용을 입력하세요.', 'error')
            return render_template('teacher/class_board_form.html',
                                 course=course,
                                 is_edit=False)

        # 게시글 생성
        post = ClassBoardPost(
            course_id=course_id,
            author_id=current_user.user_id,
            title=title,
            content=content,
            post_type=post_type,
            is_pinned=is_pinned,
            is_notice=is_notice
        )
        db.session.add(post)
        db.session.flush()  # post_id 확보

        # 이미지 업로드 처리 (최대 10장)
        from app.utils.image_utils import save_post_images
        img_files = request.files.getlist('images')
        for img in save_post_images(img_files, 'class_board', post.post_id, current_user.user_id):
            db.session.add(img)

        db.session.commit()

        flash('게시글이 등록되었습니다.', 'success')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post.post_id))

    return render_template('teacher/class_board_form.html',
                         course=course,
                         is_edit=False,
                         images=[])


@teacher_bp.route('/class-board/<course_id>/<post_id>')
@login_required
@requires_role('teacher', 'admin')
def class_board_post_detail(course_id, post_id):
    """게시글 상세"""
    course = Course.query.get_or_404(course_id)
    post = ClassBoardPost.query.get_or_404(post_id)

    # 권한 확인
    if course.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board'))

    # 조회수 증가 (본인 글 제외)
    if post.author_id != current_user.user_id:
        post.view_count += 1
        db.session.commit()

    from app.utils.image_utils import get_post_images
    images = get_post_images('class_board', post.post_id)
    return render_template('teacher/class_board_post_detail.html',
                         course=course,
                         post=post,
                         images=images)


@teacher_bp.route('/class-board/<course_id>/<post_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def edit_class_board_post(course_id, post_id):
    """게시글 수정"""
    course = Course.query.get_or_404(course_id)
    post = ClassBoardPost.query.get_or_404(post_id)

    # 수정 권한 확인
    if not post.can_edit(current_user):
        flash('수정 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'notice')
        is_pinned = request.form.get('is_pinned') == 'on'
        is_notice = request.form.get('is_notice') == 'on'

        if not title or not content:
            flash('제목과 내용을 입력하세요.', 'error')
            return render_template('teacher/class_board_form.html',
                                 course=course,
                                 post=post,
                                 is_edit=True)

        post.title = title
        post.content = content
        post.post_type = post_type
        post.is_pinned = is_pinned
        post.is_notice = is_notice
        post.updated_at = datetime.utcnow()

        # 이미지 삭제 처리
        from app.models.post_image import PostImage
        from app.utils.image_utils import delete_post_image, save_post_images
        delete_ids = request.form.getlist('delete_images')
        for img_id in delete_ids:
            img = PostImage.query.get(img_id)
            if img and img.post_id == post.post_id:
                delete_post_image(img)

        # 새 이미지 업로드
        existing_count = PostImage.query.filter_by(board_type='class_board', post_id=post.post_id).count()
        img_files = request.files.getlist('images')
        for img in save_post_images(img_files, 'class_board', post.post_id, current_user.user_id, existing_count):
            db.session.add(img)

        db.session.commit()

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    from app.utils.image_utils import get_post_images
    images = get_post_images('class_board', post.post_id)
    return render_template('teacher/class_board_form.html',
                         course=course,
                         post=post,
                         is_edit=True,
                         images=images)


@teacher_bp.route('/class-board/<course_id>/<post_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_class_board_post(course_id, post_id):
    """게시글 삭제"""
    post = ClassBoardPost.query.get_or_404(post_id)

    # 삭제 권한 확인
    if not post.can_delete(current_user):
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    db.session.delete(post)
    db.session.commit()

    flash('게시글이 삭제되었습니다.', 'info')
    return redirect(url_for('teacher.class_board_posts', course_id=course_id))


@teacher_bp.route('/class-board/<course_id>/<post_id>/comment', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def add_class_board_comment(course_id, post_id):
    """댓글 작성"""
    post = ClassBoardPost.query.get_or_404(post_id)
    course = Course.query.get_or_404(course_id)

    # 권한 확인
    if course.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post_id))

    content = request.form.get('content', '').strip()

    if not content:
        flash('댓글 내용을 입력하세요.', 'error')
        return redirect(url_for('teacher.class_board_post_detail',
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
    return redirect(url_for('teacher.class_board_post_detail',
                          course_id=course_id,
                          post_id=post_id))


@teacher_bp.route('/class-board/comment/<comment_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_class_board_comment(comment_id):
    """댓글 삭제"""
    comment = ClassBoardComment.query.get_or_404(comment_id)
    post = comment.post
    course_id = post.course_id

    # 삭제 권한 확인
    if not comment.can_delete(current_user):
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('teacher.class_board_post_detail',
                              course_id=course_id,
                              post_id=post.post_id))

    db.session.delete(comment)

    # 댓글 수 감소
    post.comment_count = max(0, post.comment_count - 1)
    db.session.commit()

    flash('댓글이 삭제되었습니다.', 'info')
    return redirect(url_for('teacher.class_board_post_detail',
                          course_id=course_id,
                          post_id=post.post_id))


# ==================== 데이터 내보내기 ====================

@teacher_bp.route('/export/my-students')
@login_required
@requires_role('teacher', 'admin')
def export_my_students():
    """내 학생 목록 Excel 내보내기"""
    from app.utils.export_utils import create_excel_workbook, create_excel_response, add_title_row, add_info_row, style_header_row, style_data_rows, auto_adjust_column_width

    # 내가 담당하는 수업의 학생들
    my_courses = Course.query.filter_by(
        teacher_id=current_user.user_id,
        status='active'
    ).all()

    student_data = {}  # student_id를 key로 사용하여 중복 제거

    for course in my_courses:
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.course_id,
            status='active'
        ).all()

        for enrollment in enrollments:
            student = enrollment.student
            if student.student_id not in student_data:
                student_data[student.student_id] = {
                    'student': student,
                    'courses': [],
                    'attendance_rate': 0,
                    'total_sessions': 0,
                    'attended_sessions': 0
                }

            student_data[student.student_id]['courses'].append(course.course_name)
            student_data[student.student_id]['total_sessions'] += enrollment.course.total_sessions
            student_data[student.student_id]['attended_sessions'] += enrollment.attended_sessions

    # 출석률 계산
    for student_id in student_data:
        data = student_data[student_id]
        if data['total_sessions'] > 0:
            data['attendance_rate'] = (data['attended_sessions'] / data['total_sessions']) * 100

    wb, ws = create_excel_workbook("내 학생 목록")

    # 제목
    add_title_row(ws, f"{current_user.name} 강사 - 담당 학생 목록", 6)
    add_info_row(ws, f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", 2)

    # 헤더
    headers = ['번호', '이름', '학년', '등급', '수강 수업', '출석률']
    ws.append([])
    ws.append(headers)

    style_header_row(ws, row_num=4, column_count=len(headers))

    # 데이터
    for idx, (student_id, data) in enumerate(sorted(student_data.items(), key=lambda x: x[1]['student'].name), start=1):
        student = data['student']
        ws.append([
            idx,
            student.name,
            student.grade or '-',
            student.tier or '-',
            ', '.join(data['courses'][:3]) + ('...' if len(data['courses']) > 3 else ''),
            f"{data['attendance_rate']:.1f}%"
        ])

    style_data_rows(ws, start_row=5, column_count=len(headers))
    auto_adjust_column_width(ws)

    return create_excel_response(wb, "내학생목록")


@teacher_bp.route('/export/course-attendance/<course_id>')
@login_required
@requires_role('teacher', 'admin')
def export_course_attendance(course_id):
    """수업별 출석부 Excel 내보내기"""
    from app.utils.export_utils import create_excel_workbook, create_excel_response, add_title_row, add_info_row, style_header_row, style_data_rows, auto_adjust_column_width

    course = Course.query.get_or_404(course_id)

    # 권한 확인
    if course.teacher_id != current_user.user_id and not current_user.role == 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.courses'))

    # 수업 세션 및 출석 데이터
    sessions = CourseSession.query.filter_by(
        course_id=course_id
    ).order_by(CourseSession.session_date).all()

    enrollments = CourseEnrollment.query.filter_by(
        course_id=course_id,
        status='active'
    ).order_by(Student.name).join(Student).all()

    wb, ws = create_excel_workbook("출석부")

    # 제목
    add_title_row(ws, f"{course.course_name} 출석부", len(sessions) + 3)
    add_info_row(ws, f"강사: {course.teacher.name} | 생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", 2)

    # 헤더 (학생명 + 각 세션 날짜)
    headers = ['번호', '학생명', '출석률']
    for session in sessions:
        headers.append(session.session_date.strftime('%m/%d'))

    ws.append([])
    ws.append(headers)
    style_header_row(ws, row_num=4, column_count=len(headers))

    # 데이터 (학생별 출석 현황)
    for idx, enrollment in enumerate(enrollments, start=1):
        student = enrollment.student
        row_data = [idx, student.name, f"{enrollment.attendance_rate:.1f}%"]

        for session in sessions:
            attendance = Attendance.query.filter_by(
                enrollment_id=enrollment.enrollment_id,
                session_id=session.session_id
            ).first()

            if attendance:
                status_symbol = {
                    'present': 'O',
                    'late': '△',
                    'absent': 'X',
                    'excused': '결'
                }.get(attendance.status, '-')
                row_data.append(status_symbol)
            else:
                row_data.append('-')

        ws.append(row_data)

    style_data_rows(ws, start_row=5, column_count=len(headers))
    auto_adjust_column_width(ws)

    return create_excel_response(wb, f"{course.course_name}_출석부")


@teacher_bp.route('/export/student-report/<student_id>')
@login_required
@requires_role('teacher', 'admin')
def export_student_report(student_id):
    """학생 종합 리포트 Excel 내보내기"""
    from app.utils.export_utils import export_student_report_to_excel
    from app.models.essay import Essay

    student = Student.query.get_or_404(student_id)

    # 내가 담당하는 학생인지 확인
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id).all()
    my_course_ids = [c.course_id for c in my_courses]

    enrollments = CourseEnrollment.query.filter(
        CourseEnrollment.student_id == student_id,
        CourseEnrollment.course_id.in_(my_course_ids)
    ).all()

    if not enrollments and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.students'))

    # 전체 enrollment
    all_enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student_id
    ).order_by(Essay.created_at.desc()).all()

    # 출석 통계
    total_sessions = sum(e.total_sessions for e in all_enrollments)
    attended = sum(e.attended_sessions for e in all_enrollments)
    late = sum(e.late_sessions for e in all_enrollments)
    absent = sum(e.absent_sessions for e in all_enrollments)
    attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 0

    attendance_stats = {
        'total_sessions': total_sessions,
        'present': attended,
        'late': late,
        'absent': absent,
        'attendance_rate': attendance_rate
    }

    return export_student_report_to_excel(student, all_enrollments, essays, attendance_stats)


# ==================== PDF 내보내기 ====================

@teacher_bp.route('/export/student-report-pdf/<student_id>')
@login_required
@requires_role('teacher', 'admin')
def export_student_report_pdf(student_id):
    """학생 성적표 PDF 내보내기"""
    from app.utils.pdf_utils import generate_student_report_card_pdf
    from app.models.essay import Essay

    student = Student.query.get_or_404(student_id)

    # 내가 담당하는 학생인지 확인
    my_courses = Course.query.filter_by(teacher_id=current_user.user_id).all()
    my_course_ids = [c.course_id for c in my_courses]

    enrollments = CourseEnrollment.query.filter(
        CourseEnrollment.student_id == student_id,
        CourseEnrollment.course_id.in_(my_course_ids)
    ).all()

    if not enrollments and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('teacher.students'))

    # 전체 enrollment
    all_enrollments = CourseEnrollment.query.filter_by(
        student_id=student_id,
        status='active'
    ).all()

    # 첨삭 기록
    essays = Essay.query.filter_by(
        student_id=student_id
    ).order_by(Essay.created_at.desc()).all()

    # 출석 통계
    total_sessions = sum(e.total_sessions for e in all_enrollments)
    attended = sum(e.attended_sessions for e in all_enrollments)
    late = sum(e.late_sessions for e in all_enrollments)
    absent = sum(e.absent_sessions for e in all_enrollments)
    attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 0

    attendance_stats = {
        'total_sessions': total_sessions,
        'present': attended,
        'late': late,
        'absent': absent,
        'attendance_rate': attendance_rate
    }

    return generate_student_report_card_pdf(student, all_enrollments, essays, attendance_stats)


# ============================================================================
# 독서 논술 MBTI - 교사 포털
# ============================================================================

@teacher_bp.route('/reading-mbti')
@login_required
@requires_role('teacher', 'admin')
def reading_mbti():
    """담당 학생들의 독서 논술 MBTI 결과 조회"""
    from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType
    from sqlalchemy import func, desc

    # 내가 담당하는 학생들
    my_students = Student.query.filter_by(teacher_id=current_user.user_id).all()
    student_ids = [s.student_id for s in my_students]

    # 학생들의 최근 결과
    results = ReadingMBTIResult.query.filter(
        ReadingMBTIResult.student_id.in_(student_ids)
    ).order_by(desc(ReadingMBTIResult.created_at)).all()

    # 학생별 최신 결과만 필터링
    latest_results = {}
    for result in results:
        if result.student_id not in latest_results:
            latest_results[result.student_id] = result

    # 유형별 통계
    type_distribution = {}
    for result in latest_results.values():
        type_name = result.mbti_type.type_name
        if type_name not in type_distribution:
            type_distribution[type_name] = {
                'count': 0,
                'students': [],
                'type_code': result.mbti_type.type_code
            }
        type_distribution[type_name]['count'] += 1
        type_distribution[type_name]['students'].append(result.student)

    # 차원별 통계 (새로운 3단계 수준 체계)
    read_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
    speech_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
    write_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}

    for result in latest_results.values():
        read_distribution[result.read_type] += 1
        speech_distribution[result.speech_type] += 1
        write_distribution[result.write_type] += 1

    return render_template('teacher/reading_mbti/index.html',
                           my_students=my_students,
                           latest_results=latest_results,
                           type_distribution=type_distribution,
                           read_distribution=read_distribution,
                           speech_distribution=speech_distribution,
                           write_distribution=write_distribution,
                           total_tested=len(latest_results))


@teacher_bp.route('/reading-mbti/student/<string:student_id>')
@login_required
@requires_role('teacher', 'admin')
def view_student_mbti(student_id):
    """특정 학생의 MBTI 결과 상세 보기"""
    from app.models.reading_mbti import ReadingMBTIResult

    student = Student.query.get_or_404(student_id)

    # 담당 학생인지 확인
    if student.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('담당 학생만 확인할 수 있습니다.', 'error')
        return redirect(url_for('teacher.reading_mbti'))

    # 학생의 모든 결과 (최신순)
    results = ReadingMBTIResult.query.filter_by(
        student_id=student_id
    ).order_by(ReadingMBTIResult.created_at.desc()).all()

    if not results:
        flash('이 학생은 아직 테스트를 응시하지 않았습니다.', 'warning')
        return redirect(url_for('teacher.reading_mbti'))

    latest_result = results[0]

    return render_template('teacher/reading_mbti/student_detail.html',
                           student=student,
                           latest_result=latest_result,
                           all_results=results)


@teacher_bp.route('/reading-mbti/course/<int:course_id>')
@login_required
@requires_role('teacher', 'admin')
def course_mbti_stats(course_id):
    """수업별 MBTI 통계"""
    from app.models.reading_mbti import ReadingMBTIResult

    course = Course.query.get_or_404(course_id)

    # 강사 권한 확인
    if course.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('담당 수업만 확인할 수 있습니다.', 'error')
        return redirect(url_for('teacher.reading_mbti'))

    # 수업 수강생들
    enrollments = CourseEnrollment.query.filter_by(course_id=course_id).all()
    student_ids = [e.student_id for e in enrollments]

    # 수강생들의 최근 결과
    results = ReadingMBTIResult.query.filter(
        ReadingMBTIResult.student_id.in_(student_ids)
    ).order_by(ReadingMBTIResult.created_at.desc()).all()

    # 학생별 최신 결과만
    latest_results = {}
    for result in results:
        if result.student_id not in latest_results:
            latest_results[result.student_id] = result

    # 유형별 분포
    type_distribution = {}
    for result in latest_results.values():
        type_name = result.mbti_type.type_name
        if type_name not in type_distribution:
            type_distribution[type_name] = {
                'count': 0,
                'students': [],
                'type_code': result.mbti_type.type_code
            }
        type_distribution[type_name]['count'] += 1
        type_distribution[type_name]['students'].append(result.student)

    # 차원별 통계 (새로운 3단계 수준 체계)
    read_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
    speech_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
    write_distribution = {'beginner': 0, 'intermediate': 0, 'advanced': 0}

    for result in latest_results.values():
        read_distribution[result.read_type] += 1
        speech_distribution[result.speech_type] += 1
        write_distribution[result.write_type] += 1

    return render_template('teacher/reading_mbti/course_stats.html',
                           course=course,
                           enrollments=enrollments,
                           latest_results=latest_results,
                           type_distribution=type_distribution,
                           read_distribution=read_distribution,
                           speech_distribution=speech_distribution,
                           write_distribution=write_distribution,
                           total_students=len(enrollments),
                           tested_students=len(latest_results))


# ==================== 학생 프로필 조회 (강사용) ====================

@teacher_bp.route('/students/<student_id>/profile')
@login_required
@requires_role('teacher', 'admin', 'master_admin')
def student_profile(student_id):
    """학생 프로필 조회 (강사용 - 자신의 수업 학생만)"""
    from app.models.student_profile import StudentProfile
    from app.models.consultation import ConsultationRecord
    from app.models.course import CourseEnrollment, Course

    student = Student.query.get_or_404(student_id)
    profile = StudentProfile.query.filter_by(student_id=student_id).first()

    # 현재 강사가 이 학생을 가르치는지 확인
    if current_user.role not in ['admin', 'master_admin']:
        # 강사는 자신의 수업에 등록된 학생만 볼 수 있음
        is_my_student = db.session.query(CourseEnrollment).join(Course).filter(
            Course.teacher_id == current_user.user_id,
            CourseEnrollment.student_id == student_id
        ).first()

        if not is_my_student:
            flash('접근 권한이 없습니다.', 'danger')
            return redirect(url_for('teacher.index'))

    # 상담 이력 조회 (본인 작성 + 공유받은 것만)
    consultations = ConsultationRecord.query.filter_by(student_id=student_id)\
        .filter(
            (ConsultationRecord.counselor_id == current_user.user_id) |
            (ConsultationRecord.reference_teachers.like(f'%{current_user.user_id}%'))
        )\
        .order_by(ConsultationRecord.consultation_date.desc())\
        .all()

    return render_template('teacher/student_profile.html',
                         student=student,
                         profile=profile,
                         consultations=consultations)


# ==================== ACE 평가 시스템 ====================

@teacher_bp.route('/ace-evaluation')
@login_required
@requires_role('teacher', 'admin')
def ace_evaluation():
    """ACE 평가 시스템 메인 페이지 (대시보드)"""
    from app.models.ace_evaluation import WeeklyEvaluation, AceEvaluation, ACE_AXES
    from sqlalchemy import func

    # 선택된 학생 ID
    selected_student_id = request.args.get('student_id', type=str)

    # 내가 담당하는 학생 목록
    my_students = Student.query.join(CourseEnrollment).join(Course).filter(
        Course.teacher_id == current_user.user_id
    ).distinct().order_by(Student.name).all()

    # 학생이 없으면 빈 대시보드 표시
    if not my_students:
        return render_template('teacher/ace_evaluation/index.html',
                             students=[],
                             selected_student=None,
                             weekly_evals=[],
                             ace_evals=[],
                             ace_axes=ACE_AXES)

    # 선택된 학생 또는 첫 번째 학생
    if selected_student_id:
        selected_student = next((s for s in my_students if s.student_id == selected_student_id), my_students[0])
    else:
        selected_student = None

    # 선택된 학생의 평가 데이터
    weekly_evals = []
    ace_evals = []

    if selected_student:
        weekly_evals = WeeklyEvaluation.query.filter_by(
            student_id=selected_student.student_id
        ).order_by(WeeklyEvaluation.eval_date.desc()).limit(10).all()

        ace_evals = AceEvaluation.query.filter_by(
            student_id=selected_student.student_id
        ).order_by(AceEvaluation.year.desc(), AceEvaluation.quarter.desc()).all()

    return render_template('teacher/ace_evaluation/index.html',
                         students=my_students,
                         selected_student=selected_student,
                         weekly_evals=weekly_evals,
                         ace_evals=ace_evals,
                         ace_axes=ACE_AXES)


@teacher_bp.route('/ace-evaluation/weekly', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def ace_weekly():
    """주차 평가 입력 및 관리"""
    from app.models.ace_evaluation import WeeklyEvaluation, WEEKLY_GRADES, CLASS_TYPES, TEACHER_COMMENTS
    from datetime import date

    # 내가 담당하는 학생 목록
    my_students = Student.query.join(CourseEnrollment).join(Course).filter(
        Course.teacher_id == current_user.user_id
    ).distinct().order_by(Student.name).all()

    if request.method == 'POST':
        try:
            student_id = request.form.get('student_id')
            eval_date = datetime.strptime(request.form.get('eval_date'), '%Y-%m-%d').date()
            week_number = int(request.form.get('week_number', 1))
            book_title = request.form.get('book_title', '')
            class_type = request.form.get('class_type', '1:1')
            score = int(request.form.get('score', 0))
            grade = request.form.get('grade', 'B0')
            participation_score = int(request.form.get('participation_score', 3))
            understanding_score = int(request.form.get('understanding_score', 3))
            comment = request.form.get('comment', '')

            # 새 주차 평가 생성
            weekly_eval = WeeklyEvaluation(
                student_id=student_id,
                teacher_id=current_user.user_id,
                eval_date=eval_date,
                week_number=week_number,
                book_title=book_title,
                class_type=class_type,
                score=score,
                grade=grade,
                participation_score=participation_score,
                understanding_score=understanding_score,
                comment=comment
            )

            db.session.add(weekly_eval)
            db.session.commit()

            # 주간 평가 등록 → 학부모 Push
            try:
                from app.models.notification import Notification
                from app.utils.push_utils import send_push_to_user
                student_obj = Student.query.get(student_id)
                if student_obj:
                    grade_label = weekly_eval.grade or ''
                    msg = f'{student_obj.name} 학생의 {eval_date.strftime("%m/%d")} 주차 평가가 등록되었습니다. (등급: {grade_label})'
                    parents = ParentStudent.query.filter_by(
                        student_id=student_id, is_active=True
                    ).all()
                    for ps in parents:
                        db.session.add(Notification(
                            user_id=ps.parent_id,
                            notification_type='weekly_eval',
                            title=f'{student_obj.name} 주간 평가 등록',
                            message=msg,
                            link_url='/parent/ace-evaluation'
                        ))
                        send_push_to_user(
                            user_id=ps.parent_id,
                            title=f'{student_obj.name} 주간 평가 등록',
                            body=msg,
                            url='/parent/ace-evaluation'
                        )
                    db.session.commit()
            except Exception as e:
                current_app.logger.warning(f'[Push] 주간 평가 알림 오류: {e}')

            flash('주차 평가가 저장되었습니다.', 'success')
            return redirect(url_for('teacher.ace_weekly'))

        except Exception as e:
            db.session.rollback()
            flash(f'저장 중 오류가 발생했습니다: {str(e)}', 'danger')

    # 최근 평가 이력 (최근 20개)
    weekly_evals = WeeklyEvaluation.query.filter_by(
        teacher_id=current_user.user_id
    ).order_by(WeeklyEvaluation.eval_date.desc()).limit(20).all()

    return render_template('teacher/ace_evaluation/weekly.html',
                         students=my_students,
                         weekly_grades=WEEKLY_GRADES,
                         class_types=CLASS_TYPES,
                         teacher_comments=TEACHER_COMMENTS,
                         weekly_evals=weekly_evals,
                         today=date.today())


@teacher_bp.route('/ace-evaluation/weekly/<int:eval_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def ace_weekly_edit(eval_id):
    """주차 평가 수정"""
    from app.models.ace_evaluation import WeeklyEvaluation, WEEKLY_GRADES, CLASS_TYPES, TEACHER_COMMENTS
    from datetime import date

    weekly_eval = WeeklyEvaluation.query.get_or_404(eval_id)

    # 권한 확인 (작성자 또는 관리자만)
    if weekly_eval.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('수정 권한이 없습니다.', 'danger')
        return redirect(url_for('teacher.ace_weekly'))

    if request.method == 'POST':
        try:
            weekly_eval.eval_date = datetime.strptime(request.form.get('eval_date'), '%Y-%m-%d').date()
            weekly_eval.week_number = int(request.form.get('week_number', 1))
            weekly_eval.book_title = request.form.get('book_title', '')
            weekly_eval.class_type = request.form.get('class_type', '1:1')
            weekly_eval.score = int(request.form.get('score', 0))
            weekly_eval.grade = request.form.get('grade', 'B0')
            weekly_eval.participation_score = int(request.form.get('participation_score', 3))
            weekly_eval.understanding_score = int(request.form.get('understanding_score', 3))
            weekly_eval.comment = request.form.get('comment', '')

            db.session.commit()
            flash('주차 평가가 수정되었습니다.', 'success')
            return redirect(url_for('teacher.ace_weekly'))

        except Exception as e:
            db.session.rollback()
            flash(f'수정 중 오류가 발생했습니다: {str(e)}', 'danger')

    return render_template('teacher/ace_evaluation/weekly_edit.html',
                         eval=weekly_eval,
                         weekly_grades=WEEKLY_GRADES,
                         class_types=CLASS_TYPES,
                         teacher_comments=TEACHER_COMMENTS,
                         today=date.today())


@teacher_bp.route('/ace-evaluation/weekly/<int:eval_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def ace_weekly_delete(eval_id):
    """주차 평가 삭제"""
    from app.models.ace_evaluation import WeeklyEvaluation

    weekly_eval = WeeklyEvaluation.query.get_or_404(eval_id)

    # 권한 확인 (작성자 또는 관리자만)
    if weekly_eval.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('teacher.ace_weekly'))

    try:
        db.session.delete(weekly_eval)
        db.session.commit()
        flash('주차 평가가 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'danger')

    return redirect(url_for('teacher.ace_weekly'))


@teacher_bp.route('/ace-evaluation/weekly/report/<student_id>')
@login_required
@requires_role('teacher', 'admin')
def ace_weekly_report(student_id):
    """학생별 주차평가 리포트"""
    from app.models.ace_evaluation import WeeklyEvaluation
    from datetime import date, timedelta
    from sqlalchemy import func

    # 학생 정보 조회
    student = Student.query.get_or_404(student_id)

    # 권한 확인 (내가 담당하는 학생인지)
    if current_user.role != 'admin':
        is_my_student = CourseEnrollment.query.join(Course).filter(
            CourseEnrollment.student_id == student_id,
            Course.teacher_id == current_user.user_id
        ).first()
        if not is_my_student:
            flash('해당 학생의 리포트를 볼 권한이 없습니다.', 'error')
            return redirect(url_for('teacher.students'))

    # 기간 필터링
    period = request.args.get('period', 'all')  # all, 3months, 6months, 1year

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

    # 최근 성장률 계산 (최근 5개 vs 이전 5개)
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

    return render_template('teacher/ace_evaluation/weekly_report.html',
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


@teacher_bp.route('/ace-evaluation/weekly/dashboard')
@login_required
@requires_role('teacher', 'admin')
def ace_weekly_dashboard():
    """전체 학생 주차평가 비교 대시보드"""
    from app.models.ace_evaluation import WeeklyEvaluation
    from sqlalchemy import func
    from datetime import date, timedelta

    # 내가 담당하는 학생 목록
    my_students = Student.query.join(CourseEnrollment).join(Course).filter(
        Course.teacher_id == current_user.user_id
    ).distinct().all()

    # 각 학생별 통계 계산
    student_stats = []

    for student in my_students:
        # 전체 평가
        all_evals = WeeklyEvaluation.query.filter_by(student_id=student.student_id).all()

        # 최근 1개월 평가
        one_month_ago = date.today() - timedelta(days=30)
        recent_evals = WeeklyEvaluation.query.filter(
            WeeklyEvaluation.student_id == student.student_id,
            WeeklyEvaluation.eval_date >= one_month_ago
        ).all()

        if all_evals:
            avg_score = round(sum(e.score for e in all_evals) / len(all_evals), 1)
            avg_participation = round(sum(e.participation_score for e in all_evals) / len(all_evals), 1)
            avg_understanding = round(sum(e.understanding_score for e in all_evals) / len(all_evals), 1)

            # 최근 성장률 (최근 3개 vs 이전 3개)
            growth_rate = 0
            if len(all_evals) >= 6:
                recent_3 = all_evals[-3:]
                previous_3 = all_evals[-6:-3]
                recent_avg = sum(e.score for e in recent_3) / 3
                previous_avg = sum(e.score for e in previous_3) / 3
                growth_rate = round(((recent_avg - previous_avg) / previous_avg) * 100, 1) if previous_avg > 0 else 0

            student_stats.append({
                'student': student,
                'eval_count': len(all_evals),
                'recent_eval_count': len(recent_evals),
                'avg_score': avg_score,
                'avg_participation': avg_participation,
                'avg_understanding': avg_understanding,
                'growth_rate': growth_rate
            })

    # 성장률 순으로 정렬
    student_stats.sort(key=lambda x: x['growth_rate'], reverse=True)

    return render_template('teacher/ace_evaluation/weekly_dashboard.html',
                         student_stats=student_stats)


@teacher_bp.route('/ace-evaluation/ace', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def ace_quarterly():
    """ACE 분기 평가 입력 및 관리"""
    from app.models.ace_evaluation import (AceEvaluation, ACE_AXES, ACE_ALL_ITEMS,
                                          GRADE_LABELS, QUARTERS)
    from datetime import date

    # 내가 담당하는 학생 목록
    my_students = Student.query.join(CourseEnrollment).join(Course).filter(
        Course.teacher_id == current_user.user_id
    ).distinct().order_by(Student.name).all()

    # URL 파라미터에서 선택된 학생 ID 가져오기
    selected_student_id = request.args.get('student_id', type=str)

    if request.method == 'POST':
        try:
            student_id = request.form.get('student_id')
            year = int(request.form.get('year', date.today().year))
            quarter = request.form.get('quarter')
            comment = request.form.get('comment', '')

            # 15개 항목 점수 수집
            scores = {}
            for item_name in ACE_ALL_ITEMS:
                # form field name: 'score_사실, 분석적 독해' 형식
                field_name = f'score_{item_name}'
                scores[item_name] = request.form.get(field_name, '중')

            # 새 ACE 평가 생성
            ace_eval = AceEvaluation(
                student_id=student_id,
                teacher_id=current_user.user_id,
                year=year,
                quarter=quarter,
                comment=comment
            )
            ace_eval.scores = scores  # setter를 통해 JSON 저장

            db.session.add(ace_eval)
            db.session.commit()

            flash('ACE 분기 평가가 저장되었습니다.', 'success')
            return redirect(url_for('teacher.ace_quarterly'))

        except Exception as e:
            db.session.rollback()
            flash(f'저장 중 오류가 발생했습니다: {str(e)}', 'danger')

    # 최근 평가 이력
    ace_evals = AceEvaluation.query.filter_by(
        teacher_id=current_user.user_id
    ).order_by(AceEvaluation.year.desc(), AceEvaluation.quarter.desc()).limit(20).all()

    return render_template('teacher/ace_evaluation/ace.html',
                         students=my_students,
                         ace_axes=ACE_AXES,
                         grade_labels=GRADE_LABELS,
                         quarters=QUARTERS,
                         ace_evals=ace_evals,
                         current_year=date.today().year,
                         selected_student_id=selected_student_id)


@teacher_bp.route('/ace-evaluation/ace/<int:eval_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def ace_quarterly_delete(eval_id):
    """ACE 분기 평가 삭제"""
    from app.models.ace_evaluation import AceEvaluation

    ace_eval = AceEvaluation.query.get_or_404(eval_id)

    # 권한 확인 (작성자 또는 관리자만)
    if ace_eval.teacher_id != current_user.user_id and current_user.role != 'admin':
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('teacher.ace_quarterly'))

    try:
        db.session.delete(ace_eval)
        db.session.commit()
        flash('ACE 분기 평가가 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'danger')

    return redirect(url_for('teacher.ace_quarterly'))


@teacher_bp.route('/ace-evaluation/report/<student_id>')
@login_required
@requires_role('teacher', 'admin')
def ace_report(student_id):
    """학부모 리포트 (미리보기 및 출력)"""
    from app.models.ace_evaluation import WeeklyEvaluation, AceEvaluation, ACE_AXES

    student = Student.query.get_or_404(student_id)

    # 권한 확인 (담당 강사 또는 관리자만)
    if current_user.role not in ['admin', 'master_admin']:
        is_my_student = db.session.query(CourseEnrollment).join(Course).filter(
            Course.teacher_id == current_user.user_id,
            CourseEnrollment.student_id == student_id
        ).first()

        if not is_my_student:
            flash('접근 권한이 없습니다.', 'danger')
            return redirect(url_for('teacher.ace_evaluation'))

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


@teacher_bp.route('/help')
@login_required
@requires_role('teacher', 'admin')
def help_page():
    """강사 도움말"""
    return render_template('teacher/help.html')


@teacher_bp.route('/my-hours')
@login_required
@requires_role('teacher', 'admin')
def my_hours():
    """강사 본인 월별 시수 확인"""
    from datetime import date
    from app.utils.hours_calculator import build_teacher_monthly_data
    from app.models.teacher_hours import TeacherHoursCorrection

    year  = request.args.get('year',  date.today().year,  type=int)
    month = request.args.get('month', date.today().month, type=int)

    data = build_teacher_monthly_data(current_user.user_id, year, month)
    corrections = TeacherHoursCorrection.query.filter_by(
        teacher_id=current_user.user_id, year=year, month=month
    ).order_by(TeacherHoursCorrection.created_at).all()

    return render_template(
        'teacher/my_hours.html',
        data=data,
        corrections=corrections,
        year=year,
        month=month,
    )


@teacher_bp.route('/help/pdf')
@login_required
@requires_role('teacher', 'admin')
def help_pdf():
    """강사 도움말 PDF 다운로드"""
    from app.utils.pdf_utils import generate_teacher_manual_pdf
    return generate_teacher_manual_pdf()


# ─────────────────────────────────────────
# 학생 주의사항(경고) CRUD
# ─────────────────────────────────────────

@teacher_bp.route('/students/<student_id>/cautions/new', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def create_caution(student_id):
    """주의사항 등록"""
    student = Student.query.get_or_404(student_id)
    title    = request.form.get('title', '').strip()
    content  = request.form.get('content', '').strip()
    category = request.form.get('category', 'other')
    severity = request.form.get('severity', 'caution')
    if not title or not content:
        flash('제목과 내용을 모두 입력해주세요.', 'error')
        return redirect(url_for('teacher.student_detail', student_id=student_id))

    caution = StudentCaution(
        student_id=student_id,
        author_id=current_user.user_id,
        category=category,
        severity=severity,
        title=title,
        content=content,
    )
    db.session.add(caution)
    db.session.commit()
    flash('주의사항이 등록되었습니다.', 'success')
    return redirect(url_for('teacher.student_detail', student_id=student_id) + '#tab-caution')


@teacher_bp.route('/cautions/<int:caution_id>/resolve', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def resolve_caution(caution_id):
    """주의사항 해결 처리"""
    caution = StudentCaution.query.get_or_404(caution_id)
    note    = request.form.get('resolve_note', '').strip()
    caution.resolve(current_user.user_id, note)
    db.session.commit()
    flash('주의사항을 해결 처리했습니다.', 'success')
    return redirect(url_for('teacher.student_detail', student_id=caution.student_id) + '#tab-caution')


@teacher_bp.route('/cautions/<int:caution_id>/delete', methods=['POST'])
@login_required
@requires_role('teacher', 'admin')
def delete_caution(caution_id):
    """주의사항 삭제 (관리자만)"""
    if current_user.role not in ('admin', 'master_admin'):
        flash('관리자만 삭제할 수 있습니다.', 'error')
        caution = StudentCaution.query.get_or_404(caution_id)
        return redirect(url_for('teacher.student_detail', student_id=caution.student_id) + '#tab-caution')
    caution    = StudentCaution.query.get_or_404(caution_id)
    student_id = caution.student_id
    db.session.delete(caution)
    db.session.commit()
    flash('주의사항을 삭제했습니다.', 'success')
    return redirect(url_for('teacher.student_detail', student_id=student_id) + '#tab-caution')


@teacher_bp.route('/sms', methods=['GET', 'POST'])
@login_required
@requires_role('teacher', 'admin')
def teacher_sms():
    """강사 SMS/LMS 발송"""
    from app.models.message import Message, MessageRecipient
    import json

    # 이 강사의 수업에 등록된 학생 목록 (중복 제거)
    enrollments = CourseEnrollment.query.join(Course).filter(
        Course.teacher_id == current_user.user_id,
        Course.status == 'active',
        CourseEnrollment.status == 'active'
    ).all()

    student_ids_seen = set()
    students = []
    for enr in enrollments:
        if enr.student_id not in student_ids_seen:
            student_ids_seen.add(enr.student_id)
            if enr.student:
                students.append(enr.student)
    students.sort(key=lambda s: (s.grade or '', s.name or ''))

    # 학부모 목록 (위 학생들의 학부모만)
    parents_with_children = []
    seen_parent_ids = set()
    for student in students:
        relations = ParentStudent.query.filter_by(student_id=student.student_id, is_active=True).all()
        for rel in relations:
            if rel.parent and rel.parent_id not in seen_parent_ids and rel.parent.phone:
                seen_parent_ids.add(rel.parent_id)
                children = [r.student for r in ParentStudent.query.filter_by(
                    parent_id=rel.parent_id, is_active=True).all() if r.student]
                parents_with_children.append({'parent': rel.parent, 'children': children})

    # 강사의 수업 목록 (클래스 필터용)
    courses = Course.query.filter_by(
        teacher_id=current_user.user_id, status='active'
    ).order_by(Course.course_name).all()

    if request.method == 'POST':
        message_type = request.form.get('message_type', 'SMS')
        subject = request.form.get('subject', '').strip()
        content = request.form.get('content', '').strip()
        recipient_ids = request.form.getlist('recipients[]')
        recipient_role = request.form.get('recipient_role', 'student')  # student / parent
        notes = request.form.get('notes', '').strip()

        if not content:
            flash('메시지 내용을 입력해주세요.', 'error')
            return redirect(url_for('teacher.teacher_sms'))

        if message_type == 'LMS' and not subject:
            flash('LMS는 제목이 필요합니다.', 'error')
            return redirect(url_for('teacher.teacher_sms'))

        content_bytes = len(content.encode('utf-8'))
        if message_type == 'SMS' and content_bytes > 90:
            flash('SMS는 90바이트(한글 약 45자)까지 입력 가능합니다.', 'error')
            return redirect(url_for('teacher.teacher_sms'))
        elif message_type == 'LMS' and content_bytes > 2000:
            flash('LMS는 2000바이트(한글 약 1000자)까지 입력 가능합니다.', 'error')
            return redirect(url_for('teacher.teacher_sms'))

        # 수신자 데이터 수집
        recipients_data = []
        if recipient_role == 'parent':
            for parent_id in recipient_ids:
                parent = User.query.get(parent_id)
                if parent and parent.phone:
                    children = [r.student for r in ParentStudent.query.filter_by(
                        parent_id=parent_id, is_active=True).all() if r.student]
                    child_names = ', '.join(s.name for s in children)
                    recipients_data.append({
                        'student_id': None,
                        'name': f'{parent.name}({child_names})',
                        'phone': parent.phone
                    })
        else:
            for student_id in recipient_ids:
                student = Student.query.get(student_id)
                if student and student.phone:
                    recipients_data.append({
                        'student_id': student.student_id,
                        'name': student.name,
                        'phone': student.phone
                    })

        if not recipients_data:
            flash('수신자를 선택하거나 수신자의 전화번호를 확인해주세요.', 'error')
            return redirect(url_for('teacher.teacher_sms'))

        message = Message(
            sender_id=current_user.user_id,
            message_type=message_type,
            subject=subject if message_type == 'LMS' else None,
            content=content,
            recipient_type='group',
            recipients_json=json.dumps(recipients_data, ensure_ascii=False),
            total_recipients=len(recipients_data),
            notes=notes
        )
        db.session.add(message)
        db.session.flush()

        from app.utils.sms import send_sms_message as _send_sms
        success_count = 0
        failed_count = 0
        failed_names = []

        for rd in recipients_data:
            ok, reason = _send_sms(rd['phone'], content, title=subject if message_type == 'LMS' else None)
            if ok:
                success_count += 1
                r_status = 'sent'
                r_fail = None
            else:
                failed_count += 1
                r_status = 'failed'
                r_fail = reason
                failed_names.append(f"{rd['name']}({reason})")

            db.session.add(MessageRecipient(
                message_id=message.message_id,
                student_id=rd.get('student_id'),
                recipient_name=rd['name'],
                recipient_phone=rd['phone'],
                status=r_status,
                sent_at=datetime.utcnow() if ok else None,
                error_message=r_fail
            ))

        message.status = 'completed'
        message.sent_at = datetime.utcnow()
        message.success_count = success_count
        message.failed_count = failed_count
        db.session.commit()

        if failed_count > 0 and success_count == 0:
            flash(f'발송 실패: {", ".join(failed_names[:5])}', 'error')
        elif failed_count > 0:
            flash(f'{message_type} {success_count}건 발송 완료, {failed_count}건 실패', 'warning')
        else:
            flash(f'{message_type} {success_count}건 발송 완료!', 'success')
        return redirect(url_for('teacher.teacher_sms'))

    # 발송 이력 (최근 30건)
    history = Message.query.filter_by(sender_id=current_user.user_id)\
        .order_by(Message.created_at.desc()).limit(30).all()

    return render_template('teacher/send_sms.html',
                           students=students,
                           parents_with_children=parents_with_children,
                           courses=courses,
                           history=history)
