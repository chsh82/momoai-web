#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""27개 독서 논술 MBTI 유형 데이터 삽입"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.reading_mbti import ReadingMBTIType

print("=" * 70)
print("📚 27개 독서 논술 MBTI 유형 데이터 삽입")
print("=" * 70)

app = create_app('development')

with app.app_context():
    print("\n[1단계] 기존 유형 데이터 확인")
    print("-" * 70)

    existing_count = ReadingMBTIType.query.count()
    if existing_count > 0:
        print(f"⚠️  기존 유형 {existing_count}개 발견")
        confirm = input("기존 유형을 삭제하고 새로 삽입하시겠습니까? (y/N): ")
        if confirm.lower() != 'y':
            print("취소되었습니다.")
            sys.exit(0)

        # 기존 데이터 삭제
        print("🗑️  기존 유형 삭제 중...")
        ReadingMBTIType.query.delete()
        db.session.commit()
        print("✅ 기존 유형 삭제 완료")

    # 27개 유형 데이터 (HTML 파일에서 추출)
    # 독해(read): vocab, reread, analyze
    # 발표(speech): textual, expand, lead
    # 쓰기(write): summary, logic, rewrite
    # 총 3x3x3 = 27가지 조합

    types_data = [
        # R1-S1-Wx (vocab-textual-x)
        {
            'type_key': 'vocab-textual-summary',
            'type_code': 'R1-S1-W1',
            'type_name': '정확성의 달인형',
            'combo': '어휘탐험가 × 교재토론러 × 핵심정리왕',
            'desc': '단어 하나하나를 정확히 이해하고, 텍스트에 충실하게 토론하며, 핵심을 간결하게 정리하는 능력이 뛰어난 유형입니다.',
            'reading': '모르는 단어가 나오면 즉시 사전이나 검색을 통해 찾아봅니다. 비슷한 단어의 미묘한 차이도 구분하려고 노력하며, 풍부한 어휘력으로 글의 뉘앙스까지 정확히 이해합니다.',
            'speaking': '토론할 때 정확한 출처를 밝히며 근거를 제시합니다. 확실한 내용만 말하며 구조화해서 차분하고 논리적으로 설명합니다.',
            'writing': '긴 글을 읽고 핵심 내용 3-5가지를 정확히 뽑아낼 수 있습니다. 요약할 때 짧고 간결하게 쓰며, 객관적으로 서술합니다.',
            'strengths': ['정확한 언어 사용', '신뢰할 수 있는 발언', '효율적 정리 능력', '탄탄한 기초'],
            'weaknesses': ['창의적 아이디어 제시 어려움', '주제 확장 논의 부족', '과도한 간결성'],
            'tips': ['내 생각 추가하기', '다른 과목과 연결', '다양한 표현 연습']
        },
        {
            'type_key': 'vocab-textual-logic',
            'type_code': 'R1-S1-W2',
            'type_name': '체계적 완벽주의형',
            'combo': '어휘탐험가 × 교재토론러 × 논리설계사',
            'desc': '정확한 어휘 이해와 텍스트 충실성에 더해 논리적 구조화 능력까지 갖춘 완벽주의 유형입니다.',
            'reading': '단어의 정확한 의미를 파악하여 오독이 거의 없습니다. 한 문장도 대충 넘어가지 않고 완전히 이해하려 합니다.',
            'speaking': '정확한 출처 제시가 가능합니다. 구조화해서 말하며, 주장과 근거의 연결이 명확합니다.',
            'writing': '서론-본론-결론이 명확하고 체계적이며, 주장→근거→예시 순서가 일관됩니다.',
            'strengths': ['정확성과 체계성 조화', '논리적 완결성', '높은 신뢰도', '체계적 개요 작성'],
            'weaknesses': ['과도한 형식 집착', '창의성 제한', '유연성 부족'],
            'tips': ['개요 없이 자유롭게 쓰기', '감성적 표현 더하기', '창의적 구조 실험']
        },
        {
            'type_key': 'vocab-textual-rewrite',
            'type_code': 'R1-S1-W3',
            'type_name': '정밀한 혁신가형',
            'combo': '어휘탐험가 × 교재토론러 × 재구성작가',
            'desc': '정확한 이해를 바탕으로 텍스트에 충실하되, 새롭게 재구성하는 능력을 가진 유형입니다.',
            'reading': '단어를 정확히 파악하여 오독을 방지하며, 표현의 뉘앙스까지 섬세하게 파악합니다.',
            'speaking': '책 내용을 정확히 인용하되, 건설적 제안을 합니다. 새로운 시각을 제시하는 균형잡힌 토론자입니다.',
            'writing': '글의 구조적 개선점을 발견하며, 같은 내용을 다양하게 표현할 수 있습니다.',
            'strengths': ['정확성과 창의성 결합', '혁신적 표현력', '독창적 구조 설계', '비판적 사고'],
            'weaknesses': ['완성 지연 가능', '일관성 흔들림', '과도한 수정'],
            'tips': ['수정 3회 제한', '완성 우선', '버전 저장하며 진행']
        },
        # R1-S2-Wx (vocab-expand-x)
        {
            'type_key': 'vocab-expand-summary',
            'type_code': 'R1-S2-W1',
            'type_name': '정밀 확장형',
            'combo': '어휘탐험가 × 확장사고가 × 핵심정리왕',
            'desc': '정확한 어휘 이해로 아이디어를 풍부하게 확장하면서도, 핵심만 간결하게 정리합니다.',
            'reading': '모르는 단어를 반드시 찾아보며, 관련 유의어와 반의어까지 함께 학습합니다.',
            'speaking': '하나의 주제에서 다양한 방향으로 논의를 확장합니다. 지식을 연결하며 새로운 관점을 제시합니다.',
            'writing': '복잡한 내용을 쉬운 말로 풀어쓰며, 핵심을 정확히 선별합니다.',
            'strengths': ['정확한 기초', '아이디어 풍부', '핵심 파악', '명료한 표현'],
            'weaknesses': ['주제 이탈 가능', '정리 부족', '시간 초과'],
            'tips': ['핵심으로 돌아오기', '3분 발언 규칙', '연결성 명확히']
        },
        {
            'type_key': 'vocab-expand-logic',
            'type_code': 'R1-S2-W2',
            'type_name': '체계적 창의형',
            'combo': '어휘탐험가 × 확장사고가 × 논리설계사',
            'desc': '정확한 어휘력과 창의적 사고, 논리적 구조화 능력을 모두 갖춘 균형 잡힌 유형입니다.',
            'reading': '어휘의 정확한 의미를 파악하며, 관련 단어들의 연결망을 만들며 학습합니다.',
            'speaking': '하나의 주제를 여러 각도에서 바라보며, 다른 과목이나 경험과 자연스럽게 연결합니다.',
            'writing': '서론-본론-결론이 명확하고, 주장→근거→예시 순서가 일관됩니다.',
            'strengths': ['정확성+창의성+논리성', '다양한 관점', '설득력', '균형잡힌 사고'],
            'weaknesses': ['복잡도 증가', '딱딱함', '형식 집착'],
            'tips': ['단순화 연습', '감성 더하기', '시간 배분 개선']
        },
        {
            'type_key': 'vocab-expand-rewrite',
            'type_code': 'R1-S2-W3',
            'type_name': '창의적 개선형',
            'combo': '어휘탐험가 × 확장사고가 × 재구성작가',
            'desc': '정확한 어휘 감각으로 기초를 다지고, 아이디어를 자유롭게 확장하며, 글을 끊임없이 개선합니다.',
            'reading': '정확한 어휘 이해로 오독을 방지하며, 단어 선택의 효과를 비판적으로 평가합니다.',
            'speaking': '주제를 다양한 방향으로 확장하며, 창의적 질문과 대안을 제시합니다.',
            'writing': '글의 구조적 개선점을 발견하며, 같은 내용을 다양하게 표현할 수 있습니다.',
            'strengths': ['정밀함+창의성', '혁신적 표현', '독창적 구조', '메타인지'],
            'weaknesses': ['무한 수정', '완성 지연', '일관성 흔들림'],
            'tips': ['수정 3회 제한', '완성 우선 원칙', '개선 시점 명확화']
        },
        # R1-S3-Wx (vocab-lead-x)
        {
            'type_key': 'vocab-lead-summary',
            'type_code': 'R1-S3-W1',
            'type_name': '정확한 리더형',
            'combo': '어휘탐험가 × 토론리더 × 핵심정리왕',
            'desc': '정확한 어휘력과 리더십, 핵심 정리 능력을 갖춘 신뢰받는 조정자입니다.',
            'reading': '정밀한 어휘 이해와 핵심 용어를 즉시 파악합니다. 용어 정의를 명확히 합니다.',
            'speaking': '토론 흐름을 조정하고 의견을 종합 정리합니다. 핵심 질문을 제시합니다.',
            'writing': '핵심만 간결하게 쓰며, 명료한 표현을 사용합니다. 빠른 요약 능력이 특징입니다.',
            'strengths': ['정밀한 이해', '흐름 조정', '의견 종합', '신뢰성'],
            'weaknesses': ['자신 주장 약화', '중재만 집중', '갈등 회피'],
            'tips': ['리더 전 자기 의견 제시', '건설적 갈등 허용', '주장력 강화']
        },
        {
            'type_key': 'vocab-lead-logic',
            'type_code': 'R1-S3-W2',
            'type_name': '체계적 리더형',
            'combo': '어휘탐험가 × 토론리더 × 논리설계사',
            'desc': '정확한 언어 구사력, 토론 진행 능력, 논리적 글쓰기를 모두 갖춘 완벽한 프로젝트 리더입니다.',
            'reading': '용어의 정확한 정의를 중시하며, 핵심 개념을 파악합니다.',
            'speaking': '논의를 구조화하고 단계별로 진행합니다. 논점을 명확히 하며 합의를 도출합니다.',
            'writing': '완벽한 구조와 논리적 일관성을 유지합니다. 체계적으로 전개하며 설득력이 높습니다.',
            'strengths': ['용어 정의', '구조화', '논리 일관성', '합의 도출'],
            'weaknesses': ['형식 과다 집착', '유연성 부족', '자기 의견 후순위'],
            'tips': ['즉흥 토론 연습', '유연한 진행', '창의적 논의 허용']
        },
        {
            'type_key': 'vocab-lead-rewrite',
            'type_code': 'R1-S3-W3',
            'type_name': '혁신적 리더형',
            'combo': '어휘탐험가 × 토론리더 × 재구성작가',
            'desc': '정확성, 리더십, 개선 능력을 모두 갖춘 변화를 이끄는 혁신가입니다.',
            'reading': '정밀 분석과 표현 평가를 하며, 대안을 제시합니다. 비판적으로 읽습니다.',
            'speaking': '논의를 재구성하고 새로운 관점을 제시합니다. 창의적 해결책을 제시합니다.',
            'writing': '구조를 재설계하고 창의적으로 개선합니다. 지속적으로 발전시킵니다.',
            'strengths': ['정밀 분석', '논의 재구성', '창의적 해결', '변화 주도'],
            'weaknesses': ['과도한 개입', '타인 교정', '완벽 추구'],
            'tips': ['경청 먼저', '제안형 피드백', '다양성 존중']
        },
        # R2-S1-Wx (reread-textual-x)
        {
            'type_key': 'reread-textual-summary',
            'type_code': 'R2-S1-W1',
            'type_name': '꼼꼼한 신중형',
            'combo': '반복독해왕 × 교재토론러 × 핵심정리왕',
            'desc': '반복 읽기로 깊이 이해하고, 텍스트에 충실하며, 핵심을 정확히 정리하는 신뢰형입니다.',
            'reading': '중요한 지문은 최소 2-3번 읽으며, 매번 다른 것을 발견합니다. 밑줄 긋고 메모하며 읽습니다.',
            'speaking': '토론 전 자료를 여러 번 읽고 준비해 와서 내용을 정확히 알고 있습니다.',
            'writing': '핵심을 정확히 파악하고 간결하게 요약합니다. 객관적으로 서술합니다.',
            'strengths': ['깊은 이해력', '정확한 내용 파악', '신뢰성 높은 발언', '장기 기억'],
            'weaknesses': ['시간 과다 소요', '창의성 부족', '텍스트 의존도 높음'],
            'tips': ['1차 독서 집중력 향상', '자기 의견 추가', '즉흥 발언 연습']
        },
        {
            'type_key': 'reread-textual-logic',
            'type_code': 'R2-S1-W2',
            'type_name': '심층 분석형',
            'combo': '반복독해왕 × 교재토론러 × 논리설계사',
            'desc': '반복 읽기로 완전히 이해하고, 텍스트 기반 토론하며, 논리적으로 구조화하는 학구파입니다.',
            'reading': '완벽한 이해를 추구하며 층층이 깊어지는 독해를 합니다. 세부 정보를 장악합니다.',
            'speaking': '내용을 정통하게 알고 있으며, 근거가 명확합니다. 체계적으로 발언합니다.',
            'writing': '완벽한 구조와 논리적 전개가 특징입니다. 일관성이 있고 설득력이 높습니다.',
            'strengths': ['완벽한 이해', '내용 정통', '체계적 발언', '설득력'],
            'weaknesses': ['많은 시간 소요', '준비 없이 약함', '형식 집착'],
            'tips': ['중요도별 재독 조절', '브레인스토밍', '즉흥 토론 연습']
        },
        {
            'type_key': 'reread-textual-rewrite',
            'type_code': 'R2-S1-W3',
            'type_name': '신중한 개선형',
            'combo': '반복독해왕 × 교재토론러 × 재구성작가',
            'desc': '반복으로 완벽히 이해하고, 텍스트에 충실하며, 지속적으로 개선하는 완성도 추구형입니다.',
            'reading': '매 독서마다 새로운 것을 발견하며, 깊이 있게 이해합니다. 비교 독서를 합니다.',
            'speaking': '내용을 숙지하고 있으며, 정확히 인용합니다. 재구성을 제안하고 건설적 피드백을 합니다.',
            'writing': '구조를 개선하고 지속적으로 퇴고합니다. 표현을 다듬으며 완성도가 높습니다.',
            'strengths': ['매번 새 발견', '내용 숙지', '구조 개선', '완성도'],
            'weaknesses': ['시간 부족', '텍스트 의존', '무한 수정'],
            'tips': ['전략적 재독', '수정 제한', '완성 우선 원칙']
        },
        # R2-S2-Wx (reread-expand-x)
        {
            'type_key': 'reread-expand-summary',
            'type_code': 'R2-S2-W1',
            'type_name': '심화 확장형',
            'combo': '반복독해왕 × 확장사고가 × 핵심정리왕',
            'desc': '깊이 읽고, 폭넓게 확장하며, 핵심을 정리하는 균형잡힌 사고형입니다.',
            'reading': '층층이 이해하며 새로운 발견을 합니다. 연결 독서를 하고 깊은 통찰을 얻습니다.',
            'speaking': '지식을 연결하며 깊이와 폭을 모두 갖춥니다. 풍부한 예시를 사용하고 통찰력이 있습니다.',
            'writing': '핵심을 파악하고 간결하게 표현합니다. 구조 감각이 있고 명료합니다.',
            'strengths': ['층층이 이해', '지식 연결', '통찰력', '명료함'],
            'weaknesses': ['시간 소요', '주제 이탈', '정리 부족'],
            'tips': ['선택적 재독', '시간 제한', '마무리 요약']
        },
        {
            'type_key': 'reread-expand-logic',
            'type_code': 'R2-S2-W2',
            'type_name': '통합 사고형',
            'combo': '반복독해왕 × 확장사고가 × 논리설계사',
            'desc': '깊이, 폭, 체계를 모두 갖춘 완벽한 통합 사고자입니다.',
            'reading': '완벽하게 이해하며 다층적으로 독해합니다. 통찰력과 연결 능력이 뛰어납니다.',
            'speaking': '다양한 관점을 제시하고 깊은 통찰을 합니다. 체계적으로 확장하며 창의적으로 종합합니다.',
            'writing': '완벽한 구조로 논리적으로 전개합니다. 깊이와 폭을 모두 갖추며 설득력이 높습니다.',
            'strengths': ['완벽한 이해', '다양한 관점', '깊이와 폭', '설득력'],
            'weaknesses': ['과도한 시간', '복잡도 증가', '결론 도출 어려움'],
            'tips': ['효율적 재독', '주제 중심 유지', '시간 관리']
        },
        {
            'type_key': 'reread-expand-rewrite',
            'type_code': 'R2-S2-W3',
            'type_name': '완벽 추구형',
            'combo': '반복독해왕 × 확장사고가 × 재구성작가',
            'desc': '반복 읽기, 확장 사고, 지속 개선을 모두 하는 극도의 완벽주의자입니다.',
            'reading': '매번 새로운 발견을 하며 깊은 통찰을 얻습니다. 비교 독서와 비판적 읽기를 합니다.',
            'speaking': '창의적으로 확장하고 깊이 있게 논의합니다. 대안을 제시하고 개선을 제안합니다.',
            'writing': '창의적으로 구성하고 지속적으로 개선합니다. 구조를 재설계하며 완성도가 높습니다.',
            'strengths': ['매번 새 발견', '창의적 확장', '지속적 개선', '높은 완성도'],
            'weaknesses': ['극도로 느림', '과도한 개입', '제출 지연'],
            'tips': ['완성 우선', '마감 엄수', '70% 법칙 적용']
        },
        # R2-S3-Wx (reread-lead-x)
        {
            'type_key': 'reread-lead-summary',
            'type_code': 'R2-S3-W1',
            'type_name': '신중한 리더형',
            'combo': '반복독해왕 × 토론리더 × 핵심정리왕',
            'desc': '깊이 이해하고, 토론을 이끌며, 핵심을 정리하는 신뢰받는 리더입니다.',
            'reading': '완벽하게 이해하고 세부를 장악합니다. 반복 효과를 활용하고 장기 기억합니다.',
            'speaking': '내용을 정통하게 알고 흐름을 조정합니다. 의견을 종합하고 신뢰성이 높습니다.',
            'writing': '핵심을 정리하고 간결하게 표현합니다. 명료하고 객관적입니다.',
            'strengths': ['완벽한 이해', '흐름 조정', '의견 종합', '신뢰성'],
            'weaknesses': ['시간 과다', '자기 주장 약화', '갈등 회피'],
            'tips': ['전략적 재독', '의견 먼저 제시', '주장력 강화']
        },
        {
            'type_key': 'reread-lead-logic',
            'type_code': 'R2-S3-W2',
            'type_name': '통찰형 리더',
            'combo': '반복독해왕 × 토론리더 × 논리설계사',
            'desc': '깊이, 리더십, 체계를 갖춘 프로젝트를 이끄는 완벽 리더형입니다.',
            'reading': '층층이 이해하고 완벽하게 파악합니다. 통찰력과 비판적 독해를 합니다.',
            'speaking': '체계적으로 진행하고 논점을 정리합니다. 구조화하고 합의를 도출합니다.',
            'writing': '완벽한 구조와 체계적 논리로 전개합니다. 깊이와 일관성을 모두 갖췄습니다.',
            'strengths': ['완벽한 이해', '논점 정리', '구조화', '합의 도출'],
            'weaknesses': ['많은 시간', '유연성 부족', '자기 의견 후순위'],
            'tips': ['효율적 재독', '즉흥 토론', '자기 주장 강화']
        },
        {
            'type_key': 'reread-lead-rewrite',
            'type_code': 'R2-S3-W3',
            'type_name': '개선 주도형',
            'combo': '반복독해왕 × 토론리더 × 재구성작가',
            'desc': '깊이 이해하고, 토론을 이끌며, 지속적으로 개선하는 변화 주도자입니다.',
            'reading': '매번 새로운 발견을 하며 완벽하게 이해합니다. 비판적 독해와 대안 모색을 합니다.',
            'speaking': '논의를 재구성하고 방향을 제시합니다. 새로운 관점으로 토론을 이끕니다.',
            'writing': '구조를 개선하고 창의적으로 재구성합니다. 지속적으로 퇴고하며 완성도를 높입니다.',
            'strengths': ['완벽한 이해', '논의 재구성', '창의적 개선', '변화 주도'],
            'weaknesses': ['과도한 시간', '무한 수정', '과도한 개입'],
            'tips': ['시간 관리', '수정 제한', '완성 우선']
        },
        # R3-S1-Wx (analyze-textual-x)
        {
            'type_key': 'analyze-textual-summary',
            'type_code': 'R3-S1-W1',
            'type_name': '비판적 정리형',
            'combo': '분석비평가 × 교재토론러 × 핵심정리왕',
            'desc': '글을 비판적으로 분석하고, 텍스트에 충실하게 토론하며, 핵심을 정리하는 유형입니다.',
            'reading': '글의 논리 구조를 파악하고, 주장과 근거를 구분하며, 비판적으로 읽습니다.',
            'speaking': '텍스트 내용을 정확히 인용하며, 논리적 문제점을 지적하고 개선점을 제안합니다.',
            'writing': '핵심 논지를 정확히 파악하여 간결하게 요약하며, 객관적으로 서술합니다.',
            'strengths': ['비판적 사고', '논리 파악', '핵심 정리', '객관성'],
            'weaknesses': ['부정적 표현', '텍스트 의존', '감성 부족'],
            'tips': ['긍정적 표현', '자기 의견 추가', '감정 표현 연습']
        },
        {
            'type_key': 'analyze-textual-logic',
            'type_code': 'R3-S1-W2',
            'type_name': '논리 완벽형',
            'combo': '분석비평가 × 교재토론러 × 논리설계사',
            'desc': '분석력, 텍스트 충실성, 논리적 구조화를 모두 갖춘 완벽한 논리형입니다.',
            'reading': '글의 구조를 분석하고, 논리적 흠결을 발견하며, 비판적으로 독해합니다.',
            'speaking': '텍스트 기반으로 논리적으로 발언하며, 체계적으로 반박하고 대안을 제시합니다.',
            'writing': '서론-본론-결론이 완벽하며, 논리적 일관성과 체계성이 매우 높습니다.',
            'strengths': ['완벽한 논리', '비판적 분석', '체계성', '설득력'],
            'weaknesses': ['과도한 비판', '딱딱함', '감성 부족'],
            'tips': ['긍정적 피드백', '유연한 사고', '감성 더하기']
        },
        {
            'type_key': 'analyze-textual-rewrite',
            'type_code': 'R3-S1-W3',
            'type_name': '비판적 개선형',
            'combo': '분석비평가 × 교재토론러 × 재구성작가',
            'desc': '비판적으로 분석하고, 텍스트에 충실하며, 창의적으로 재구성하는 유형입니다.',
            'reading': '논리 구조를 파악하고 문제점을 발견하며, 대안적 구조를 상상합니다.',
            'speaking': '텍스트 기반으로 정확히 인용하되, 개선 방안을 제시하고 재구성을 제안합니다.',
            'writing': '글의 구조적 문제를 발견하고 창의적으로 개선하며, 지속적으로 퇴고합니다.',
            'strengths': ['비판적 분석', '창의적 개선', '구조 재설계', '완성도'],
            'weaknesses': ['과도한 비판', '무한 수정', '완성 지연'],
            'tips': ['긍정적 피드백', '수정 제한', '완성 우선']
        },
        # R3-S2-Wx (analyze-expand-x)
        {
            'type_key': 'analyze-expand-summary',
            'type_code': 'R3-S2-W1',
            'type_name': '통찰 정리형',
            'combo': '분석비평가 × 확장사고가 × 핵심정리왕',
            'desc': '비판적으로 분석하고, 폭넓게 확장하며, 핵심을 정리하는 통찰력 있는 유형입니다.',
            'reading': '논리 구조를 파악하고, 다른 분야와 연결하며, 비판적으로 독해합니다.',
            'speaking': '분석적으로 접근하되 다양한 관점을 제시하며, 지식을 연결하고 확장합니다.',
            'writing': '복잡한 논의를 핵심만 간결하게 정리하며, 명료하게 표현합니다.',
            'strengths': ['비판적 통찰', '지식 연결', '핵심 파악', '명료함'],
            'weaknesses': ['주제 이탈', '비판 과다', '정리 부족'],
            'tips': ['핵심 유지', '긍정적 표현', '시간 관리']
        },
        {
            'type_key': 'analyze-expand-logic',
            'type_code': 'R3-S2-W2',
            'type_name': '융합 사고형',
            'combo': '분석비평가 × 확장사고가 × 논리설계사',
            'desc': '비판적 분석, 확장 사고, 논리적 구조화를 모두 갖춘 융합형 사고자입니다.',
            'reading': '논리를 분석하고, 다양한 분야와 연결하며, 비판적으로 통찰합니다.',
            'speaking': '분석적으로 접근하되 창의적으로 확장하며, 체계적으로 종합합니다.',
            'writing': '완벽한 논리 구조에 다양한 관점을 녹여내며, 설득력이 매우 높습니다.',
            'strengths': ['비판적 통찰', '창의적 확장', '논리적 종합', '설득력'],
            'weaknesses': ['복잡도 증가', '시간 과다', '결론 도출 어려움'],
            'tips': ['단순화', '주제 중심', '시간 관리']
        },
        {
            'type_key': 'analyze-expand-rewrite',
            'type_code': 'R3-S2-W3',
            'type_name': '창조적 혁신형',
            'combo': '분석비평가 × 확장사고가 × 재구성작가',
            'desc': '비판적 분석, 확장 사고, 창의적 재구성을 모두 갖춘 최고의 혁신가입니다.',
            'reading': '논리를 분석하고, 다양한 관점을 연결하며, 대안을 모색합니다.',
            'speaking': '분석적으로 접근하되 창의적으로 확장하며, 혁신적 해결책을 제시합니다.',
            'writing': '구조를 비판적으로 분석하여 창의적으로 재설계하며, 독창적 글을 씁니다.',
            'strengths': ['비판적 통찰', '창의적 확장', '혁신적 재구성', '독창성'],
            'weaknesses': ['극도로 복잡', '완성 매우 지연', '과도한 야심'],
            'tips': ['단계별 완성', '현실적 목표', '70% 원칙']
        },
        # R3-S3-Wx (analyze-lead-x)
        {
            'type_key': 'analyze-lead-summary',
            'type_code': 'R3-S3-W1',
            'type_name': '전략적 리더형',
            'combo': '분석비평가 × 토론리더 × 핵심정리왕',
            'desc': '비판적으로 분석하고, 토론을 이끌며, 핵심을 정리하는 전략적 리더입니다.',
            'reading': '논리 구조를 파악하고, 핵심 쟁점을 발견하며, 비판적으로 독해합니다.',
            'speaking': '논의를 분석하여 흐름을 조정하며, 핵심 질문으로 토론을 이끕니다.',
            'writing': '핵심 논지를 명확히 정리하며, 간결하고 명료하게 표현합니다.',
            'strengths': ['비판적 분석', '흐름 조정', '핵심 파악', '리더십'],
            'weaknesses': ['비판 과다', '갈등 유발', '자기 의견 부족'],
            'tips': ['긍정적 리더십', '건설적 비판', '주장력 강화']
        },
        {
            'type_key': 'analyze-lead-logic',
            'type_code': 'R3-S3-W2',
            'type_name': '논리 리더형',
            'combo': '분석비평가 × 토론리더 × 논리설계사',
            'desc': '비판적 분석, 리더십, 논리적 구조화를 모두 갖춘 이상적 리더입니다.',
            'reading': '논리 구조를 완벽히 파악하고, 비판적으로 분석하며, 통찰합니다.',
            'speaking': '논의를 구조화하여 체계적으로 진행하며, 논리적으로 합의를 도출합니다.',
            'writing': '완벽한 논리 구조로 설득력 높은 글을 쓰며, 체계적으로 전개합니다.',
            'strengths': ['비판적 통찰', '논리 구조화', '체계적 리더십', '합의 도출'],
            'weaknesses': ['과도한 비판', '딱딱함', '유연성 부족'],
            'tips': ['긍정적 리더십', '유연한 사고', '감성 더하기']
        },
        {
            'type_key': 'analyze-lead-rewrite',
            'type_code': 'R3-S3-W3',
            'type_name': '비전 제시형',
            'combo': '분석비평가 × 토론리더 × 재구성작가',
            'desc': '비판적 분석, 리더십, 창의적 개선을 모두 갖춘 비전을 제시하는 변혁적 리더입니다.',
            'reading': '논리를 분석하고 문제점을 발견하며, 혁신적 대안을 모색합니다.',
            'speaking': '논의를 재구성하고 새로운 방향을 제시하며, 변화를 주도합니다.',
            'writing': '구조를 비판적으로 분석하여 창의적으로 재설계하며, 설득력 있게 제안합니다.',
            'strengths': ['비판적 통찰', '변혁적 리더십', '창의적 혁신', '비전 제시'],
            'weaknesses': ['과도한 변화 추구', '급진적', '갈등 유발'],
            'tips': ['점진적 변화', '공감대 형성', '경청']
        },
    ]

    print(f"⏳ {len(types_data)}개 유형 삽입 중...")

    for idx, type_data in enumerate(types_data, start=1):
        mbti_type = ReadingMBTIType(
            type_key=type_data['type_key'],
            type_code=type_data['type_code'],
            type_name=type_data['type_name'],
            combo_description=type_data['combo'],
            full_description=type_data['desc'],
            reading_style=type_data['reading'],
            speaking_style=type_data['speaking'],
            writing_style=type_data['writing'],
            strengths=type_data['strengths'],
            weaknesses=type_data['weaknesses'],
            tips=type_data['tips']
        )
        db.session.add(mbti_type)

        if idx % 9 == 0:
            print(f"  ✓ {idx}개 유형 삽입 완료...")

    db.session.commit()
    print(f"\n✅ {len(types_data)}개 유형 삽입 완료!")

    # 확인
    print("\n" + "=" * 70)
    print("📊 최종 확인")
    print("=" * 70)

    test_count = ReadingMBTITest.query.count()
    question_count = ReadingMBTIQuestion.query.count()
    type_count = ReadingMBTIType.query.count()

    print(f"✅ 테스트: {test_count}개")
    print(f"✅ 질문: {question_count}개")
    print(f"✅ 유형: {type_count}개")

    print("\n" + "=" * 70)
    print("🎉 Phase 1 완료!")
    print("=" * 70)
    print("\n다음 단계:")
    print("- Phase 2: 학생 테스트 기능 구현")
    print("- Phase 3: 결과 표시 & 분석")
    print("- Phase 4: 교사/학부모 기능")
    print("=" * 70)
