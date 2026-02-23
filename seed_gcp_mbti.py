#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GCP용 독서 논술 MBTI 시드 스크립트
   - DATABASE_URL 환경변수를 설정하여 gunicorn과 동일한 instance/momoai.db 사용
   - 표준 버전 + 초등 버전 테스트 생성
   - 27가지 유형 데이터 생성
"""
import sys
import os
sys.path.insert(0, '/home/chsh82/momoai_web')
os.chdir('/home/chsh82/momoai_web')

# gunicorn과 동일한 DATABASE_URL 설정
os.environ['DATABASE_URL'] = 'sqlite:///momoai.db'

from app import create_app
from app.models import db
from app.models.reading_mbti import (
    ReadingMBTITest, ReadingMBTIQuestion, ReadingMBTIType
)

app = create_app()

with app.app_context():
    print("=" * 60)
    print("독서 논술 MBTI 시드 데이터 삽입 (GCP)")
    print("=" * 60)

    # ── 1. 27가지 유형 생성 ───────────────────────────────────
    existing_types = ReadingMBTIType.query.count()
    if existing_types >= 27:
        print(f"SKIP: 유형 데이터 이미 존재 ({existing_types}개)")
    else:
        print("\n[1단계] 27가지 유형 데이터 삽입")
        ReadingMBTIType.query.delete()
        db.session.commit()

        levels = {
            'beginner': {'code': '1', 'name': '초급'},
            'intermediate': {'code': '2', 'name': '중급'},
            'advanced': {'code': '3', 'name': '고급'}
        }
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

        for read_level in ['beginner', 'intermediate', 'advanced']:
            for speech_level in ['beginner', 'intermediate', 'advanced']:
                for write_level in ['beginner', 'intermediate', 'advanced']:
                    type_key = f"{read_level}-{speech_level}-{write_level}"
                    type_code = f"R{levels[read_level]['code']}-S{levels[speech_level]['code']}-W{levels[write_level]['code']}"

                    read_name = levels[read_level]['name']
                    speech_name = levels[speech_level]['name']
                    write_name = levels[write_level]['name']

                    if read_level == speech_level == write_level:
                        if read_level == 'beginner':
                            type_name, combo_desc = "기초 학습자", "모든 영역에서 기본기를 다지는 단계"
                        elif read_level == 'intermediate':
                            type_name, combo_desc = "균형 발전형", "모든 영역이 고르게 발달한 학습자"
                        else:
                            type_name, combo_desc = "통합 마스터", "모든 영역에서 고급 역량을 갖춘 학습자"
                    else:
                        max_level = max([read_level, speech_level, write_level],
                                        key=lambda x: ['beginner', 'intermediate', 'advanced'].index(x))
                        if max_level == 'advanced':
                            if read_level == 'advanced':
                                type_name, combo_desc = f"{read_name}독해 전문가", "독해력이 뛰어난 분석적 학습자"
                            elif speech_level == 'advanced':
                                type_name, combo_desc = f"{speech_name}토론 리더", "사고력과 토론 능력이 뛰어난 학습자"
                            else:
                                type_name, combo_desc = f"{write_name}작문 전문가", "서술력이 뛰어난 표현적 학습자"
                        elif max_level == 'intermediate':
                            if read_level == 'intermediate':
                                type_name, combo_desc = f"{read_name}독해 발전형", "독해력이 성장 중인 학습자"
                            elif speech_level == 'intermediate':
                                type_name, combo_desc = f"{speech_name}토론 성장형", "사고력이 발달 중인 학습자"
                            else:
                                type_name, combo_desc = f"{write_name}작문 성장형", "서술력이 향상 중인 학습자"
                        else:
                            type_name, combo_desc = "잠재력 발굴형", "기초를 다지며 성장하는 학습자"

                    full_desc = (f"이 유형은 독해력이 {read_name} 수준, 사고력(토론)이 {speech_name} 수준, "
                                 f"서술력이 {write_name} 수준인 학습자입니다.")

                    strengths, weaknesses, tips = [], [], []
                    if read_level == 'advanced':
                        strengths.append("복잡한 텍스트를 빠르게 이해하고 분석할 수 있음")
                        tips.append("심화 독서를 통해 배경지식을 넓히세요")
                    elif read_level == 'intermediate':
                        strengths.append("체계적으로 읽고 주요 내용을 파악할 수 있음")
                        tips.append("비판적 독해 연습으로 분석력을 키우세요")
                    else:
                        weaknesses.append("긴 글이나 복잡한 내용을 이해하는 데 시간이 필요함")
                        tips.append("매일 꾸준히 읽고 모르는 단어를 정리하세요")

                    if speech_level == 'advanced':
                        strengths.append("논리적으로 사고하고 창의적으로 표현할 수 있음")
                        tips.append("디베이트나 발표 기회를 적극 활용하세요")
                    elif speech_level == 'intermediate':
                        strengths.append("여러 관점을 이해하고 논리적으로 설명할 수 있음")
                        tips.append("토론 활동에 참여하며 다양한 관점을 연습하세요")
                    else:
                        weaknesses.append("즉흥적인 발표나 토론에서 어려움을 느낌")
                        tips.append("생각을 미리 정리하고 발표 연습을 자주 하세요")

                    if write_level == 'advanced':
                        strengths.append("논리적이고 창의적인 글쓰기가 가능함")
                        tips.append("다양한 장르의 글쓰기에 도전하세요")
                    elif write_level == 'intermediate':
                        strengths.append("체계적으로 구조화하여 글을 쓸 수 있음")
                        tips.append("글쓰기 후 퇴고하는 습관을 들이세요")
                    else:
                        weaknesses.append("긴 글을 쓰거나 논리적으로 전개하는 것이 어려움")
                        tips.append("짧은 글부터 시작해 점진적으로 분량을 늘려가세요")

                    db.session.add(ReadingMBTIType(
                        type_key=type_key,
                        type_code=type_code,
                        type_name=type_name,
                        combo_description=combo_desc,
                        full_description=full_desc,
                        reading_style=reading_styles[read_level],
                        speaking_style=speaking_styles[speech_level],
                        writing_style=writing_styles[write_level],
                        strengths=strengths,
                        weaknesses=weaknesses if weaknesses else ["현재 특별한 약점은 발견되지 않았습니다"],
                        tips=tips
                    ))

        db.session.commit()
        print(f"OK: 27개 유형 삽입 완료")

    # ── 2. 표준 버전 테스트 (중고등) ─────────────────────────
    existing_std = ReadingMBTITest.query.filter_by(version='standard').first()
    if existing_std:
        print(f"\nSKIP: 표준 버전 테스트 이미 존재 (ID={existing_std.test_id})")
    else:
        print("\n[2단계] 표준 버전 테스트 삽입 (중고등)")
        test_std = ReadingMBTITest(
            title='MOMO 논술 MBTI 역량 진단',
            description='독해력, 사고력, 서술력을 9가지 세부 능력으로 분석하여 학습자 수준을 진단하는 시스템',
            is_active=True,
            version='standard'
        )
        db.session.add(test_std)
        db.session.commit()

        std_questions = [
            # 읽기 초급
            ('read', 'beginner', '글을 읽다가 모르는 단어가 나오면 그 자리에서 사전이나 검색을 통해 찾아본다'),
            ('read', 'beginner', '문장에서 "그러나", "따라서" 같은 접속어를 보면 앞뒤 문맥을 연결해서 의미를 파악한다'),
            ('read', 'beginner', '"민주주의"와 "민주정치"처럼 비슷한 단어의 차이를 구분하려고 노력한다'),
            ('read', 'beginner', '같은 단어라도 문맥에 따라 의미가 달라진다는 것을 알고 주의해서 읽는다'),
            ('read', 'beginner', '새로운 단어를 배우면 예문을 찾아보거나 직접 문장을 만들어본다'),
            # 읽기 중급
            ('read', 'intermediate', '중요한 지문은 시험 전이나 과제할 때 최소 2번 이상 다시 읽는다'),
            ('read', 'intermediate', '같은 글을 다시 읽으면 "아, 이런 의미였구나" 하고 새롭게 이해되는 부분이 있다'),
            ('read', 'intermediate', '글을 읽을 때 중요한 숫자, 날짜, 고유명사 등을 놓치지 않으려고 신경 쓴다'),
            ('read', 'intermediate', '저자가 직접 말하지 않았지만 암시하는 내용이 무엇인지 생각하며 읽는다'),
            ('read', 'intermediate', '처음 읽을 때보다 두 번째 읽을 때 내용이 훨씬 더 잘 이해된다'),
            # 읽기 고급
            ('read', 'advanced', '글을 읽을 때 "이 글의 구조는 원인→결과, 문제제기→해결방안" 같은 틀을 파악한다'),
            ('read', 'advanced', '글에서 저자의 주장과 주장을 뒷받침하는 근거를 구분하며 읽는다'),
            ('read', 'advanced', '글을 읽다가 "이 근거로는 주장이 약한데"라고 의문을 가질 때가 있다'),
            ('read', 'advanced', '글을 읽고 나서 "이 주장에 동의하는가"를 스스로 판단해본다'),
            ('read', 'advanced', '글을 읽으면 "이 내용을 우리 학교/우리 동네에 적용하면"처럼 확장해서 생각한다'),
            # 말하기 초급
            ('speech', 'beginner', '토론할 때 "교과서 00페이지에 보면~"처럼 책 내용을 정확히 인용한다'),
            ('speech', 'beginner', '내 생각을 말할 때 "제 의견은 크게 3가지입니다"처럼 구조화해서 말한다'),
            ('speech', 'beginner', '토론 중 내 주장을 할 때 반드시 책이나 자료의 내용을 근거로 제시한다'),
            ('speech', 'beginner', '친구가 발표할 때 끝까지 듣고 "그 부분은 ~라는 뜻인가요"처럼 질문한다'),
            ('speech', 'beginner', '토론할 때 정해진 순서를 지키고 다른 사람 말을 끊지 않으려고 노력한다'),
            # 말하기 중급
            ('speech', 'intermediate', '토론 주제가 나오면 "이건 뉴스에서 본 000 사건과 비슷하네"라고 연결한다'),
            ('speech', 'intermediate', '찬성 입장에서 보면 이렇고, 반대 입장에서 보면 저렇다처럼 여러 시각으로 본다'),
            ('speech', 'intermediate', '내 주장을 설명할 때 "예를 들어"라며 실제 있었던 일이나 경험을 이야기한다'),
            ('speech', 'intermediate', '환경 문제를 토론하다가 "이건 경제 문제와도 연결되는데"처럼 주제를 확장한다'),
            ('speech', 'intermediate', '주장을 말할 때 논리적 설명과 함께 "이렇게 되면 우리가 불편하잖아요"처럼 감정도 섞는다'),
            # 말하기 고급
            ('speech', 'advanced', '토론이 막히면 "그럼 이런 관점에서는 어떨까요"라며 새로운 질문을 던진다'),
            ('speech', 'advanced', '토론 중 "지금까지 나온 의견을 정리하면~"이라며 흐름을 정리한다'),
            ('speech', 'advanced', '여러 친구들의 다른 의견을 듣고 "A와 B의 공통점은 ~이네요"라고 연결한다'),
            ('speech', 'advanced', '토론하다가 "우리가 놓친 부분이 있는데 000은 어떨까"라고 제시한다'),
            ('speech', 'advanced', '조별 토론에서 "A는 찬성 의견 말하고, B는 반대 의견 말해볼래"처럼 역할을 나눈다'),
            # 쓰기 초급
            ('write', 'beginner', '긴 글을 읽고 나서 핵심 내용 3-5가지를 뽑아낼 수 있다'),
            ('write', 'beginner', '요약할 때 "이건 예시니까 빼고, 이건 핵심이니까 넣자"라고 판단한다'),
            ('write', 'beginner', '요약문을 쓸 때 한 문장이 20자를 넘지 않도록 짧고 간결하게 쓴다'),
            ('write', 'beginner', '요약할 때 "내 생각에는~"이 아니라 글쓴이의 내용만 객관적으로 쓴다'),
            ('write', 'beginner', '내가 쓴 요약문만 읽어도 원문의 핵심을 이해할 수 있도록 작성한다'),
            # 쓰기 중급
            ('write', 'intermediate', '글을 쓰기 전에 "이 글의 주제는 정확히 무엇인가"를 먼저 정한다'),
            ('write', 'intermediate', '글을 쓸 때 서론-본론-결론 순서로 구조를 잡고 쓴다'),
            ('write', 'intermediate', '주장을 쓴 다음 "왜냐하면~"으로 근거를 연결하며 논리적으로 쓴다'),
            ('write', 'intermediate', '어려운 개념을 설명할 때 "쉽게 말하면", "예를 들어"를 사용해서 풀어쓴다'),
            ('write', 'intermediate', '결론 부분에서 서론의 질문에 대한 명확한 답을 제시한다'),
            # 쓰기 고급
            ('write', 'advanced', '친구 글을 읽으면 "이 부분은 순서를 바꾸면 더 좋겠다"라는 생각이 든다'),
            ('write', 'advanced', '내 글을 다시 읽으면 "이 문장과 저 문장의 연결이 어색하네"를 발견한다'),
            ('write', 'advanced', '같은 주제로 글을 쓰더라도 "이번엔 전혀 다른 방식으로 써볼까"라고 시도한다'),
            ('write', 'advanced', '글을 쓸 때 "반대 입장에서는 이렇게 반박하겠지"를 미리 생각하고 대응한다'),
            ('write', 'advanced', '내 글에 다른 사람의 시각이나 비유를 섞어서 더 풍부하게 만든다'),
        ]
        for i, (area, cat, text) in enumerate(std_questions, 1):
            db.session.add(ReadingMBTIQuestion(
                test_id=test_std.test_id, question_type='absolute',
                order=i, area=area, category=cat, text=text
            ))

        # 비교 질문 5개
        comparison_std = [
            (46, '다음 중 나에게 가장 잘 맞는 학습 방법은?',
             [{'t': '어려운 개념은 반복해서 읽고 외워서 완벽하게 이해한다', 'v': 'read:beginner:2,read:intermediate:3'},
              {'t': '책의 전체 구조와 흐름을 파악한 후 세부 내용을 공부한다', 'v': 'read:intermediate:2,read:advanced:3'},
              {'t': '내용을 비판적으로 검토하고 다른 자료와 비교하며 공부한다', 'v': 'read:advanced:3,speech:advanced:2'}]),
            (47, '토론할 때 나의 강점은?',
             [{'t': '자료를 정확히 인용하고 체계적으로 말할 수 있다', 'v': 'speech:beginner:3,speech:intermediate:2'},
              {'t': '여러 관점을 제시하고 논리적으로 반박할 수 있다', 'v': 'speech:intermediate:3,speech:advanced:2'},
              {'t': '토론을 이끌고 의견을 종합해서 새로운 해결책을 제시한다', 'v': 'speech:advanced:3,write:advanced:2'}]),
            (48, '글을 쓸 때 나의 스타일은?',
             [{'t': '핵심 내용을 간결하고 명확하게 정리해서 쓴다', 'v': 'write:beginner:3,write:intermediate:2'},
              {'t': '논리적 구조를 잡고 체계적으로 서술한다', 'v': 'write:intermediate:3,write:advanced:2'},
              {'t': '기존 내용을 비판적으로 재구성하고 창의적으로 표현한다', 'v': 'write:advanced:3,read:advanced:2'}]),
            (49, '새로운 주제를 학습할 때 나의 방식은?',
             [{'t': '기본 개념과 용어를 먼저 정확히 이해한다', 'v': 'read:beginner:2,write:beginner:2,speech:beginner:1'},
              {'t': '전체 맥락을 파악하고 다른 사람에게 설명해본다', 'v': 'read:intermediate:2,speech:intermediate:2,write:intermediate:1'},
              {'t': '비판적으로 분석하고 나만의 관점으로 재해석한다', 'v': 'read:advanced:2,speech:advanced:2,write:advanced:1'}]),
            (50, '과제나 시험을 준비할 때 나의 강점은?',
             [{'t': '중요한 내용을 빠짐없이 정리하고 암기한다', 'v': 'read:beginner:1,read:intermediate:2,write:beginner:2'},
              {'t': '논리적으로 구조화하고 예시를 들어 설명한다', 'v': 'read:intermediate:1,speech:intermediate:2,write:intermediate:2'},
              {'t': '창의적으로 재구성하고 심화 내용까지 확장한다', 'v': 'read:advanced:1,speech:advanced:2,write:advanced:2'}]),
        ]
        for order, text, options in comparison_std:
            db.session.add(ReadingMBTIQuestion(
                test_id=test_std.test_id, question_type='comparison',
                order=order, text=text, options=options
            ))

        db.session.commit()
        print(f"OK: 표준 버전 테스트 삽입 완료 (ID={test_std.test_id}, 질문 50개)")

    # ── 3. 초등 버전 테스트 ───────────────────────────────────
    existing_elem = ReadingMBTITest.query.filter_by(version='elementary').first()
    if existing_elem:
        print(f"\nSKIP: 초등 버전 테스트 이미 존재 (ID={existing_elem.test_id})")
    else:
        print("\n[3단계] 초등 버전 테스트 삽입")
        test_elem = ReadingMBTITest(
            title='MOMO 논술 MBTI 역량 진단 (초등)',
            description='독해력, 사고력, 서술력을 9가지 세부 능력으로 분석하는 초등학생용 자가평가 시스템',
            is_active=True,
            version='elementary'
        )
        db.session.add(test_elem)
        db.session.commit()

        elem_questions = [
            # 독해 초급
            ('read', 'beginner', '글을 읽다가 모르는 단어가 나오면 사전이나 어른에게 물어봐서 뜻을 알아봐요.'),
            ('read', 'beginner', "글에서 '그런데', '그래서' 같은 말이 나오면 앞뒤 내용을 연결해서 무슨 뜻인지 생각해봐요."),
            ('read', 'beginner', "'바다'와 '강'처럼 비슷하지만 다른 단어의 차이를 구분하려고 해요."),
            ('read', 'beginner', '같은 단어라도 문장에 따라 뜻이 달라질 수 있다는 걸 알고 주의해서 읽어요.'),
            ('read', 'beginner', '새로운 단어를 배우면 그 단어를 써서 짧은 문장을 만들어봐요.'),
            # 독해 중급
            ('read', 'intermediate', '중요한 글은 숙제나 시험 전에 두 번 이상 다시 읽어봐요.'),
            ('read', 'intermediate', '같은 글을 다시 읽으면 처음에 몰랐던 내용이 새롭게 이해될 때가 있어요.'),
            ('read', 'intermediate', '글을 읽을 때 중요한 숫자나 이름이 나오면 놓치지 않으려고 신경 써요.'),
            ('read', 'intermediate', '글쓴이가 직접 말하지 않아도 어떤 말을 하고 싶은지 생각하면서 읽어요.'),
            ('read', 'intermediate', '처음 읽을 때보다 두 번째 읽을 때 내용이 훨씬 잘 이해돼요.'),
            # 독해 고급
            ('read', 'advanced', "'왜냐하면~', '그래서~'처럼 글의 흐름을 파악하면서 읽어요."),
            ('read', 'advanced', '글에서 글쓴이의 생각(주장)과 그 이유(근거)를 구분하면서 읽어요.'),
            ('read', 'advanced', "'이 이유로는 좀 부족한 것 같은데?'라는 생각이 들 때가 있어요."),
            ('read', 'advanced', "'나는 이 생각에 동의하나?'를 스스로 생각해봐요."),
            ('read', 'advanced', "'이 내용을 우리 학교나 우리 동네에 적용하면 어떨까?'라고 생각을 넓혀봐요."),
            # 발표/토론 초급
            ('speech', 'beginner', "'책 00쪽에 보면~'처럼 읽은 내용을 정확하게 이야기해요."),
            ('speech', 'beginner', "'제 의견은 두 가지예요'처럼 순서를 정해서 말해요."),
            ('speech', 'beginner', '내 생각을 말할 때 꼭 책이나 자료에서 찾은 이유를 함께 이야기해요.'),
            ('speech', 'beginner', "'그 말은 ~라는 뜻이야?'라고 질문해봐요."),
            ('speech', 'beginner', '토론할 때 순서를 지키고 친구가 말하는 도중에 끼어들지 않으려고 노력해요.'),
            # 발표/토론 중급
            ('speech', 'intermediate', "'이거 뉴스에서 본 것이랑 비슷하네!'라고 연결해서 생각해요."),
            ('speech', 'intermediate', '찬성하는 쪽과 반대하는 쪽 두 가지 모두 생각해봐요.'),
            ('speech', 'intermediate', "'예를 들어, 내가 경험한 것처럼~'이라며 실제 이야기를 해요."),
            ('speech', 'intermediate', "'이건 돈 문제와도 연결되는 것 같아!'라고 생각을 넓혀봐요."),
            ('speech', 'intermediate', "논리적인 설명도 하고 '이러면 우리가 힘들잖아요'처럼 감정도 표현해요."),
            # 발표/토론 고급
            ('speech', 'advanced', "'그럼 이런 생각은 어때요?'라며 새로운 질문을 던져봐요."),
            ('speech', 'advanced', "'지금까지 나온 의견을 정리하면~'이라고 흐름을 정리해줘요."),
            ('speech', 'advanced', "'두 의견의 공통점은 ~이네요'라고 연결해봐요."),
            ('speech', 'advanced', "'우리가 빠뜨린 부분이 있는데, ~은 어떨까?'라고 새로운 의견을 내봐요."),
            ('speech', 'advanced', "모둠 토론에서 역할을 나눠줘요."),
            # 쓰기 초급
            ('write', 'beginner', '긴 글을 읽고 나서 중요한 내용 3~5가지를 골라낼 수 있어요.'),
            ('write', 'beginner', "'이건 예시니까 빼고, 이건 중요하니까 넣자'라고 스스로 판단해요."),
            ('write', 'beginner', '요약문을 쓸 때 너무 길지 않게 짧고 간결한 문장으로 쓰려고 노력해요.'),
            ('write', 'beginner', '요약할 때 내 생각은 빼고 글쓴이의 내용만 그대로 정리해요.'),
            ('write', 'beginner', '내가 쓴 요약문만 읽어도 원래 글의 중요한 내용을 알 수 있도록 써요.'),
            # 쓰기 중급
            ('write', 'intermediate', "'내가 하고 싶은 말이 뭔지'를 먼저 생각해서 정해요."),
            ('write', 'intermediate', '글을 쓸 때 처음-가운데-끝 순서로 구조를 먼저 생각하고 써요.'),
            ('write', 'intermediate', "'왜냐하면~'으로 이유를 이어서 써요."),
            ('write', 'intermediate', "'쉽게 말하면', '예를 들어'를 사용해서 풀어서 써요."),
            ('write', 'intermediate', '글의 끝부분에서 처음에 했던 질문에 대한 내 답을 분명하게 써요.'),
            # 쓰기 고급
            ('write', 'advanced', "'이 부분 순서를 바꾸면 더 좋겠다'는 생각이 들어요."),
            ('write', 'advanced', "'이 문장과 저 문장이 어색하게 연결됐네'를 발견해요."),
            ('write', 'advanced', "'이번엔 다른 방식으로 써볼까?'라고 시도해봐요."),
            ('write', 'advanced', "'반대 입장에서는 어떻게 반박할까?'를 미리 생각하고 대응해요."),
            ('write', 'advanced', '내 글에 다른 사람의 생각이나 비유를 넣어서 더 풍부하게 만들어요.'),
        ]
        for i, (area, cat, text) in enumerate(elem_questions, 1):
            db.session.add(ReadingMBTIQuestion(
                test_id=test_elem.test_id, question_type='absolute',
                order=i, area=area, category=cat, text=text
            ))

        comparison_elem = [
            (46, '다음 중 나에게 가장 잘 맞는 공부 방법은 뭐예요?',
             [{'t': '어려운 내용은 여러 번 읽고 외워서 완전히 이해해요.', 'v': 'read:beginner:2,read:intermediate:3'},
              {'t': '글 전체의 흐름을 먼저 파악하고 나서 세부 내용을 공부해요.', 'v': 'read:intermediate:2,read:advanced:3'},
              {'t': '내용을 꼼꼼히 살펴보고 다른 자료와 비교하면서 공부해요.', 'v': 'read:advanced:3,speech:advanced:2'}]),
            (47, '토론할 때 내가 가장 잘하는 건 뭐예요?',
             [{'t': '자료를 정확히 인용하고 차근차근 이야기할 수 있어요.', 'v': 'speech:beginner:3,speech:intermediate:2'},
              {'t': '여러 관점을 제시하고 논리적으로 반박할 수 있어요.', 'v': 'speech:intermediate:3,speech:advanced:2'},
              {'t': '토론을 이끌고 의견을 모아서 새로운 해결책을 제시해요.', 'v': 'speech:advanced:3,write:advanced:2'}]),
            (48, '글을 쓸 때 나의 스타일은 뭐예요?',
             [{'t': '핵심 내용을 간결하고 명확하게 정리해서 써요.', 'v': 'write:beginner:3,write:intermediate:2'},
              {'t': '논리적인 순서를 잡고 체계적으로 써요.', 'v': 'write:intermediate:3,write:advanced:2'},
              {'t': '내용을 새롭게 재구성하고 창의적으로 표현해요.', 'v': 'write:advanced:3,read:advanced:2'}]),
            (49, '새로운 주제를 배울 때 나의 방식은 뭐예요?',
             [{'t': '기본 개념과 용어를 먼저 정확히 이해해요.', 'v': 'read:beginner:2,write:beginner:2,speech:beginner:1'},
              {'t': '전체 내용을 파악하고 친구에게 설명해봐요.', 'v': 'read:intermediate:2,speech:intermediate:2,write:intermediate:1'},
              {'t': '꼼꼼히 분석하고 나만의 생각으로 새롭게 정리해요.', 'v': 'read:advanced:2,speech:advanced:2,write:advanced:1'}]),
            (50, '과제나 시험을 준비할 때 내가 가장 잘하는 건 뭐예요?',
             [{'t': '중요한 내용을 빠짐없이 정리하고 암기해요.', 'v': 'read:beginner:1,read:intermediate:2,write:beginner:2'},
              {'t': '논리적으로 구조화하고 예시를 들어 설명해요.', 'v': 'read:intermediate:1,speech:intermediate:2,write:intermediate:2'},
              {'t': '창의적으로 재구성하고 더 깊은 내용까지 공부해요.', 'v': 'read:advanced:1,speech:advanced:2,write:advanced:2'}]),
        ]
        for order, text, options in comparison_elem:
            db.session.add(ReadingMBTIQuestion(
                test_id=test_elem.test_id, question_type='comparison',
                order=order, text=text, options=options
            ))

        db.session.commit()
        print(f"OK: 초등 버전 테스트 삽입 완료 (ID={test_elem.test_id}, 질문 50개)")

    print("\n" + "=" * 60)
    print("완료!")
    types_count = ReadingMBTIType.query.count()
    std_count = ReadingMBTITest.query.filter_by(version='standard').count()
    elem_count = ReadingMBTITest.query.filter_by(version='elementary').count()
    print(f"  유형: {types_count}개 | 표준 테스트: {std_count}개 | 초등 테스트: {elem_count}개")
    print("=" * 60)
