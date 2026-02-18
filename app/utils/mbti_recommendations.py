# -*- coding: utf-8 -*-
"""
MBTI 기반 수업 스타일 추천 유틸리티
"""
from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType


def get_student_latest_mbti(student_id):
    """학생의 최신 MBTI 결과 조회"""
    return ReadingMBTIResult.query.filter_by(
        student_id=student_id
    ).order_by(ReadingMBTIResult.created_at.desc()).first()


def generate_teaching_recommendations(mbti_result):
    """MBTI 결과 기반 수업 추천 생성

    Args:
        mbti_result: ReadingMBTIResult 객체

    Returns:
        dict: {
            'type_name': '유형명',
            'type_combination': 'vocab-textual-summary',
            'reading_style': '독서 스타일 설명',
            'speaking_style': '말하기 스타일 설명',
            'writing_style': '쓰기 스타일 설명',
            'strengths': ['강점1', '강점2', ...],
            'weaknesses': ['약점1', '약점2', ...],
            'tips': ['팁1', '팁2', ...],
            'recommended_approaches': ['추천 교수법1', '추천 교수법2', ...]
        }
    """
    if not mbti_result or not mbti_result.mbti_type:
        return None

    mbti_type = mbti_result.mbti_type

    # 기본 정보
    recommendations = {
        'type_name': mbti_type.type_name,
        'type_code': mbti_type.type_code,
        'type_combination': mbti_result.type_combination,
        'combo_description': mbti_type.combo_description,
        'reading_style': mbti_type.reading_style,
        'speaking_style': mbti_type.speaking_style,
        'writing_style': mbti_type.writing_style,
        'strengths': mbti_type.strengths or [],
        'weaknesses': mbti_type.weaknesses or [],
        'tips': mbti_type.tips or [],
    }

    # 유형별 맞춤 교수법 추천
    recommended_approaches = []

    # 독서 유형에 따른 추천
    if mbti_result.read_type == 'vocab':
        recommended_approaches.extend([
            "📖 어휘 중심 수업: 텍스트 내 핵심 어휘를 집중 분석하고 확장 학습",
            "📝 어휘 노트 작성: 새로운 단어의 뜻과 용례를 정리하는 습관 형성",
            "🎯 정확한 독해: 단어 하나하나의 의미를 정확히 파악하는 훈련"
        ])
    elif mbti_result.read_type == 'reread':
        recommended_approaches.extend([
            "🔄 반복 학습: 같은 텍스트를 여러 번 읽으며 깊이 이해",
            "📚 정독 중심: 빠른 독서보다 천천히 깊게 읽는 연습",
            "💡 통찰력 개발: 반복 읽기를 통한 새로운 발견 유도"
        ])
    elif mbti_result.read_type == 'analyze':
        recommended_approaches.extend([
            "🔍 비판적 독서: 저자의 의도와 논리 구조 분석",
            "📊 구조 파악: 글의 전개 방식과 논리적 흐름 파악",
            "🤔 질문 중심: 'Why'와 'How'를 끊임없이 묻는 학습"
        ])

    # 말하기 유형에 따른 추천
    if mbti_result.speech_type == 'textual':
        recommended_approaches.extend([
            "📖 텍스트 기반 토론: 교재 내용을 근거로 한 논의 진행",
            "✍️ 인용 활용: 원문을 인용하며 의견 표현하는 훈련",
            "📚 근거 중심 대화: 자신의 주장에 텍스트 근거 제시하기"
        ])
    elif mbti_result.speech_type == 'expand':
        recommended_approaches.extend([
            "🌐 확장 토론: 텍스트를 넘어 다양한 관점 탐색",
            "💭 창의적 사고: 교재 주제를 실생활과 연결하는 연습",
            "🎨 자유로운 표현: 개인적 경험과 생각 나누기 장려"
        ])
    elif mbti_result.speech_type == 'lead':
        recommended_approaches.extend([
            "👥 토론 리더 역할: 조별 활동에서 사회자 경험 제공",
            "🎯 주제 선정: 토론 주제를 직접 제안하고 이끌기",
            "💪 리더십 개발: 다른 학생들의 의견을 이끌어내는 훈련"
        ])

    # 쓰기 유형에 따른 추천
    if mbti_result.write_type == 'summary':
        recommended_approaches.extend([
            "📝 요약 훈련: 핵심 내용을 간결하게 정리하는 연습",
            "🎯 핵심 파악: 중요한 정보와 부수적 정보 구분하기",
            "✂️ 간결한 표현: 불필요한 내용 제거하고 핵심만 남기기"
        ])
    elif mbti_result.write_type == 'logic':
        recommended_approaches.extend([
            "🔗 논리적 구조: 서론-본론-결론의 명확한 구성 연습",
            "📊 근거 제시: 주장에 대한 타당한 근거 개발",
            "🎯 논증 훈련: 반론 예상과 재반박 구성하기"
        ])
    elif mbti_result.write_type == 'rewrite':
        recommended_approaches.extend([
            "✍️ 재작성 연습: 초고를 여러 번 수정하며 완성도 높이기",
            "🔄 표현 개선: 더 나은 단어와 문장으로 다듬기",
            "💎 퇴고 습관: 쓴 글을 반드시 검토하고 수정하는 습관"
        ])

    recommendations['recommended_approaches'] = recommended_approaches

    return recommendations


def format_recommendations_for_consultation(mbti_result):
    """상담 기록에 들어갈 추천 내용 텍스트 생성"""
    recs = generate_teaching_recommendations(mbti_result)

    if not recs:
        return "MBTI 검사 결과가 없습니다. 먼저 독서 논술 MBTI 검사를 진행해주세요."

    text = f"""
🎯 **{recs['type_name']}** ({recs['type_code']})
{recs['combo_description']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 **독서 스타일**
{recs['reading_style']}

💬 **말하기 스타일**
{recs['speaking_style']}

✍️ **쓰기 스타일**
{recs['writing_style']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ **강점**
"""

    for i, strength in enumerate(recs['strengths'], 1):
        text += f"\n{i}. {strength}"

    text += "\n\n⚠️ **보완 필요 영역**\n"

    for i, weakness in enumerate(recs['weaknesses'], 1):
        text += f"\n{i}. {weakness}"

    text += "\n\n💡 **수업 진행 팁**\n"

    for i, tip in enumerate(recs['tips'], 1):
        text += f"\n{i}. {tip}"

    text += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "🎓 **추천 교수법**\n"

    for approach in recs['recommended_approaches']:
        text += f"\n• {approach}"

    return text.strip()


def get_quick_mbti_summary(mbti_result):
    """MBTI 요약 정보 (한 줄)"""
    if not mbti_result or not mbti_result.mbti_type:
        return "MBTI 미실시"

    return f"{mbti_result.mbti_type.type_name} ({mbti_result.type_combination})"
