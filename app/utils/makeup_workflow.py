# -*- coding: utf-8 -*-
"""보강 신청 UX 상태 계산 유틸리티.

DB의 `MakeupClassRequest.status`는 기존 호환을 위해 pending/approved/rejected로
유지하고, 화면에서는 기존 필드 조합으로 더 구체적인 진행 상태를 파생한다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MakeupWorkflowState:
    """보강 신청 화면용 파생 상태."""

    key: str
    parent_label: str
    admin_label: str
    admin_action: str
    step_index: int
    tone: str = "gray"


WORKFLOW_STEPS = [
    ("received", "신청 접수"),
    ("waiting_teacher", "담당 선생님 확인 중"),
    ("teacher_proposed", "보강 일정 제안됨"),
    ("waiting_parent", "학부모 확인 필요"),
    ("approved", "보강 확정"),
]


def _truthy_attr(obj, name):
    return bool(getattr(obj, name, None))


def get_makeup_workflow_state(makeup_request):
    """MakeupClassRequest-like 객체를 화면용 상태로 변환한다.

    실제 SQLAlchemy 모델뿐 아니라 테스트용 SimpleNamespace에도 동작하도록
    attribute 접근만 사용한다.
    """
    status = getattr(makeup_request, "status", None)

    if status == "approved":
        return MakeupWorkflowState(
            key="approved",
            parent_label="보강 확정",
            admin_label="완료",
            admin_action="보강수업 보기",
            step_index=4,
            tone="green",
        )

    if status == "rejected":
        return MakeupWorkflowState(
            key="rejected",
            parent_label="반려됨",
            admin_label="반려됨",
            admin_action="반려 사유 확인",
            step_index=0,
            tone="red",
        )

    parent_conversation_exists = _truthy_attr(makeup_request, "parent_conversation_id")
    parent_confirmed = _truthy_attr(makeup_request, "parent_confirmed_at")
    teacher_confirmed = bool(getattr(makeup_request, "teacher_confirmed", False))
    teacher_proposed = _truthy_attr(makeup_request, "teacher_proposed_date")
    internal_conversation_exists = _truthy_attr(makeup_request, "internal_conversation_id")
    reschedule_requested_at = getattr(makeup_request, "parent_reschedule_requested_at", None)
    reschedule_admin_acted_at = getattr(makeup_request, "parent_reschedule_admin_acted_at", None)
    reschedule_pending = bool(reschedule_requested_at) and (
        not reschedule_admin_acted_at or str(reschedule_admin_acted_at) < str(reschedule_requested_at)
    )

    if reschedule_pending:
        return MakeupWorkflowState(
            key="reschedule_requested",
            parent_label="다른 일정 요청됨",
            admin_label="재조율 필요",
            admin_action="강사에게 다시 문의",
            step_index=3,
            tone="yellow",
        )

    if teacher_proposed and parent_conversation_exists and not parent_confirmed:
        return MakeupWorkflowState(
            key="waiting_parent",
            parent_label="학부모 확인 필요",
            admin_label="학부모 확인 대기",
            admin_action="학부모 재안내",
            step_index=3,
            tone="blue",
        )

    if teacher_confirmed:
        return MakeupWorkflowState(
            key="ready_to_approve",
            parent_label="보강 일정 제안됨",
            admin_label="승인 가능",
            admin_action="최종 승인",
            step_index=2,
            tone="green",
        )

    if internal_conversation_exists:
        return MakeupWorkflowState(
            key="waiting_teacher",
            parent_label="담당 선생님 확인 중",
            admin_label="강사 확인 대기",
            admin_action="강사 회신 확인",
            step_index=1,
            tone="yellow",
        )

    return MakeupWorkflowState(
        key="received",
        parent_label="신청 접수",
        admin_label="강사 문의 필요",
        admin_action="강사에게 문의",
        step_index=0,
        tone="gray",
    )


def get_makeup_workflow_steps(makeup_request):
    """운영/관리자 화면용 상세 타임라인 단계 리스트를 반환한다."""
    state = get_makeup_workflow_state(makeup_request)
    steps = []
    for index, (key, label) in enumerate(WORKFLOW_STEPS):
        if state.key == "rejected":
            step_status = "current" if index == 0 else "todo"
        elif index < state.step_index:
            step_status = "done"
        elif index == state.step_index:
            step_status = "current"
        else:
            step_status = "todo"
        steps.append({"key": key, "label": label, "status": step_status})

    if state.key == "rejected":
        steps.append({"key": "rejected", "label": "반려됨", "status": "current"})

    return steps


ADMIN_QUEUE_LABELS = [
    ("all", "전체"),
    ("needs_teacher_consult", "강사 문의 필요"),
    ("waiting_teacher", "강사 회신 대기"),
    ("reschedule_requested", "재조율 필요"),
    ("waiting_parent", "학부모 확인 대기"),
    ("ready_to_approve", "승인 가능"),
    ("done", "완료"),
    ("rejected", "반려/취소"),
]


def get_admin_makeup_queue_key(makeup_request):
    """관리자 작업 큐용 상태 키를 반환한다."""
    state = get_makeup_workflow_state(makeup_request)
    if state.key == "received":
        return "needs_teacher_consult"
    if state.key == "approved":
        return "done"
    return state.key


def build_admin_makeup_queue_counts(makeup_requests):
    """관리자 작업 큐 탭별 건수를 계산한다."""
    counts = {key: 0 for key, _ in ADMIN_QUEUE_LABELS}
    items = list(makeup_requests)
    counts["all"] = len(items)
    for item in items:
        key = get_admin_makeup_queue_key(item)
        counts[key] = counts.get(key, 0) + 1
    return counts


def filter_makeup_requests_by_queue(makeup_requests, queue_key):
    """큐 키로 보강 신청 목록을 필터링한다. 빈 값/all은 전체 반환."""
    if not queue_key or queue_key == "all":
        return list(makeup_requests)
    return [item for item in makeup_requests if get_admin_makeup_queue_key(item) == queue_key]


def _display_attr(obj, attr, default=""):
    target = getattr(obj, attr, None)
    if target is None:
        return default
    if hasattr(target, "strftime"):
        return target.strftime("%Y-%m-%d")
    return str(target)


def _display_time(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def build_teacher_consult_draft(makeup_request):
    """강사 문의 모달에 넣을 기본 초안 문구를 만든다.

    자동 발송하지 않고 운영자가 확인·수정 후 전송하는 본문이다.
    """
    student = getattr(makeup_request, "student", None)
    course = getattr(makeup_request, "requested_course", None)
    student_name = getattr(student, "name", None) or getattr(student, "display_name", None) or "학생"
    student_grade = getattr(student, "grade", "") or ""
    course_name = getattr(course, "course_name", "수업") or "수업"
    reason = getattr(makeup_request, "reason", None) or "사유 미기재"
    requested_date = _display_attr(makeup_request, "requested_date", "특정 희망일 없음")

    return (
        f"{student_name}({student_grade}) 학생의 {course_name} 보강 신청 건입니다.\n"
        f"신청 사유: {reason}\n"
        f"학부모 희망일: {requested_date}\n"
        f"{('재조율 요청: ' + getattr(makeup_request, 'parent_reschedule_reason', '') + chr(10)) if getattr(makeup_request, 'parent_reschedule_reason', None) else ''}\n"
        "가능한 보강 후보 일정을 확인해서 회신 부탁드립니다. "
        "가능하시면 날짜와 시간을 함께 알려주세요."
    )


def build_parent_reply_draft(makeup_request):
    """학부모 답장 모달에 넣을 상태별 기본 초안 문구를 만든다."""
    state = get_makeup_workflow_state(makeup_request)
    proposed_date = _display_attr(makeup_request, "teacher_proposed_date", "")
    proposed_time = _display_time(getattr(makeup_request, "teacher_proposed_time", None))
    when = proposed_date + (f" {proposed_time}" if proposed_time else "")

    if state.key == "received":
        return "보강 신청이 접수되었습니다. 담당 선생님께 가능 일정을 확인한 뒤 후보 일정을 안내드리겠습니다."
    if state.key == "waiting_teacher":
        return "현재 담당 선생님께 확인 중입니다. 가능한 보강 후보 일정이 확인되는 대로 바로 안내드리겠습니다."
    if state.key == "ready_to_approve":
        if when:
            return f"담당 선생님 확인 결과 {when}에 보강 진행이 가능합니다. 이 일정으로 확정해드릴까요?"
        return "담당 선생님 확인이 완료되었습니다. 가능한 보강 후보 일정을 정리해 다시 안내드리겠습니다."
    if state.key == "waiting_parent":
        if when:
            return f"안내드린 보강 후보 일정은 {when}입니다. 이 일정으로 진행 가능하실지 확인 부탁드립니다."
        return "안내드린 보강 후보 일정으로 진행 가능하실지 확인 부탁드립니다."
    if state.key == "reschedule_requested":
        reason = getattr(makeup_request, "parent_reschedule_reason", None) or "학부모님이 다른 일정을 요청하셨습니다."
        return f"재조율 요청 확인했습니다. 남겨주신 내용({reason})을 바탕으로 담당 선생님께 다시 확인한 뒤 후보 일정을 안내드리겠습니다."
    if state.key == "approved":
        return "보강 일정이 확정되었습니다. 앱의 수업 일정에서 다시 확인 부탁드립니다."
    if state.key == "rejected":
        return "이번 보강 신청은 진행이 어려운 것으로 확인되었습니다. 필요하시면 다른 후보 일정으로 다시 문의해주세요."
    return "보강 신청 건 확인 후 다시 안내드리겠습니다."


def get_parent_makeup_workflow_steps(makeup_request):
    """학부모 화면용 4단계 타임라인을 반환한다.

    관리자/운영 화면은 더 자세한 5단계 상태를 쓰지만, 학부모 화면은
    이해하기 쉬운 `접수됨 → 확인 중 → 일정 확인 → 확정`으로 축약한다.
    """
    state = get_makeup_workflow_state(makeup_request)
    parent_steps = [
        ("received", "접수됨"),
        ("checking", "확인 중"),
        ("schedule_check", "일정 확인"),
        ("approved", "확정"),
    ]
    state_to_index = {
        "received": 0,
        "waiting_teacher": 1,
        "ready_to_approve": 2,
        "waiting_parent": 2,
        "reschedule_requested": 2,
        "approved": 3,
        "rejected": 0,
    }
    current_index = state_to_index.get(state.key, 0)

    steps = []
    for index, (key, label) in enumerate(parent_steps):
        if state.key == "rejected":
            step_status = "current" if index == 0 else "todo"
        elif index < current_index:
            step_status = "done"
        elif index == current_index:
            step_status = "current"
        else:
            step_status = "todo"
        steps.append({"key": key, "label": label, "status": step_status})

    if state.key == "rejected":
        steps.append({"key": "rejected", "label": "반려", "status": "current"})

    return steps
