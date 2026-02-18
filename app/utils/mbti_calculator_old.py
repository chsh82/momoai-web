# -*- coding: utf-8 -*-
"""독서 논술 MBTI 점수 계산 유틸리티"""


def calculate_mbti_scores(responses):
    """
    학생 응답을 기반으로 MBTI 점수 계산

    Args:
        responses (dict): {
            'q1': 5, 'q2': 4, ..., 'q45': 3,
            'comp1': 'vocab', 'comp2': 'textual', ...
        }

    Returns:
        dict: {
            'read': {'vocab': 20, 'reread': 18, 'analyze': 15},
            'speech': {'textual': 22, 'expand': 19, 'lead': 16},
            'write': {'summary': 21, 'logic': 17, 'rewrite': 14}
        }
    """
    # 초기화
    scores = {
        'read': {'vocab': 0, 'reread': 0, 'analyze': 0},
        'speech': {'textual': 0, 'expand': 0, 'lead': 0},
        'write': {'summary': 0, 'logic': 0, 'rewrite': 0}
    }

    # 45개 절대평가 문항 점수 집계
    # 문항 매핑 (HTML과 동일)
    question_mapping = [
        # Read 영역 (1-15)
        # vocab (1-5)
        {'id': 1, 'area': 'read', 'cat': 'vocab'},
        {'id': 2, 'area': 'read', 'cat': 'vocab'},
        {'id': 3, 'area': 'read', 'cat': 'vocab'},
        {'id': 4, 'area': 'read', 'cat': 'vocab'},
        {'id': 5, 'area': 'read', 'cat': 'vocab'},
        # reread (6-10)
        {'id': 6, 'area': 'read', 'cat': 'reread'},
        {'id': 7, 'area': 'read', 'cat': 'reread'},
        {'id': 8, 'area': 'read', 'cat': 'reread'},
        {'id': 9, 'area': 'read', 'cat': 'reread'},
        {'id': 10, 'area': 'read', 'cat': 'reread'},
        # analyze (11-15)
        {'id': 11, 'area': 'read', 'cat': 'analyze'},
        {'id': 12, 'area': 'read', 'cat': 'analyze'},
        {'id': 13, 'area': 'read', 'cat': 'analyze'},
        {'id': 14, 'area': 'read', 'cat': 'analyze'},
        {'id': 15, 'area': 'read', 'cat': 'analyze'},

        # Speech 영역 (16-30)
        # textual (16-20)
        {'id': 16, 'area': 'speech', 'cat': 'textual'},
        {'id': 17, 'area': 'speech', 'cat': 'textual'},
        {'id': 18, 'area': 'speech', 'cat': 'textual'},
        {'id': 19, 'area': 'speech', 'cat': 'textual'},
        {'id': 20, 'area': 'speech', 'cat': 'textual'},
        # expand (21-25)
        {'id': 21, 'area': 'speech', 'cat': 'expand'},
        {'id': 22, 'area': 'speech', 'cat': 'expand'},
        {'id': 23, 'area': 'speech', 'cat': 'expand'},
        {'id': 24, 'area': 'speech', 'cat': 'expand'},
        {'id': 25, 'area': 'speech', 'cat': 'expand'},
        # lead (26-30)
        {'id': 26, 'area': 'speech', 'cat': 'lead'},
        {'id': 27, 'area': 'speech', 'cat': 'lead'},
        {'id': 28, 'area': 'speech', 'cat': 'lead'},
        {'id': 29, 'area': 'speech', 'cat': 'lead'},
        {'id': 30, 'area': 'speech', 'cat': 'lead'},

        # Write 영역 (31-45)
        # summary (31-35)
        {'id': 31, 'area': 'write', 'cat': 'summary'},
        {'id': 32, 'area': 'write', 'cat': 'summary'},
        {'id': 33, 'area': 'write', 'cat': 'summary'},
        {'id': 34, 'area': 'write', 'cat': 'summary'},
        {'id': 35, 'area': 'write', 'cat': 'summary'},
        # logic (36-40)
        {'id': 36, 'area': 'write', 'cat': 'logic'},
        {'id': 37, 'area': 'write', 'cat': 'logic'},
        {'id': 38, 'area': 'write', 'cat': 'logic'},
        {'id': 39, 'area': 'write', 'cat': 'logic'},
        {'id': 40, 'area': 'write', 'cat': 'logic'},
        # rewrite (41-45)
        {'id': 41, 'area': 'write', 'cat': 'rewrite'},
        {'id': 42, 'area': 'write', 'cat': 'rewrite'},
        {'id': 43, 'area': 'write', 'cat': 'rewrite'},
        {'id': 44, 'area': 'write', 'cat': 'rewrite'},
        {'id': 45, 'area': 'write', 'cat': 'rewrite'},
    ]

    # 절대평가 문항 점수 집계
    for q_map in question_mapping:
        q_id = q_map['id']
        key = f'q{q_id}'

        if key in responses and responses[key]:
            value = int(responses[key])
            area = q_map['area']
            cat = q_map['cat']
            scores[area][cat] += value

    # 비교 문항 가중치 적용 (HTML 로직과 동일)
    # comp1: Read 영역 선호
    if 'comp1' in responses:
        value = responses['comp1']
        if value == 'vocab':
            scores['read']['vocab'] += 3
        elif value == 'reread':
            scores['read']['reread'] += 3
        elif value == 'analyze':
            scores['read']['analyze'] += 3

    # comp2: Speech 영역 선호
    if 'comp2' in responses:
        value = responses['comp2']
        if value == 'textual':
            scores['speech']['textual'] += 3
        elif value == 'expand':
            scores['speech']['expand'] += 3
        elif value == 'lead':
            scores['speech']['lead'] += 3

    # comp3: Write 영역 선호
    if 'comp3' in responses:
        value = responses['comp3']
        if value == 'summary':
            scores['write']['summary'] += 3
        elif value == 'logic':
            scores['write']['logic'] += 3
        elif value == 'rewrite':
            scores['write']['rewrite'] += 3

    # comp4: Read 영역 재확인
    if 'comp4' in responses:
        value = responses['comp4']
        if value == 'vocab':
            scores['read']['vocab'] += 2
        elif value == 'reread':
            scores['read']['reread'] += 2
        elif value == 'analyze':
            scores['read']['analyze'] += 2

    # comp5: 전체 영역 선호
    if 'comp5' in responses:
        value = responses['comp5']
        if value == 'all_read':
            scores['read']['vocab'] += 1
            scores['read']['reread'] += 1
            scores['read']['analyze'] += 1
        elif value == 'all_speech':
            scores['speech']['textual'] += 1
            scores['speech']['expand'] += 1
            scores['speech']['lead'] += 1
        elif value == 'all_write':
            scores['write']['summary'] += 1
            scores['write']['logic'] += 1
            scores['write']['rewrite'] += 1

    return scores


