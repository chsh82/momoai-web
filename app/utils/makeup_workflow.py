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
