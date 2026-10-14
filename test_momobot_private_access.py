# -*- coding: utf-8 -*-
"""모모봇 임시 비공개 가드 회귀 테스트."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from config import Config
from app.chat_widget import routes as chat_routes


BASE_TEMPLATE = Path(__file__).parent / 'templates' / 'base.html'


class MomobotPrivateAccessTest(unittest.TestCase):
    def _call_guard(self, role, enabled=False):
        app = Flask(__name__)
        app.config['MOMOBOT_PARENT_WIDGET_ENABLED'] = enabled
        original_current_user = chat_routes.current_user
        chat_routes.current_user = SimpleNamespace(is_authenticated=True, role=role)
        try:
            with app.test_request_context('/widget/summary'):
                return chat_routes._block_parent_student_widget_while_private()
        finally:
            chat_routes.current_user = original_current_user

    def test_parent_student_widget_flag_defaults_private_until_reopen_order(self):
        self.assertFalse(Config.MOMOBOT_PARENT_WIDGET_ENABLED)

    def test_parent_chat_widget_is_hidden_by_feature_flag_in_base_template(self):
        body = BASE_TEMPLATE.read_text(encoding='utf-8')
        self.assertIn("current_user.role == 'parent' and config.get('MOMOBOT_PARENT_WIDGET_ENABLED')", body)
        self.assertIn('{% include "partials/momo_agent_widget.html" %}', body)

    def test_parent_and_student_widget_api_requests_return_disabled_notice(self):
        for role in ('parent', 'student'):
            response = self._call_guard(role, enabled=False)
            self.assertIsNotNone(response, role)
            payload, status = response
            self.assertEqual(status, 503)
            self.assertTrue(payload.get_json()['disabled'])
            self.assertIn('임시 중단', payload.get_json()['error'])

    def test_admin_and_teacher_widget_guard_keeps_dev_paths_available(self):
        for role in ('admin', 'teacher'):
            self.assertIsNone(self._call_guard(role, enabled=False), role)

    def test_reopen_flag_allows_parent_widget_api_again(self):
        self.assertIsNone(self._call_guard('parent', enabled=True))


if __name__ == '__main__':
    unittest.main()
