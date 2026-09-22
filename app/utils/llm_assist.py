# -*- coding: utf-8 -*-
"""관리자용 소규모 LLM 보조 기능 공용 헬퍼.

첨삭(momoai_service)처럼 핵심 상품 로직이 아니라, 메시지 초안 작성·짧은
텍스트 해석 같은 가벼운 보조 작업에 쓴다. 프롬프트는 호출하는 쪽(라우트)이
서버에서 직접 조립한다 - feedback.generate와 달리 클라이언트가 임의
프롬프트를 보내지 않도록, 이 헬퍼는 완성된 프롬프트 문자열만 받는다.
"""
import json
import re

import anthropic

from config import Config

MODEL_NAME = 'claude-sonnet-4-6'


def call_claude_text(prompt, max_tokens=300, system=None):
    """Claude를 호출해 (텍스트, usage) 튜플을 반환한다.

    usage는 {'input_tokens': int, 'output_tokens': int} 형태 - 호출부에서
    ApiUsageLog에 그대로 남기면 된다. API 키 미설정/호출 실패 시 예외를
    그대로 올린다 - 호출부가 각자 맥락에 맞는 에러 메시지로 감싼다.
    """
    if not Config.ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY 미설정')

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    kwargs = {
        'model': MODEL_NAME,
        'max_tokens': max_tokens,
        'timeout': 60.0,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        kwargs['system'] = system

    response = client.messages.create(**kwargs)
    text = ''.join(
        block.text for block in response.content if getattr(block, 'type', None) == 'text'
    )
    usage = {
        'input_tokens': getattr(response.usage, 'input_tokens', 0),
        'output_tokens': getattr(response.usage, 'output_tokens', 0),
    }
    return text, usage


def extract_json_block(text):
    """모델이 코드펜스(```json ... ```)로 감싸서 답해도 JSON을 뽑아낸다.
    파싱 실패 시 None을 반환한다 - 호출부가 '추출 실패'로 처리."""
    if not text:
        return None
    cleaned = text.strip()
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.S)
    if m:
        cleaned = m.group(1)
    else:
        m2 = re.search(r'\{.*\}', cleaned, re.S)
        if m2:
            cleaned = m2.group(0)
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        return None
