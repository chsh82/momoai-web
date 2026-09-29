# -*- coding: utf-8 -*-
"""상담 신청 라우트.

학부모 접수 -> 관리자 처리(접수 확인/내부 협의/일정 확정 또는 거절) ->
(실제 상담 후) teacher.create_consultation에서 상담 기록과 연결, 순서로
진행된다. 강사는 이 신청 건을 직접 승인/거절하지 않고, 관리자가 내부
협의로 요청했을 때만 기존 메신저(app.messages)로 회신한다.
"""
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from app.consultation_request import consultation_request_bp
from app.models import db, User, Student, ParentStudent, Notification
from app.models.consultation_request import ConsultationRequest, CATEGORY_CHOICES, MAKEUP_INDIVIDUAL_CATEGORY
from app.models.conversation import Conversation, ConversationMessage
from app.utils.decorators import requires_role


def _my_children():
    relations = ParentStudent.query.filter_by(
        parent_id=current_user.user_id, is_active=True
    ).all()
    return [pr.student for pr in relations if pr.student]


def _notify_admins_new_request(req):
    admins = User.query.filter(User.role_level <= 2, User.is_active == True).all()
    link = url_for('consultation_request.admin_detail', request_id=req.request_id)
    for admin in admins:
        db.session.add(Notification(
            user_id=admin.user_id,
            notification_type='consultation_request',
            title=f'📋 새 상담 신청: {req.student.display_name if req.student else ""}',
            message=f'{req.category} · {req.reason[:60]}',
            related_entity_type='consultation_request',
            related_entity_id=req.request_id,
            link_url=link,
        ))


def _notify_parent_response(req):
    if not req.requester_id:
        return
    if req.status == 'scheduled':
        title = '✅ 상담 일정이 확정되었습니다'
        message = f'{req.scheduled_date.strftime("%Y-%m-%d")} · {req.scheduled_note or ""}'
    elif req.status == 'rejected':
        title = '상담 신청이 반려되었습니다'
        message = req.reject_reason or ''
    else:
        return
    # create_notification()을 통해야 웹푸시도 함께 나간다 - 직접 db.session.add로
    # 만들면 알림함에만 쌓이고 실제 알림(푸시)은 안 가서 확인이 늦어진다.
    Notification.create_notification(
        user_id=req.requester_id,
        notification_type='consultation_request',
        title=title,
        message=message,
        related_entity_type='consultation_request',
        related_entity_id=req.request_id,
        link_url=url_for('consultation_request.detail', request_id=req.request_id),
    )


# ==================== 학부모 ====================

@consultation_request_bp.route('/')
@requires_role('parent', 'admin')
def index():
    """내 상담 신청 목록 (학부모)"""
    if current_user.role == 'parent':
        child_ids = [c.student_id for c in _my_children()]
        requests = ConsultationRequest.query.filter(
            ConsultationRequest.student_id.in_(child_ids)
        ).order_by(ConsultationRequest.created_at.desc()).all() if child_ids else []
    else:
        requests = ConsultationRequest.query.filter_by(
            requester_id=current_user.user_id
        ).order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('consultation_request/parent_list.html', requests=requests)


