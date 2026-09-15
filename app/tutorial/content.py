# -*- coding: utf-8 -*-
"""튜토리얼 콘텐츠 JSON 로더 - 앱 시작 후 최초 조회 시 한 번 읽어 메모리에 캐시한다.

파일이 없거나 JSON이 깨지면 빈 값을 조용히 반환하지 않고 명확한 에러 로그를 남긴다
(prompt_1_초등코스1구현.md 2절).
"""
import json
import os

from flask import current_app

_CACHE = {}


def _content_path(track, course):
    return os.path.join(os.path.dirname(__file__), 'content', track, f'{course}.json')


def get_course(track, course):
    """트랙/코스의 콘텐츠 dict 전체. 못 읽으면 None."""
    key = (track, course)
    if key in _CACHE:
        return _CACHE[key]

    path = _content_path(track, course)
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        current_app.logger.error('[tutorial.content] 콘텐츠 파일 없음: %s', path)
        return None
    except json.JSONDecodeError as e:
        current_app.logger.error('[tutorial.content] 콘텐츠 JSON 파싱 실패: %s (%s)', path, e)
        return None

    _CACHE[key] = data
    return data


def get_lesson(track, course, lesson_id):
    """course1 안에서 lesson_id로 레슨 dict 하나. 못 찾으면 None."""
    data = get_course(track, course)
    if not data:
        return None
    for lesson in data.get('lessons', []):
        if lesson.get('id') == lesson_id:
            return lesson
    return None


def get_lesson_ids(track, course):
    """이 코스에 속한 레슨 id 목록 - 코스 완료 판정에서 "전체 레슨 수"를 세는 데 쓴다.
    레슨 수를 하드코딩하지 않기 위한 함수(레슨 2·3 추가 시 자동 반영)."""
    data = get_course(track, course)
    if not data:
        return []
    return [lesson['id'] for lesson in data.get('lessons', [])]
