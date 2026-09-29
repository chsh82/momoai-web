# -*- coding: utf-8 -*-
"""사이드바 배지·알림 뱃지에 쓰는 미확인 건수 계산. base.html의
inject_unread_counts() context processor와 /notifications/api/unread-count
폴링 API가 이 함수 하나를 공유한다 - 폴링 쪽에서 로직이 따로 놀면(예전처럼)
사이드바 배지가 페이지 로드 시점에만 반영되고 실시간으로 안 움직이는
문제가 재발하기 쉽다."""

DEFAULT_COUNTS = {
    'homework': 0, 'announcement': 0, 'essay': 0,
    'feedback': 0, 'total': 0, 'assignments': 0, 'pending_users': 0,
    'hall_of_fame': 0, 'dm': 0, 'consultation_request_pending': 0,
    'refund_request_pending': 0, 'makeup_confirm_pending': 0,
    'consult_confirm_pending': 0, 'new_submission': 0,
}


def compute_unread_counts(current_user):
    """로그인한 사용자 기준 미확인 건수 딕셔너리. 인증 안 된 경우 기본값."""
    if not current_user.is_authenticated:
        return dict(DEFAULT_COUNTS)

    from app.models.notification import Notification
    from app.models import db

    try:
        def _count(ntype):
            if isinstance(ntype, list):
                return Notification.query.filter(
                    Notification.user_id == current_user.user_id,
                    Notification.is_read == False,
                    Notification.notification_type.in_(ntype)
                ).count()
            return Notification.query.filter_by(
                user_id=current_user.user_id,
                is_read=False,
                notification_type=ntype
            ).count()

        hw = _count('homework_assignment')
        ann = _count('class_announcement')

        # 관리자용: 승인 대기 회원 수 (거절된 사용자 제외)
        pending_users = 0
        if current_user.is_active and current_user.has_permission_level(2):
            from app.models import User as _UserModel
            exclude_ids = [
                n.user_id for n in Notification.query.filter(
                    Notification.notification_type.in_(['account_rejected', 'account_approved'])
                ).with_entities(Notification.user_id).all()
            ]
            q = _UserModel.query.filter_by(is_active=False).filter(
                _UserModel.role.in_(['teacher', 'parent', 'student'])
            )
            if exclude_ids:
                q = q.filter(~_UserModel.user_id.in_(exclude_ids))
            pending_users = q.count()

        # DM 미읽은 수 (강사/관리자만)
        dm_unread = 0
        if current_user.role in ('admin', 'teacher'):
            from app.models.conversation import Conversation, ConversationMessage
            dm_unread = ConversationMessage.query.join(
                Conversation,
                ConversationMessage.conversation_id == Conversation.conversation_id
            ).filter(
                db.or_(
                    Conversation.user1_id == current_user.user_id,
                    Conversation.user2_id == current_user.user_id
                ),
                ConversationMessage.sender_id != current_user.user_id,
                ConversationMessage.is_read == False
            ).count()

        # 명예의 전당 새 글 수
        from datetime import datetime as _dt
        from app.models.library import HallOfFame
        hof_last_viewed = current_user.hall_of_fame_last_viewed_at or _dt(2000, 1, 1)
        hall_of_fame_new = HallOfFame.query.filter(
            HallOfFame.is_published == True,
            HallOfFame.created_at > hof_last_viewed
        ).count()

        # 상담/환불 신청 접수 대기 수 (관리자만)
        consultation_request_pending = 0
        refund_request_pending = 0
        if current_user.is_active and current_user.has_permission_level(2):
            from app.models.consultation_request import ConsultationRequest
            from app.models.refund_request import RefundRequest
            consultation_request_pending = ConsultationRequest.query.filter_by(status='pending').count()
            refund_request_pending = RefundRequest.query.filter_by(status='pending').count()

        # 강사가 확인해야 할 그룹 보강 신청 수 (관리자가 내부 협의를 시작했지만
        # 아직 강사 본인이 컨펌 안 한 것 - approve_makeup_request가 이 값을
        # 강제로 확인하므로 강사가 놓치면 승인 자체가 막힌다)
        makeup_confirm_pending = 0
        # 강사가 확인해야 할 개별보강/상담 협의 수 (위와 같은 패턴, ConsultationRequest용)
        consult_confirm_pending = 0
        if current_user.is_active and current_user.role == 'teacher':
            from app.models.makeup_request import MakeupClassRequest
            from app.models.course import Course as _Course
            makeup_confirm_pending = MakeupClassRequest.query.join(
                _Course, MakeupClassRequest.requested_course_id == _Course.course_id
            ).filter(
                _Course.teacher_id == current_user.user_id,
                MakeupClassRequest.status == 'pending',
                MakeupClassRequest.internal_conversation_id.isnot(None),
                MakeupClassRequest.teacher_confirmed == False,
            ).count()

            from app.models.consultation_request import ConsultationRequest
            from app.models.conversation import Conversation as _Conversation
            teacher_conv_ids = [c.conversation_id for c in _Conversation.query.filter(
                db.or_(_Conversation.user1_id == current_user.user_id,
                       _Conversation.user2_id == current_user.user_id)
            ).all()]
            if teacher_conv_ids:
                consult_confirm_pending = ConsultationRequest.query.filter(
                    ConsultationRequest.internal_conversation_id.in_(teacher_conv_ids),
                    ConsultationRequest.status == 'pending',
                    ConsultationRequest.teacher_confirmed == False,
                ).count()

        return {
            'homework': hw,
            'announcement': ann,
            'assignments': hw + ann,
            'essay': _count('essay_complete'),
            'feedback': _count(['teacher_feedback', 'consultation']),
            'new_submission': _count('essay_submitted'),
            'pending_users': pending_users,
            'dm': dm_unread,
            'hall_of_fame': hall_of_fame_new,
            'consultation_request_pending': consultation_request_pending,
            'refund_request_pending': refund_request_pending,
            'makeup_confirm_pending': makeup_confirm_pending,
            'consult_confirm_pending': consult_confirm_pending,
            'total': Notification.query.filter_by(
                user_id=current_user.user_id, is_read=False
            ).count(),
        }
    except Exception:
        return dict(DEFAULT_COUNTS)