@consultation_request_bp.route('/new', methods=['GET', 'POST'])
@requires_role('parent', 'admin')
def new():
    """상담 신청서 작성 (학부모)"""
    children = _my_children()

    if request.method == 'POST':
        student_id = request.form.get('student_id', '')
        category = request.form.get('category', '')
        reason = request.form.get('reason', '').strip()
        preferred_date_raw = request.form.get('preferred_date', '').strip()
        preferred_note = request.form.get('preferred_note', '').strip()

        if student_id not in [c.student_id for c in children]:
            flash('자녀를 올바르게 선택해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))
        if category not in CATEGORY_CHOICES:
            flash('상담 분류를 선택해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))
        if not reason:
            flash('상담 사유를 입력해주세요.', 'error')
            return redirect(url_for('consultation_request.new'))

        preferred_date = None
        if preferred_date_raw:
            try:
                preferred_date = datetime.strptime(preferred_date_raw, '%Y-%m-%d').date()
            except ValueError:
                pass

        req = ConsultationRequest(
            student_id=student_id,
            requester_id=current_user.user_id,
            category=category,
            reason=reason,
            preferred_date=preferred_date,
            preferred_note=preferred_note or None,
            status='pending',
        )
        db.session.add(req)
        db.session.flush()
        _notify_admins_new_request(req)
        db.session.commit()

        flash('상담 신청이 접수되었습니다.', 'success')
        return redirect(url_for('consultation_request.detail', request_id=req.request_id))

    return render_template('consultation_request/new.html', children=children,
                            categories=CATEGORY_CHOICES)


@consultation_request_bp.route('/<request_id>')
@requires_role('parent', 'admin')
def detail(request_id):
    """상담 신청 상세 - 학부모 시점(내부 협의 스레드는 노출하지 않음)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    if current_user.role == 'parent' and req.requester_id != current_user.user_id:
        abort(403)
    return render_template('consultation_request/detail.html', req=req)


# ==================== 관리자 ====================

@consultation_request_bp.route('/admin')
@requires_role('admin')
def admin_list():
    """상담 신청 접수함 (관리자)"""
    status_filter = request.args.get('status', '')
    query = ConsultationRequest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    requests = query.order_by(ConsultationRequest.created_at.desc()).all()
    pending_count = ConsultationRequest.query.filter_by(status='pending').count()
    return render_template('consultation_request/admin_list.html',
                            requests=requests, status_filter=status_filter,
                            pending_count=pending_count)


@consultation_request_bp.route('/admin/<request_id>')
@requires_role('admin')
def admin_detail(request_id):
    """상담 신청 상세 - 관리자 시점(내부 협의 시작/일정확정/거절 액션 포함)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    teachers = User.query.filter(
        User.role == 'teacher', User.is_active == True
    ).order_by(User.name).all()
    internal_messages = []
    if req.internal_conversation_id:
        internal_messages = ConversationMessage.query.filter_by(
            conversation_id=req.internal_conversation_id
        ).order_by(ConversationMessage.created_at).all()
    parent_messages = []
    if req.parent_conversation_id:
        parent_messages = ConversationMessage.query.filter_by(
            conversation_id=req.parent_conversation_id
        ).order_by(ConversationMessage.created_at).all()

    # 개별보강은 일정 확정 시 실제 보강수업을 개설해야 하는데, 참조할 원
    # 수업(requested_course_id)이 없어(애초에 매칭되는 그룹 수업이 없어서
    # 개별로 신청한 것) 학생의 현재 수강 목록에서 관리자가 직접 골라야 한다.
    student_courses = []
    if req.category == MAKEUP_INDIVIDUAL_CATEGORY and req.status == 'pending':
        from app.models.course import CourseEnrollment
        student_courses = [e.course for e in CourseEnrollment.query.filter_by(
            student_id=req.student_id, status='active'
        ).all() if e.course]

    return render_template('consultation_request/admin_detail.html',
                            req=req, teachers=teachers, internal_messages=internal_messages,
                            parent_messages=parent_messages, student_courses=student_courses)


@consultation_request_bp.route('/admin/<request_id>/parent-reply', methods=['POST'])
@requires_role('admin')
def parent_reply(request_id):
    """학부모(위젯)에게 답장 - app.chat_widget이 학부모 쪽 답장을 담당하고
    여기는 관리자 쪽 답장만 처리한다. 같은 parent_conversation_id를 공유."""
    req = ConsultationRequest.query.get_or_404(request_id)
    body = request.form.get('body', '').strip()
    if not body:
        flash('메시지를 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    uid = current_user.user_id
    if not req.parent_conversation_id:
        if not req.requester_id:
            flash('신청자 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('consultation_request.admin_detail', request_id=request_id))
        # 신청 건마다 독립된 Conversation을 쓴다(기존 대화 재사용 금지) - 재사용하면
        # 같은 학부모의 다른 신청(보강/환불) 스레드와 뒤섞인다.
        conv = Conversation(user1_id=uid, user2_id=req.requester_id)
        db.session.add(conv)
        db.session.flush()
        req.parent_conversation_id = conv.conversation_id
    else:
        conv = Conversation.query.get(req.parent_conversation_id)

    msg = ConversationMessage(conversation_id=conv.conversation_id, sender_id=uid, body=body)
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)

    if req.requester_id:
        db.session.add(Notification(
            user_id=req.requester_id,
            notification_type='dm',
            title=f'💬 {current_user.name}님의 새 메시지',
            message=f'[상담 신청] {body[:80]}',
            related_user_id=uid,
        ))
    db.session.commit()

    flash('답장을 보냈습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))


@consultation_request_bp.route('/admin/<request_id>/internal-consult', methods=['POST'])
@requires_role('admin')
def internal_consult(request_id):
    """강사에게 내부 협의 요청.

    ask_date를 지정하면 특정 시간을 컨펌받는 질문이 되고(admin_ask_date/time
    저장, 강사 화면에 확인 버튼만 노출), 비워두면 자유롭게 물어본 것으로
    취급해 강사가 직접 날짜/시간을 정해 입력하는 폼이 노출된다
    (teacher.consult_confirm_detail에서 분기).

    신청 건마다 독립된 Conversation을 새로 만든다(기존 대화 재사용 금지) -
    재사용하면 이 강사와 나눈 다른 무관한 대화에 새 문의가 묻혀버리는
    문제가 실제로 있었다(2026-09-29, 최진우 학생 건에서 발견)."""
    req = ConsultationRequest.query.get_or_404(request_id)
    teacher_id = request.form.get('teacher_id', '')
    body = request.form.get('body', '').strip()
    teacher = User.query.filter_by(user_id=teacher_id, role='teacher').first()
    if not teacher:
        flash('강사를 올바르게 선택해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))
    if not body:
        flash('강사에게 전달할 내용을 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    from app.utils.course_utils import parse_hm_time

    ask_date_str = request.form.get('ask_date', '').strip()
    ask_date = None
    ask_time = None
    if ask_date_str:
        try:
            ask_date = datetime.strptime(ask_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if ask_date:
        ask_time = parse_hm_time(request.form, 'ask_time')

    req.admin_ask_date = ask_date
    req.admin_ask_time = ask_time
    # 강사를 새로 바꿔서 다시 물어보는 경우를 대비해 이전 컨펌 상태는 초기화
    req.teacher_confirmed = False
    req.teacher_confirmed_at = None
    req.teacher_proposed_date = None
    req.teacher_proposed_time = None

    uid = current_user.user_id
    # 관리자가 매번 다른 강사를 고를 수 있으므로(강사 고정인 그룹 보강과 달리),
    # 이전에 연결된 대화가 있어도 상대(강사)가 바뀌었으면 새로 만든다.
    existing_conv = Conversation.query.get(req.internal_conversation_id) if req.internal_conversation_id else None
    if existing_conv and teacher_id in (existing_conv.user1_id, existing_conv.user2_id):
        conv = existing_conv
    else:
        conv = Conversation(user1_id=uid, user2_id=teacher_id)
        db.session.add(conv)
        db.session.flush()
        req.internal_conversation_id = conv.conversation_id

    student_name = req.student.display_name if req.student else ''
    prefix = f'[상담 신청 - {student_name} / {req.category}]\n'
    if ask_date:
        when_label = ask_date.strftime('%Y-%m-%d')
        if ask_time:
            when_label += f' {ask_time.strftime("%H:%M")}'
        body = f'{body}\n\n➡️ 이 시간에 가능하신가요? {when_label}'
    msg = ConversationMessage(conversation_id=conv.conversation_id, sender_id=uid, body=prefix + body)
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)

    db.session.commit()

    Notification.create_notification(
        user_id=teacher_id,
        notification_type='dm',
        title=f'💬 {current_user.name}님의 새 메시지',
        message=(prefix + body)[:80],
        link_url=url_for('teacher.consult_confirm_detail', request_id=req.request_id),
        related_user_id=uid,
    )

    flash('강사에게 내부 협의를 요청했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))


@consultation_request_bp.route('/admin/<request_id>/schedule', methods=['POST'])
@requires_role('admin')
def schedule(request_id):
    """학부모와 일정 확정.

    category가 개별보강이면 단순히 날짜/메모만 기록하는 게 아니라 실제
    1회 보강수업(Course/CourseSession)까지 함께 개설한다(finalize_individual_makeup).
    예전엔 이 분기가 없어서 "일정 확정"을 눌러도 수업이 열리지 않는 문제가
    있었다."""
    req = ConsultationRequest.query.get_or_404(request_id)
    date_raw = request.form.get('scheduled_date', '').strip()
    try:
        scheduled_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        flash('일정을 올바르게 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    if req.category == MAKEUP_INDIVIDUAL_CATEGORY:
        from app.models import Course
        from app.utils.course_utils import finalize_individual_makeup, parse_hm_time

        if req.created_makeup_course_id:
            flash('이미 보강수업이 개설되어 있습니다.', 'warning')
            return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

        source_course_id = request.form.get('source_course_id', '').strip()
        source_course = Course.query.get(source_course_id) if source_course_id else None
        if not source_course:
            flash('보강 시수/요금 산정 기준이 될 원 수업을 선택해주세요.', 'error')
            return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

        makeup_time = parse_hm_time(request.form, 'scheduled_time')
        try:
            makeup_course = finalize_individual_makeup(
                req, source_course, scheduled_date,
                makeup_start_override=makeup_time,
                approved_by=current_user.user_id,
            )
            db.session.commit()
            flash(f'보강 일정을 확정하고 수업을 개설했습니다: {makeup_course.course_name}', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'[개별보강 확정] 오류 request_id={request_id}: {e}', exc_info=True)
            flash(f'보강수업 개설 중 오류가 발생했습니다. (오류: {type(e).__name__})', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    note = request.form.get('scheduled_note', '').strip()
    req.status = 'scheduled'
    req.scheduled_date = scheduled_date
    req.scheduled_note = note or None
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    db.session.commit()
    _notify_parent_response(req)

    flash('상담 일정을 확정했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))


@consultation_request_bp.route('/admin/<request_id>/reject', methods=['POST'])
@requires_role('admin')
def reject(request_id):
    """상담 신청 거절 (사유 필수)"""
    req = ConsultationRequest.query.get_or_404(request_id)
    reason = request.form.get('reject_reason', '').strip()
    if not reason:
        flash('거절 사유를 입력해주세요.', 'error')
        return redirect(url_for('consultation_request.admin_detail', request_id=request_id))

    req.status = 'rejected'
    req.reject_reason = reason
    req.responded_by = current_user.user_id
    req.responded_at = datetime.utcnow()
    _notify_parent_response(req)
    db.session.commit()

    flash('상담 신청을 거절했습니다.', 'success')
    return redirect(url_for('consultation_request.admin_detail', request_id=request_id))
