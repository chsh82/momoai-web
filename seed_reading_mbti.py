#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""독서 논술 MBTI 시스템 초기 데이터 삽입"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.reading_mbti import (
    ReadingMBTITest,
    ReadingMBTIQuestion,
    ReadingMBTIType
)

print("=" * 70)
print("📚 독서 논술 MBTI 시스템 초기 데이터 삽입")
print("=" * 70)

app = create_app('development')

with app.app_context():
    print("\n[1단계] 기존 데이터 확인")
    print("-" * 70)

    existing_test = ReadingMBTITest.query.first()
    if existing_test:
        print(f"⚠️  기존 테스트 발견: {existing_test.title}")
        confirm = input("기존 데이터를 삭제하고 새로 삽입하시겠습니까? (y/N): ")
        if confirm.lower() != 'y':
            print("취소되었습니다.")
            sys.exit(0)

        # 기존 데이터 삭제
        print("🗑️  기존 데이터 삭제 중...")
        ReadingMBTIResult.query.delete()
        ReadingMBTIResponse.query.delete()
        ReadingMBTIQuestion.query.delete()
        ReadingMBTIType.query.delete()
        ReadingMBTITest.query.delete()
        db.session.commit()
        print("✅ 기존 데이터 삭제 완료")

    # 1. 테스트 생성
    print("\n[2단계] 테스트 생성")
    print("-" * 70)

    test = ReadingMBTITest(
        title='MOMO 논술 MBTI 자가평가',
        description='학생들의 독서, 발표/토론, 쓰기 능력을 9가지 차원에서 분석하여 27가지 유형으로 진단하는 시스템',
        is_active=True
    )
    db.session.add(test)
    db.session.commit()
    print(f"✅ 테스트 생성 완료: {test.title} (ID: {test.test_id})")

    # 2. 45개 절대평가 질문 삽입
    print("\n[3단계] 45개 절대평가 질문 삽입")
    print("-" * 70)

    questions_data = [
        # 독해 영역 (Read) - 15문항
        # vocab (어휘탐험가) - 5문항
        {'area': 'read', 'cat': 'vocab', 'text': '글을 읽다가 모르는 단어가 나오면 그 자리에서 사전이나 검색을 통해 찾아본다'},
        {'area': 'read', 'cat': 'vocab', 'text': '문장에서 그러나, 따라서 같은 접속어를 보면 앞뒤 문맥을 연결해서 의미를 파악한다'},
        {'area': 'read', 'cat': 'vocab', 'text': '"민주주의"와 "민주정치"처럼 비슷한 단어의 차이를 구분하려고 노력한다'},
        {'area': 'read', 'cat': 'vocab', 'text': '같은 단어라도 문맥에 따라 의미가 달라진다는 것을 알고 주의해서 읽는다'},
        {'area': 'read', 'cat': 'vocab', 'text': '새로운 단어를 배우면 예문을 찾아보거나 직접 문장을 만들어본다'},

        # reread (반복독해왕) - 5문항
        {'area': 'read', 'cat': 'reread', 'text': '중요한 지문은 시험 전이나 과제할 때 최소 2번 이상 다시 읽는다'},
        {'area': 'read', 'cat': 'reread', 'text': '같은 글을 다시 읽으면 "아, 이런 의미였구나" 하고 새롭게 이해되는 부분이 있다'},
        {'area': 'read', 'cat': 'reread', 'text': '글을 읽을 때 중요한 숫자, 날짜, 고유명사 등을 놓치지 않으려고 신경 쓴다'},
        {'area': 'read', 'cat': 'reread', 'text': '저자가 직접 말하지 않았지만 암시하는 내용이 무엇인지 생각하며 읽는다'},
        {'area': 'read', 'cat': 'reread', 'text': '처음 읽을 때보다 두 번째 읽을 때 내용이 훨씬 더 잘 이해된다'},

        # analyze (분석비평가) - 5문항
        {'area': 'read', 'cat': 'analyze', 'text': '글을 읽을 때 "이 글의 구조는 원인→결과, 문제제기→해결방안" 같은 틀을 파악한다'},
        {'area': 'read', 'cat': 'analyze', 'text': '글에서 저자의 주장과 주장을 뒷받침하는 근거를 구분하며 읽는다'},
        {'area': 'read', 'cat': 'analyze', 'text': '글을 읽다가 "이 근거로는 주장이 약한데"라고 의문을 가질 때가 있다'},
        {'area': 'read', 'cat': 'analyze', 'text': '글을 읽고 나서 "이 주장에 동의하는가"를 스스로 판단해본다'},
        {'area': 'read', 'cat': 'analyze', 'text': '글을 읽으면 "이 내용을 우리 학교/우리 동네에 적용하면"처럼 확장해서 생각한다'},

        # 발표/토론 영역 (Speech) - 15문항
        # textual (교재토론러) - 5문항
        {'area': 'speech', 'cat': 'textual', 'text': '토론할 때 "교과서 00페이지에 보면~"처럼 책 내용을 정확히 인용한다'},
        {'area': 'speech', 'cat': 'textual', 'text': '내 생각을 말할 때 "제 의견은 크게 3가지입니다"처럼 구조화해서 말한다'},
        {'area': 'speech', 'cat': 'textual', 'text': '토론 중 내 주장을 할 때 반드시 책이나 자료의 내용을 근거로 제시한다'},
        {'area': 'speech', 'cat': 'textual', 'text': '친구가 발표할 때 끝까지 듣고 "그 부분은 ~라는 뜻인가요"처럼 질문한다'},
        {'area': 'speech', 'cat': 'textual', 'text': '토론할 때 정해진 순서를 지키고 다른 사람 말을 끊지 않으려고 노력한다'},

        # expand (확장사고가) - 5문항
        {'area': 'speech', 'cat': 'expand', 'text': '토론 주제가 나오면 "이건 뉴스에서 본 000 사건과 비슷하네"라고 연결한다'},
        {'area': 'speech', 'cat': 'expand', 'text': '찬성 입장에서 보면 이렇고, 반대 입장에서 보면 저렇다처럼 여러 시각으로 본다'},
        {'area': 'speech', 'cat': 'expand', 'text': '내 주장을 설명할 때 "예를 들어"라며 실제 있었던 일이나 경험을 이야기한다'},
        {'area': 'speech', 'cat': 'expand', 'text': '환경 문제를 토론하다가 "이건 경제 문제와도 연결되는데"처럼 주제를 확장한다'},
        {'area': 'speech', 'cat': 'expand', 'text': '주장을 말할 때 논리적 설명과 함께 "이렇게 되면 우리가 불편하잖아요"처럼 감정도 섞는다'},

        # lead (토론리더) - 5문항
        {'area': 'speech', 'cat': 'lead', 'text': '토론이 막히면 "그럼 이런 관점에서는 어떨까요"라며 새로운 질문을 던진다'},
        {'area': 'speech', 'cat': 'lead', 'text': '토론 중 "지금까지 나온 의견을 정리하면~"이라며 흐름을 정리한다'},
        {'area': 'speech', 'cat': 'lead', 'text': '여러 친구들의 다른 의견을 듣고 "A와 B의 공통점은 ~이네요"라고 연결한다'},
        {'area': 'speech', 'cat': 'lead', 'text': '토론하다가 "우리가 놓친 부분이 있는데 000은 어떨까"라고 제시한다'},
        {'area': 'speech', 'cat': 'lead', 'text': '조별 토론에서 "A는 찬성 의견 말하고, B는 반대 의견 말해볼래"처럼 역할을 나눈다'},

        # 쓰기 영역 (Write) - 15문항
        # summary (핵심정리왕) - 5문항
        {'area': 'write', 'cat': 'summary', 'text': '긴 글을 읽고 나서 핵심 내용 3-5가지를 뽑아낼 수 있다'},
        {'area': 'write', 'cat': 'summary', 'text': '요약할 때 "이건 예시니까 빼고, 이건 핵심이니까 넣자"라고 판단한다'},
        {'area': 'write', 'cat': 'summary', 'text': '요약문을 쓸 때 한 문장이 20자를 넘지 않도록 짧고 간결하게 쓴다'},
        {'area': 'write', 'cat': 'summary', 'text': '요약할 때 "내 생각에는~"이 아니라 글쓴이의 내용만 객관적으로 쓴다'},
        {'area': 'write', 'cat': 'summary', 'text': '내가 쓴 요약문만 읽어도 원문의 핵심을 이해할 수 있도록 작성한다'},

        # logic (논리설계사) - 5문항
        {'area': 'write', 'cat': 'logic', 'text': '글을 쓰기 전에 "이 글의 주제는 정확히 무엇인가"를 먼저 정한다'},
        {'area': 'write', 'cat': 'logic', 'text': '글을 쓸 때 서론-본론-결론 순서로 구조를 잡고 쓴다'},
        {'area': 'write', 'cat': 'logic', 'text': '주장을 쓴 다음 "왜냐하면~"으로 근거를 연결하며 논리적으로 쓴다'},
        {'area': 'write', 'cat': 'logic', 'text': '어려운 개념을 설명할 때 "쉽게 말하면", "예를 들어"를 사용해서 풀어쓴다'},
        {'area': 'write', 'cat': 'logic', 'text': '결론 부분에서 서론의 질문에 대한 명확한 답을 제시한다'},

        # rewrite (재구성작가) - 5문항
        {'area': 'write', 'cat': 'rewrite', 'text': '친구 글을 읽으면 "이 부분은 순서를 바꾸면 더 좋겠다"라는 생각이 든다'},
        {'area': 'write', 'cat': 'rewrite', 'text': '내 글을 다시 읽으면 "이 문장과 저 문장의 연결이 어색하네"를 발견한다'},
        {'area': 'write', 'cat': 'rewrite', 'text': '같은 내용도 "이걸 질문으로 시작하면 더 흥미롭겠다"처럼 다르게 표현해본다'},
        {'area': 'write', 'cat': 'rewrite', 'text': '글을 고칠 때 문장을 짧게 나누거나 한자어를 쉬운 말로 바꾼다'},
        {'area': 'write', 'cat': 'rewrite', 'text': '글을 쓰고 나서 "왜 이렇게 썼지? 더 나은 방법은 없을까?" 돌아본다'},
    ]

    for idx, q_data in enumerate(questions_data, start=1):
        question = ReadingMBTIQuestion(
            test_id=test.test_id,
            question_type='absolute',
            area=q_data['area'],
            category=q_data['cat'],
            text=q_data['text'],
            order=idx
        )
        db.session.add(question)

    db.session.commit()
    print(f"✅ 45개 절대평가 질문 삽입 완료")

    # 3. 5개 비교 선택 질문 삽입
    print("\n[4단계] 5개 비교 선택 질문 삽입")
    print("-" * 70)

    comparisons_data = [
        {
            'q': '글을 읽을 때 나는 주로:',
            'opts': [
                {'v': 'vocab', 't': '모르는 단어를 먼저 찾아보고 이해한다'},
                {'v': 'reread', 't': '일단 끝까지 읽고 다시 한 번 읽는다'},
                {'v': 'analyze', 't': '글의 논리 구조를 분석하며 읽는다'}
            ]
        },
        {
            'q': '토론 수업에서 나는:',
            'opts': [
                {'v': 'textual', 't': '책 내용을 근거로 차근차근 의견을 말한다'},
                {'v': 'expand', 't': '여러 지식을 연결해 주제를 확장한다'},
                {'v': 'lead', 't': '질문을 만들고 토론을 이끌어간다'}
            ]
        },
        {
            'q': '글쓰기 과제를 받았을 때 나는:',
            'opts': [
                {'v': 'summary', 't': '핵심 내용만 간결하게 정리한다'},
                {'v': 'logic', 't': '논리적 구조를 세워 체계적으로 쓴다'},
                {'v': 'rewrite', 't': '새로운 관점으로 재구성한다'}
            ]
        },
        {
            'q': '강점을 기르기 위해 나는:',
            'opts': [
                {'v': 'vocab', 't': '어휘력과 표현력을 키우고 싶다'},
                {'v': 'reread', 't': '독해력과 이해력을 키우고 싶다'},
                {'v': 'analyze', 't': '분석력과 비판력을 키우고 싶다'}
            ]
        },
        {
            'q': '나의 학습 스타일은:',
            'opts': [
                {'v': 'all_read', 't': '읽고 이해하는 것이 가장 편하다'},
                {'v': 'all_speech', 't': '말하고 토론하는 것이 가장 편하다'},
                {'v': 'all_write', 't': '쓰고 정리하는 것이 가장 편하다'}
            ]
        }
    ]

    for idx, comp_data in enumerate(comparisons_data, start=46):
        question = ReadingMBTIQuestion(
            test_id=test.test_id,
            question_type='comparison',
            text=comp_data['q'],
            options=comp_data['opts'],
            order=idx
        )
        db.session.add(question)

    db.session.commit()
    print(f"✅ 5개 비교 선택 질문 삽입 완료")

    print("\n[5단계] 27가지 유형 데이터 삽입")
    print("-" * 70)
    print("⏳ 27개 유형 삽입 중... (잠시만 기다려주세요)")

    # Continue in next part due to length...
