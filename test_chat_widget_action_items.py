# -*- coding: utf-8 -*-
"""chat_widget 보강 신청 ActionItem 생성 보조 테스트.

프로젝트 실행 환경에 Flask 의존성이 없을 수 있어 routes.py를 직접 import하지 않고
대상 헬퍼 함수의 AST만 추출해 실행한다.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


ROUTES_PATH = Path(__file__).parent / 'app' / 'chat_widget' / 'routes.py'


def load_function(name):
    tree = ast.parse(ROUTES_PATH.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            ns = {}
            exec(compile(module, str(ROUTES_PATH), 'exec'), ns)
            return ns[node.name]
    raise AssertionError(f'{name} helper not found')


def load_helper():
    return load_function('_build_makeup_action_item_kwargs')


class MakeupActionItemKwargsTest(unittest.TestCase):
    def test_group_makeup_action_item_mentions_student_course_and_reason(self):
        helper = load_helper()
        student = SimpleNamespace(student_id='student-1', display_name='김모모')
        course = SimpleNamespace(course_name='초등 독서논술 월수')
        course.teacher_id = 'teacher-1'

        kwargs = helper(
            kind='group', student=student, creator_id='admin-1',
            reason='감기로 결석했습니다', course=course,
        )

        self.assertEqual(kwargs['category'], '상담처리')
        self.assertEqual(kwargs['priority'], 'medium')
        self.assertEqual(kwargs['status'], 'pending')
        self.assertEqual(kwargs['student_id'], 'student-1')
        self.assertEqual(kwargs['created_by'], 'admin-1')
        self.assertIn('김모모', kwargs['title'])
        self.assertIn('그룹 보강', kwargs['title'])
        self.assertIn('초등 독서논술 월수', kwargs['content'])
        self.assertIn('감기로 결석했습니다', kwargs['content'])
        self.assertIsNone(kwargs['assigned_to'])

    def test_individual_makeup_action_item_records_preferred_time_without_course(self):
        helper = load_helper()
        student = SimpleNamespace(student_id='student-2', display_name='박모모')
        kwargs = helper(
            kind='individual', student=student, creator_id='admin-1',
            reason='해외 일정으로 결석', preferred_date='2026-10-12',
            preferred_time='19:30', preferred_note='평일 저녁 가능',
        )

        self.assertIn('박모모', kwargs['title'])
        self.assertIn('개별보강', kwargs['title'])
        self.assertIn('2026-10-12', kwargs['content'])
        self.assertIn('19:30', kwargs['content'])
        self.assertIn('평일 저녁 가능', kwargs['content'])
        self.assertNotIn('None', kwargs['content'])

    def test_action_item_creator_prefers_visible_admin_accounts(self):
        pick_creator = load_function('_pick_action_item_creator_id')
        manager = SimpleNamespace(user_id='manager-1', role='manager')
        admin = SimpleNamespace(user_id='admin-1', role='admin')
        master = SimpleNamespace(user_id='master-1', role='master_admin')

        self.assertEqual(pick_creator([manager, admin, master]), 'admin-1')
        self.assertEqual(pick_creator([manager]), 'manager-1')
        self.assertIsNone(pick_creator([]))


if __name__ == '__main__':
    unittest.main()
