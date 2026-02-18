# -*- coding: utf-8 -*-
"""
독서 논술 MBTI 점수 계산 유틸리티 (신규 체계)

3대 영역 × 3단계 수준 = 9개 세부 능력
각 능력당 5문항, 각 문항 1-5점
"""


def calculate_mbti_scores(responses):
    """
    응답을 기반으로 9개 세부 능력 점수 계산

    Args:
        responses (dict): 질문 응답 {' q1': '3', 'q2': '5', ..., 'comp1': 'read:beginner:2,read:intermediate:3', ...}

    Returns:
        dict: 9개 세부 능력 점수
        {
            'read': {
                'beginner': 0-25,
                'intermediate': 0-25,
                'advanced': 0-25
            },
            'speech': {
                'beginner': 0-25,
                'intermediate': 0-25,
                'advanced': 0-25
            },
            'write': {
                'beginner': 0-25,
                'intermediate': 0-25,
                'advanced': 0-25
            }
        }
    """

    scores = {
        'read': {'beginner': 0, 'intermediate': 0, 'advanced': 0},
        'speech': {'beginner': 0, 'intermediate': 0, 'advanced': 0},
        'write': {'beginner': 0, 'intermediate': 0, 'advanced': 0}
    }

    # 질문 매핑 (question number → (area, level))
    # 1-5: read beginner, 6-10: read intermediate, 11-15: read advanced
    # 16-20: speech beginner, 21-25: speech intermediate, 26-30: speech advanced
    # 31-35: write beginner, 36-40: write intermediate, 41-45: write advanced
    question_mapping = {}

    q_num = 1
    for area in ['read', 'speech', 'write']:
        for level in ['beginner', 'intermediate', 'advanced']:
            for _ in range(5):  # 각 능력당 5문항
                question_mapping[f'q{q_num}'] = (area, level)
                q_num += 1

    # Step 1: 45개 절대평가 질문 점수 계산 (각 1-5점)
    for q_key, response in responses.items():
        if q_key.startswith('q') and q_key in question_mapping:
            try:
                score = int(response)
                if 1 <= score <= 5:
                    area, level = question_mapping[q_key]
                    scores[area][level] += score
            except (ValueError, TypeError):
                continue

    # Step 2: 5개 비교 질문 보너스 점수 추가
    # 형식: "read:beginner:2,read:intermediate:3" → read_beginner에 +2, read_intermediate에 +3
    for i in range(1, 6):
        comp_key = f'comp{i}'
        if comp_key in responses:
            comp_value = responses[comp_key]
            if comp_value:
                # 형식: "area:level:points,area:level:points"
                parts = comp_value.split(',')
                for part in parts:
                    try:
                        area, level, points = part.split(':')
                        bonus = int(points)
                        if area in scores and level in scores[area]:
                            scores[area][level] += bonus
                    except (ValueError, IndexError):
                        continue

    return scores


def determine_mbti_level(area_score):
    """
    영역별 누적 점수로 수준 판정

    Args:
        area_score (int): 영역 누적 점수 (3개 세부능력 합계)

    Returns:
        str: 'beginner', 'intermediate', 'advanced'
    """
    if area_score <= 5:
        return 'beginner'
    elif area_score <= 10:
        return 'intermediate'
    else:
        return 'advanced'


def determine_mbti_type(scores):
    """
    9개 세부 능력 점수로 MBTI 유형 결정

    Args:
        scores (dict): 9개 세부 능력 점수

    Returns:
        tuple: (read_level, speech_level, write_level, type_key)
            - read_level: 'beginner', 'intermediate', 'advanced'
            - speech_level: 'beginner', 'intermediate', 'advanced'
            - write_level: 'beginner', 'intermediate', 'advanced'
            - type_key: 'beginner-beginner-beginner' 형식
    """

    # 각 영역의 누적 점수 계산
    read_total = sum(scores['read'].values())
    speech_total = sum(scores['speech'].values())
    write_total = sum(scores['write'].values())

    # 수준 판정
    read_level = determine_mbti_level(read_total)
    speech_level = determine_mbti_level(speech_total)
    write_level = determine_mbti_level(write_total)

    # type_key 생성
    type_key = f"{read_level}-{speech_level}-{write_level}"

    return read_level, speech_level, write_level, type_key


def validate_responses(responses):
    """
    응답 데이터 유효성 검증

    Args:
        responses (dict): 질문 응답

    Returns:
        tuple: (is_valid, error_message)
    """

    # 45개 절대평가 질문 확인
    for i in range(1, 46):
        q_key = f'q{i}'
        if q_key not in responses:
            return False, f"질문 {i}에 대한 응답이 없습니다."

        try:
            score = int(responses[q_key])
            if not (1 <= score <= 5):
                return False, f"질문 {i}의 응답이 유효하지 않습니다 (1-5 범위)."
        except (ValueError, TypeError):
            return False, f"질문 {i}의 응답 형식이 올바르지 않습니다."

    # 5개 비교 질문 확인
    for i in range(1, 6):
        comp_key = f'comp{i}'
        if comp_key not in responses or not responses[comp_key]:
            return False, f"비교 질문 {45+i}에 대한 응답이 없습니다."

    return True, ""


def get_level_name(level):
    """수준 코드를 한글 이름으로 변환"""
    level_names = {
        'beginner': '초급',
        'intermediate': '중급',
        'advanced': '고급'
    }
    return level_names.get(level, level)


def get_area_name(area):
    """영역 코드를 한글 이름으로 변환"""
    area_names = {
        'read': '독해력',
        'speech': '사고력',
        'write': '서술력'
    }
    return area_names.get(area, area)


def get_score_summary(scores):
    """
    점수 요약 정보 생성

    Args:
        scores (dict): 9개 세부 능력 점수

    Returns:
        dict: 요약 정보
    """
    read_total = sum(scores['read'].values())
    speech_total = sum(scores['speech'].values())
    write_total = sum(scores['write'].values())
    total_score = read_total + speech_total + write_total

    return {
        'read_total': read_total,
        'speech_total': speech_total,
        'write_total': write_total,
        'total_score': total_score,
        'max_score': 135,  # 45문항 × 5점 + 비교문항 보너스 가능
        'read_level': get_level_name(determine_mbti_level(read_total)),
        'speech_level': get_level_name(determine_mbti_level(speech_total)),
        'write_level': get_level_name(determine_mbti_level(write_total))
    }
