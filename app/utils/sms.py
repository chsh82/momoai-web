# -*- coding: utf-8 -*-
"""SMS 발송 유틸리티 (Aligo API)"""
import requests
from flask import current_app


def send_sms_message(phone, message, title=None):
    """알리고 SMS API를 통한 문자 발송.

    Args:
        phone: 수신자 번호 (예: '01012345678')
        message: 발송 내용
        title: LMS 제목 (90자 초과 시 자동 LMS 전환)

    Returns:
        (success: bool, reason: str)
    """
    api_key = current_app.config.get('SMS_API_KEY')
    user_id = current_app.config.get('SMS_USER_ID')
    sender = current_app.config.get('SMS_SENDER')

    if not api_key:
        return False, 'SMS_API_KEY 미설정'
    if not user_id:
        return False, 'SMS_USER_ID 미설정'
    if not sender:
        return False, 'SMS_SENDER 미설정'
    if not phone:
        return False, '수신자 번호 없음'

    msg_type = 'LMS' if len(message) > 90 else 'SMS'
    data = {
        'key': api_key,
        'user_id': user_id,
        'sender': sender,
        'receiver': phone,
        'msg': message,
        'msg_type': msg_type,
        'title': title or ('MOMOAI' if msg_type == 'LMS' else ''),
    }

    try:
        response = requests.post('https://apis.aligo.in/send/', data=data, timeout=10)
        result = response.json()
        if result.get('result_code') == '1':
            current_app.logger.info(f'SMS 발송 성공: {phone}')
            return True, '발송 완료'
        else:
            reason = result.get('message', '알 수 없는 오류')
            current_app.logger.warning(f'SMS 발송 실패 ({phone}): {reason}')
            return False, reason
    except requests.exceptions.Timeout:
        return False, '요청 타임아웃 (10초 초과)'
    except Exception as e:
        current_app.logger.error(f'SMS 발송 오류 ({phone}): {e}')
        return False, str(e)
