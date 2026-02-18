#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""독서 논술 MBTI 27가지 유형 데이터 삽입 (신규 체계)"""
import sys
import io
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.reading_mbti import ReadingMBTIType

print("=" * 70)
print("📚 독서 논술 MBTI 27가지 유형 데이터 삽입 (신규 체계)")
print("=" * 70)

app = create_app('development')

with app.app_context():
    print("\n[1단계] 기존 유형 데이터 삭제")
    print("-" * 70)

    ReadingMBTIType.query.delete()
    db.session.commit()
    print("✅ 기존 유형 데이터 삭제 완료")

    print("\n[2단계] 27개 유형 데이터 삽입")
    print("-" * 70)

    # 수준 정의
    levels = {
        'beginner': {'code': '1', 'name': '초급'},
        'intermediate': {'code': '2', 'name': '중급'},
        'advanced': {'code': '3', 'name': '고급'}
    }

    types_data = []
    type_num = 1

    for read_level in ['beginner', 'intermediate', 'advanced']:
        for speech_level in ['beginner', 'intermediate', 'advanced']:
            for write_level in ['beginner', 'intermediate', 'advanced']:

                read_name = levels[read_level]['name']
                speech_name = levels[speech_level]['name']
                write_name = levels[write_level]['name']

                type_key = f"{read_level}-{speech_level}-{write_level}"
                type_code = f"R{levels[read_level]['code']}-S{levels[speech_level]['code']}-W{levels[write_level]['code']}"

                # 유형명 생성
                if read_level == speech_level == write_level:
                    if read_level == 'beginner':
                        type_name = "기초 학습자"
                        combo_desc = "모든 영역에서 기본기를 다지는 단계"
                    elif read_level == 'intermediate':
                        type_name = "균형 발전형"
                        combo_desc = "모든 영역이 고르게 발달한 학습자"
                    else:
                        type_name = "통합 마스터"
                        combo_desc = "모든 영역에서 고급 역량을 갖춘 학습자"
                else:
                    # 가장 높은 수준을 기준으로 명명
                    max_level = max([read_level, speech_level, write_level],
                                   key=lambda x: ['beginner', 'intermediate', 'advanced'].index(x))

                    if max_level == 'advanced':
                        if read_level == 'advanced':
                            type_name = f"{read_name}독해 전문가"
                            combo_desc = "독해력이 뛰어난 분석적 학습자"
                        elif speech_level == 'advanced':
                            type_name = f"{speech_name}토론 리더"
                            combo_desc = "사고력과 토론 능력이 뛰어난 학습자"
                        else:
                            type_name = f"{write_name}작문 전문가"
                            combo_desc = "서술력이 뛰어난 표현적 학습자"
                    elif max_level == 'intermediate':
                        if read_level == 'intermediate':
                            type_name = f"{read_name}독해 발전형"
                            combo_desc = "독해력이 성장 중인 학습자"
                        elif speech_level == 'intermediate':
                            type_name = f"{speech_name}토론 성장형"
                            combo_desc = "사고력이 발달 중인 학습자"
                        else:
                            type_name = f"{write_name}작문 성장형"
                            combo_desc = "서술력이 향상 중인 학습자"
                    else:
                        type_name = "잠재력 발굴형"
                        combo_desc = "기초를 다지며 성장하는 학습자"

                # 세부 설명 생성
                full_desc = f"이 유형은 독해력이 {read_name} 수준, 사고력(토론)이 {speech_name} 수준, 서술력이 {write_name} 수준인 학습자입니다. "

                if read_level == speech_level == write_level:
                    if read_level == 'beginner':
                        full_desc += "모든 영역에서 기본기를 탄탄히 다져나가는 것이 중요합니다. 꾸준한 학습으로 전 영역의 향상을 기대할 수 있습니다."
                    elif read_level == 'intermediate':
                        full_desc += "모든 영역이 균형있게 발달하여 안정적인 학습이 가능합니다. 심화 학습으로 한 단계 더 도약할 준비가 되어 있습니다."
                    else:
                        full_desc += "모든 영역에서 탁월한 능력을 보이는 우수한 학습자입니다. 전문적인 학습과 실전 경험으로 더욱 발전할 수 있습니다."
                else:
                    strong_areas = []
                    weak_areas = []

                    if read_level == 'advanced': strong_areas.append("독해력")
                    elif read_level == 'beginner': weak_areas.append("독해력")

                    if speech_level == 'advanced': strong_areas.append("사고력")
                    elif speech_level == 'beginner': weak_areas.append("사고력")

                    if write_level == 'advanced': strong_areas.append("서술력")
                    elif write_level == 'beginner': weak_areas.append("서술력")

                    if strong_areas:
                        full_desc += f"{', '.join(strong_areas)}이 뛰어나며, "
                    if weak_areas:
                        full_desc += f"{', '.join(weak_areas)}을 집중적으로 보완하면 균형잡힌 학습자로 성장할 수 있습니다."
                    else:
                        full_desc += "각 영역의 수준 차이를 고려한 맞춤형 학습이 효과적입니다."

                # 영역별 스타일 설명
                reading_styles = {
                    'beginner': "기본 어휘와 문장 구조를 파악하는 수준입니다. 모르는 단어를 찾아보고 문맥을 이해하려 노력합니다.",
                    'intermediate': "문단의 구조와 주제를 파악할 수 있으며, 반복 독해를 통해 심층적으로 이해합니다.",
                    'advanced': "글의 논리 구조를 분석하고 저자의 의도를 비판적으로 평가할 수 있습니다. 확장적 사고가 가능합니다."
                }

                speaking_styles = {
                    'beginner': "이해한 내용을 전달하고 자료를 근거로 의견을 표현할 수 있습니다. 체계적으로 말하려고 노력합니다.",
                    'intermediate': "여러 관점을 제시하고 논리적으로 근거를 제시할 수 있습니다. 주제를 확장하고 연결하는 능력이 있습니다.",
                    'advanced': "토론을 이끌고 의견을 종합하며 새로운 관점을 제시할 수 있습니다. 창의적이고 통합적인 사고가 가능합니다."
                }

                writing_styles = {
                    'beginner': "핵심 내용을 간결하게 요약하고 정리할 수 있습니다. 객관적이고 명확한 서술을 지향합니다.",
                    'intermediate': "논리적 구조를 갖추고 체계적으로 서술할 수 있습니다. 근거를 제시하며 설득력있게 글을 씁니다.",
                    'advanced': "내용을 비판적으로 재구성하고 창의적으로 표현할 수 있습니다. 다양한 시각을 통합하여 풍부한 글을 씁니다."
                }

                # 강점, 약점, 팁 생성
                strengths = []
                weaknesses = []
                tips = []

                # 독해력에 따른 강점/약점/팁
                if read_level == 'advanced':
                    strengths.append("복잡한 텍스트를 빠르게 이해하고 분석할 수 있음")
                    tips.append("심화 독서를 통해 배경지식을 넓히세요")
                elif read_level == 'intermediate':
                    strengths.append("체계적으로 읽고 주요 내용을 파악할 수 있음")
                    tips.append("비판적 독해 연습으로 분석력을 키우세요")
                else:
                    weaknesses.append("긴 글이나 복잡한 내용을 이해하는 데 시간이 필요함")
                    tips.append("매일 꾸준히 읽고 모르는 단어를 정리하세요")

                # 사고력에 따른 강점/약점/팁
                if speech_level == 'advanced':
                    strengths.append("논리적으로 사고하고 창의적으로 표현할 수 있음")
                    tips.append("디베이트나 발표 기회를 적극 활용하세요")
                elif speech_level == 'intermediate':
                    strengths.append("여러 관점을 이해하고 논리적으로 설명할 수 있음")
                    tips.append("토론 활동에 참여하며 다양한 관점을 연습하세요")
                else:
                    weaknesses.append("즉흥적인 발표나 토론에서 어려움을 느낌")
                    tips.append("생각을 미리 정리하고 발표 연습을 자주 하세요")

                # 서술력에 따른 강점/약점/팁
                if write_level == 'advanced':
                    strengths.append("논리적이고 창의적인 글쓰기가 가능함")
                    tips.append("다양한 장르의 글쓰기에 도전하세요")
                elif write_level == 'intermediate':
                    strengths.append("체계적으로 구조화하여 글을 쓸 수 있음")
                    tips.append("글쓰기 후 퇴고하는 습관을 들이세요")
                else:
                    weaknesses.append("긴 글을 쓰거나 논리적으로 전개하는 것이 어려움")
                    tips.append("짧은 글부터 시작해 점진적으로 분량을 늘려가세요")

                # 균형형은 특별 메시지
                if read_level == speech_level == write_level:
                    if read_level == 'beginner':
                        tips.append("세 영역을 동시에 발전시킬 수 있는 통합 프로그램이 적합합니다")
                    elif read_level == 'intermediate':
                        tips.append("심화 과정으로 도약할 준비가 되어 있습니다")
                    else:
                        tips.append("실전 경험과 전문적 학습으로 전문가 수준에 도달할 수 있습니다")

                type_data = {
                    'type_key': type_key,
                    'type_code': type_code,
                    'type_name': type_name,
                    'combo_description': combo_desc,
                    'full_description': full_desc,
                    'reading_style': reading_styles[read_level],
                    'speaking_style': speaking_styles[speech_level],
                    'writing_style': writing_styles[write_level],
                    'strengths': strengths,
                    'weaknesses': weaknesses if weaknesses else ["현재 특별한 약점은 발견되지 않았습니다"],
                    'tips': tips
                }

                types_data.append(type_data)
                type_num += 1

    # DB에 삽입
    for type_data in types_data:
        mbti_type = ReadingMBTIType(
            type_key=type_data['type_key'],
            type_code=type_data['type_code'],
            type_name=type_data['type_name'],
            combo_description=type_data['combo_description'],
            full_description=type_data['full_description'],
            reading_style=type_data['reading_style'],
            speaking_style=type_data['speaking_style'],
            writing_style=type_data['writing_style'],
            strengths=type_data['strengths'],
            weaknesses=type_data['weaknesses'],
            tips=type_data['tips']
        )
        db.session.add(mbti_type)
        print(f"  ✓ {type_data['type_code']}: {type_data['type_name']}")

    db.session.commit()

    print("\n" + "=" * 70)
    print("✅ 27개 유형 데이터 삽입 완료!")
    print("=" * 70)
    print(f"\n📊 수준 조합:")
    print(f"  • 독해력: 초급(R1) / 중급(R2) / 고급(R3)")
    print(f"  • 사고력: 초급(S1) / 중급(S2) / 고급(S3)")
    print(f"  • 서술력: 초급(W1) / 중급(W2) / 고급(W3)")
    print(f"  • 총 유형: 3 × 3 × 3 = 27가지")
    print(f"\n🎯 다음 단계: 점수 계산 알고리즘 업데이트")
