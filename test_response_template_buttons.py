# -*- coding: utf-8 -*-
"""관리자 응대 표준 답변 빠른 삽입 UI 테스트."""
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class ResponseTemplateButtonsTest(unittest.TestCase):
    def test_consultation_parent_reply_has_standard_template_buttons(self):
        html = (ROOT / 'templates' / 'consultation_request' / 'admin_detail.html').read_text(encoding='utf-8')

        self.assertIn('data-response-template-group="parent-reply"', html)
        self.assertIn('문의 확인했습니다', html)
        self.assertIn('담당 선생님/관리자 확인이 필요', html)
        self.assertIn('insertResponseTemplate', html)
        self.assertIn('id="consultParentReplyBody"', html)

    def test_refund_parent_reply_has_safe_payment_templates(self):
        html = (ROOT / 'templates' / 'refund_request' / 'admin_detail.html').read_text(encoding='utf-8')

        self.assertIn('data-response-template-group="parent-reply"', html)
        self.assertIn('환불/금액 조정 문의 확인했습니다', html)
        self.assertIn('확인 전에는 금액이나 환불 가능 여부를 확정', html)
        self.assertIn('insertResponseTemplate', html)
        self.assertIn('id="refundParentReplyBody"', html)

    def test_makeup_parent_reply_modal_has_makeup_templates(self):
        html = (ROOT / 'templates' / 'admin' / 'makeup_requests.html').read_text(encoding='utf-8')

        self.assertIn('data-response-template-group="makeup-parent-reply"', html)
        self.assertIn('보강 신청 확인했습니다', html)
        self.assertIn('현재 담당 선생님께 보강 가능 시간을 확인 중', html)
        self.assertIn('insertResponseTemplate', html)
        self.assertIn('id="parentReplyBody"', html)


if __name__ == '__main__':
    unittest.main()
