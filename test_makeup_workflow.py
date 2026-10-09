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


def req(**overrides):
    data = {
        'status': 'pending',
        'internal_conversation_id': None,
        'teacher_confirmed': False,
        'teacher_proposed_date': None,
        'teacher_proposed_time': None,
        'parent_conversation_id': None,
        'parent_confirmed_at': None,
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


if __name__ == '__main__':
    unittest.main()