def determine_mbti_type(scores):
    """
    점수를 기반으로 MBTI 유형 결정

    Args:
        scores (dict): calculate_mbti_scores의 반환값

    Returns:
        tuple: (read_type, speech_type, write_type, type_key)
        예: ('vocab', 'textual', 'summary', 'vocab-textual-summary')
    """
    # 각 영역에서 최고 점수 카테고리 찾기
    read_type = max(scores['read'], key=scores['read'].get)
    speech_type = max(scores['speech'], key=scores['speech'].get)
    write_type = max(scores['write'], key=scores['write'].get)

    # 유형 키 생성
    type_key = f"{read_type}-{speech_type}-{write_type}"

    return read_type, speech_type, write_type, type_key


def validate_responses(responses, question_count=50):
    """
    응답 데이터 유효성 검증

    Args:
        responses (dict): 응답 데이터
        question_count (int): 예상 질문 수

    Returns:
        tuple: (is_valid, error_message)
    """
    # 45개 절대평가 문항 검증
    for i in range(1, 46):
        key = f'q{i}'
        if key not in responses or not responses[key]:
            return False, f"{i}번 질문에 답변해주세요."

        try:
            value = int(responses[key])
            if value < 1 or value > 5:
                return False, f"{i}번 질문의 답변이 유효하지 않습니다. (1-5)"
        except (ValueError, TypeError):
            return False, f"{i}번 질문의 답변이 유효하지 않습니다."

    # 5개 비교 문항 검증
    comp_validations = [
        ('comp1', ['vocab', 'reread', 'analyze']),
        ('comp2', ['textual', 'expand', 'lead']),
        ('comp3', ['summary', 'logic', 'rewrite']),
        ('comp4', ['vocab', 'reread', 'analyze']),
        ('comp5', ['all_read', 'all_speech', 'all_write'])
    ]

    for idx, (key, valid_values) in enumerate(comp_validations, start=1):
        if key not in responses or not responses[key]:
            return False, f"비교 질문 {idx}에 답변해주세요."

        if responses[key] not in valid_values:
            return False, f"비교 질문 {idx}의 답변이 유효하지 않습니다."

    return True, None
