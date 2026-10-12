import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parent / 'app' / 'utils' / 'makeup_workflow.py'
spec = importlib.util.spec_from_file_location('makeup_workflow', MODULE_PATH)
assert spec is not None and spec.loader is not None
makeup_workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(makeup_workflow)

get_makeup_workflow_state = makeup_workflow.get_makeup_workflow_state
get_makeup_workflow_steps = makeup_workflow.get_makeup_workflow_steps
get_parent_makeup_workflow_steps = makeup_workflow.get_parent_makeup_workflow_steps
get_admin_makeup_queue_key = makeup_workflow.get_admin_makeup_queue_key
build_admin_makeup_queue_counts = makeup_workflow.build_admin_makeup_queue_counts
filter_makeup_requests_by_queue = makeup_workflow.filter_makeup_requests_by_queue
build_teacher_consult_draft = makeup_workflow.build_teacher_consult_draft
build_parent_reply_draft = makeup_workflow.build_parent_reply_draft


def req(**overrides):
    data = {
        'status': 'pending',
        'internal_conversation_id': None,
        'teacher_confirmed': False,
        'teacher_proposed_date': None,
        'teacher_proposed_time': None,
        'parent_conversation_id': None,
        'parent_confirmed_at': None,
        'parent_reschedule_requested_at': None,
        'parent_reschedule_admin_acted_at': None,
        'parent_reschedule_reason': None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class MakeupWorkflowStateTest(unittest.TestCase):
    def test_new_pending_request_needs_teacher_consult(self):
        state = get_makeup_workflow_state(req())

        self.assertEqual(state.key, 'received')
        self.assertEqual(state.parent_label, '신청 접수')
        self.assertEqual(state.admin_action, '강사에게 문의')
        self.assertEqual(state.step_index, 0)

    def test_pending_request_with_internal_conversation_waits_for_teacher(self):
        state = get_makeup_workflow_state(req(internal_conversation_id=12))

        self.assertEqual(state.key, 'waiting_teacher')
        self.assertEqual(state.parent_label, '담당 선생님 확인 중')
        self.assertEqual(state.admin_action, '강사 회신 확인')
        self.assertEqual(state.step_index, 1)

    def test_teacher_proposed_schedule_waits_for_parent_when_parent_conversation_exists(self):
        state = get_makeup_workflow_state(req(
            internal_conversation_id=12,
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
            parent_conversation_id=34,
        ))

        self.assertEqual(state.key, 'waiting_parent')
        self.assertEqual(state.parent_label, '학부모 확인 필요')
        self.assertEqual(state.admin_action, '학부모 재안내')
        self.assertEqual(state.step_index, 3)

    def test_parent_reschedule_request_needs_admin_recoordination(self):
        state = get_makeup_workflow_state(req(
            internal_conversation_id=12,
            parent_conversation_id=34,
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
            parent_reschedule_requested_at='2026-10-09 12:00:00',
            parent_reschedule_reason='그날은 어렵고 금요일 오후가 가능합니다.',
        ))

        self.assertEqual(state.key, 'reschedule_requested')
        self.assertEqual(state.parent_label, '다른 일정 요청됨')
        self.assertEqual(state.admin_label, '재조율 필요')
        self.assertEqual(state.admin_action, '강사에게 다시 문의')
        self.assertEqual(get_admin_makeup_queue_key(req(parent_reschedule_requested_at='x')), 'reschedule_requested')

    def test_reschedule_request_after_admin_action_waits_for_teacher_again(self):
        state = get_makeup_workflow_state(req(
            internal_conversation_id=12,
            parent_conversation_id=34,
            parent_reschedule_requested_at='2026-10-09 12:00:00',
            parent_reschedule_admin_acted_at='2026-10-09 12:05:00',
        ))

        self.assertEqual(state.key, 'waiting_teacher')

    def test_teacher_confirmed_without_parent_request_is_ready_to_approve(self):
        state = get_makeup_workflow_state(req(
            internal_conversation_id=12,
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
        ))

        self.assertEqual(state.key, 'ready_to_approve')
        self.assertEqual(state.parent_label, '보강 일정 제안됨')
        self.assertEqual(state.admin_action, '최종 승인')
        self.assertEqual(state.step_index, 2)

    def test_terminal_statuses_override_pending_fields(self):
        self.assertEqual(get_makeup_workflow_state(req(status='approved', teacher_confirmed=True)).key, 'approved')
        self.assertEqual(get_makeup_workflow_state(req(status='rejected', teacher_confirmed=True)).key, 'rejected')

    def test_steps_mark_current_and_completed(self):
        steps = get_makeup_workflow_steps(req(internal_conversation_id=12))

        self.assertEqual([s['key'] for s in steps], [
            'received', 'waiting_teacher', 'teacher_proposed', 'waiting_parent', 'approved'
        ])
        self.assertEqual(steps[0]['status'], 'done')
        self.assertEqual(steps[1]['status'], 'current')
        self.assertEqual(steps[2]['status'], 'todo')

    def test_parent_steps_are_simplified_to_four_stages(self):
        steps = get_parent_makeup_workflow_steps(req(internal_conversation_id=12))

        self.assertEqual([s['label'] for s in steps], ['접수됨', '확인 중', '일정 확인', '확정'])
        self.assertEqual(steps[0]['status'], 'done')
        self.assertEqual(steps[1]['status'], 'current')
        self.assertEqual(steps[2]['status'], 'todo')

    def test_parent_waiting_parent_step_maps_to_schedule_check(self):
        steps = get_parent_makeup_workflow_steps(req(
            internal_conversation_id=12,
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
            parent_conversation_id=34,
        ))

        self.assertEqual(steps[0]['status'], 'done')
        self.assertEqual(steps[1]['status'], 'done')
        self.assertEqual(steps[2]['status'], 'current')
        self.assertEqual(steps[3]['status'], 'todo')

    def test_admin_queue_keys_match_operational_work(self):
        self.assertEqual(get_admin_makeup_queue_key(req()), 'needs_teacher_consult')
        self.assertEqual(get_admin_makeup_queue_key(req(internal_conversation_id=1)), 'waiting_teacher')
        self.assertEqual(get_admin_makeup_queue_key(req(teacher_confirmed=True)), 'ready_to_approve')
        self.assertEqual(get_admin_makeup_queue_key(req(
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
            parent_conversation_id=2,
        )), 'waiting_parent')
        self.assertEqual(get_admin_makeup_queue_key(req(status='approved')), 'done')
        self.assertEqual(get_admin_makeup_queue_key(req(status='rejected')), 'rejected')

    def test_admin_queue_counts_and_filtering(self):
        requests = [
            req(),
            req(internal_conversation_id=1),
            req(teacher_confirmed=True),
            req(teacher_confirmed=True, teacher_proposed_date='2026-10-15', parent_conversation_id=2),
            req(parent_reschedule_requested_at='2026-10-09 12:00:00'),
            req(status='approved'),
            req(status='rejected'),
        ]

        counts = build_admin_makeup_queue_counts(requests)

        self.assertEqual(counts['all'], 7)
        self.assertEqual(counts['needs_teacher_consult'], 1)
        self.assertEqual(counts['waiting_teacher'], 1)
        self.assertEqual(counts['ready_to_approve'], 1)
        self.assertEqual(counts['waiting_parent'], 1)
        self.assertEqual(counts['reschedule_requested'], 1)
        self.assertEqual(counts['done'], 1)
        self.assertEqual(counts['rejected'], 1)
        self.assertEqual(len(filter_makeup_requests_by_queue(requests, 'waiting_teacher')), 1)
        self.assertEqual(len(filter_makeup_requests_by_queue(requests, '')), 7)

    def test_teacher_consult_draft_includes_reason_and_requested_date(self):
        student = SimpleNamespace(name='김민준', grade='초5')
        course = SimpleNamespace(course_name='독서논술 A', weekday=2, start_time=None, end_time=None)
        draft = build_teacher_consult_draft(req(
            student=student,
            requested_course=course,
            reason='학교 행사로 결석',
            requested_date='2026-10-15',
        ))

        self.assertIn('김민준', draft)
        self.assertIn('독서논술 A', draft)
        self.assertIn('학교 행사로 결석', draft)
        self.assertIn('2026-10-15', draft)
        self.assertIn('가능한 보강 후보 일정', draft)

    def test_parent_reply_draft_changes_by_queue_state(self):
        waiting_teacher = build_parent_reply_draft(req(internal_conversation_id=1))
        waiting_parent = build_parent_reply_draft(req(
            teacher_confirmed=True,
            teacher_proposed_date='2026-10-15',
            teacher_proposed_time='15:30',
            parent_conversation_id=1,
        ))
        approved = build_parent_reply_draft(req(status='approved'))

        self.assertIn('담당 선생님께 확인 중', waiting_teacher)
        self.assertIn('2026-10-15', waiting_parent)
        self.assertIn('15:30', waiting_parent)
        self.assertIn('확정', approved)


if __name__ == '__main__':
    unittest.main()
