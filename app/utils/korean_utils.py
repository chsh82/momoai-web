"""한글 처리 유틸리티"""

def get_chosung(text):
    """
    한글 텍스트에서 초성을 추출합니다.

    Args:
        text: 한글 텍스트

    Returns:
        초성만 추출된 문자열
    """
    # 한글 초성 리스트
    CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ',
                    'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

    result = []

    for char in text:
        # 한글인지 확인
        if '가' <= char <= '힣':
            # 유니코드에서 '가'(0xAC00)를 빼고 초성 인덱스 계산
            code = ord(char) - 0xAC00
            chosung_index = code // (21 * 28)  # 21개 중성, 28개 종성
            result.append(CHOSUNG_LIST[chosung_index])
        elif char.isalpha():
            # 영문자는 그대로
            result.append(char)
        elif char.isdigit():
            # 숫자는 그대로
            result.append(char)
        elif char in [' ', '-', '·', ',', '.', '(', ')', '/', '~']:
            # 공백과 특수문자는 그대로
            result.append(char)
        else:
            # 기타는 생략
            pass

    return ''.join(result)


def normalize_answer(text):
    """
    답안을 정규화합니다 (공백 제거, 소문자 변환 등)

    Args:
        text: 원본 텍스트

    Returns:
        정규화된 텍스트
    """
    if not text:
        return ''

    # 공백 제거
    text = text.replace(' ', '')
    # 소문자 변환
    text = text.lower()
    # 특수문자 제거
    text = text.replace('.', '').replace(',', '').replace('·', '')

    return text


def check_answer_similarity(student_answer, correct_answer, threshold=0.8):
    """
    학생 답안과 정답의 유사도를 확인합니다.

    Args:
        student_answer: 학생 답안
        correct_answer: 정답
        threshold: 유사도 임계값 (0.0 ~ 1.0)

    Returns:
        bool: 정답 여부
    """
    # 정규화
    student_norm = normalize_answer(student_answer)
    correct_norm = normalize_answer(correct_answer)

    # 완전 일치
    if student_norm == correct_norm:
        return True

    # 정답이 학생 답안에 포함되거나 그 반대
    if student_norm in correct_norm or correct_norm in student_norm:
        # 길이 차이가 크지 않으면 정답으로 인정
        len_diff = abs(len(student_norm) - len(correct_norm))
        if len_diff <= 2:
            return True

    return False
