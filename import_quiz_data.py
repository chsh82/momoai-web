"""어휘퀴즈와 스키마퀴즈 데이터 임포트 스크립트"""

import pandas as pd
import json
from app import create_app, db
from app.models.vocabulary_quiz import VocabularyQuiz
from app.models.schema_quiz import SchemaQuiz

app = create_app()

# 레벨별 학년 매핑
LEVEL_GRADE_MAP = {
    1: ('초1', '초2'),
    2: ('초3', '초4'),
    3: ('초5', '초6'),
    4: ('중1', '중2'),
    5: ('중3', '고1'),
    6: ('고2', '고3')
}

# 단계별 학년 매핑 (스키마)
STAGE_GRADE_MAP = {
    '1단계': ('초1', '초3'),
    '2단계': ('초4', '초6'),
    '3단계': ('중1', '중3'),
    '4단계': ('고1', '고3')
}


def import_vocabulary_quizzes():
    """어휘 사전 데이터 임포트"""
    vocab_file = r'C:\Users\aproa\Downloads\학습 도구어 사전 레벨1~6 (0925최종버전).xlsx'

    print("어휘 사전 데이터 임포트 시작...")

    with app.app_context():
        # 기존 데이터 삭제
        VocabularyQuiz.query.delete()
        db.session.commit()

        total_count = 0

        for level in range(1, 7):
            sheet_name = f'Level{level}'
            print(f"\n{sheet_name} 처리 중...")

            # 엑셀 읽기 (헤더는 3번째 행, 데이터는 4번째 행부터)
            df = pd.read_excel(vocab_file, sheet_name=sheet_name, header=3)

            # NaN 값 제거
            df = df.dropna(subset=['어휘'])

            grade_start, grade_end = LEVEL_GRADE_MAP[level]

            for idx, row in df.iterrows():
                word = str(row['어휘']).strip() if pd.notna(row['어휘']) else ''
                meaning = str(row['의미']).strip() if pd.notna(row['의미']) else ''
                pos = str(row['품사']).strip() if pd.notna(row['품사']) else ''

                # Level 1-3: '유의어/반의어' 컬럼, Level 4-6: '유의어', '반의어' 별도 컬럼
                if '유의어/반의어' in df.columns:
                    synonyms = str(row['유의어/반의어']).strip() if pd.notna(row['유의어/반의어']) else ''
                else:
                    synonym_part = str(row['유의어']).strip() if '유의어' in df.columns and pd.notna(row['유의어']) else ''
                    antonym_part = str(row['반의어']).strip() if '반의어' in df.columns and pd.notna(row['반의어']) else ''
                    synonyms = f"{synonym_part}|{antonym_part}" if synonym_part or antonym_part else ''

                if not word or not meaning:
                    continue

                # 객관식 문제 생성을 위한 더미 데이터 (나중에 실제 선택지 생성 로직으로 교체)
                quiz = VocabularyQuiz(
                    word=word,
                    meaning=meaning,
                    example=f"{word}을(를) 사용한 예문",
                    level=level,
                    grade_start=grade_start,
                    grade_end=grade_end,
                    quiz_type='multiple_choice',
                    options=json.dumps([meaning, "오답1", "오답2", "오답3"], ensure_ascii=False),
                    correct_answer=meaning,
                    category='학습도구어'
                )

                db.session.add(quiz)
                total_count += 1

            db.session.commit()
            print(f"{sheet_name} 완료: {len(df)}개 단어 추가")

        print(f"\n총 {total_count}개의 어휘 퀴즈 데이터가 임포트되었습니다.")


def import_schema_quizzes():
    """스키마 어휘 데이터 임포트"""
    schema_file = r'C:\Users\aproa\Downloads\스키마 어휘 목록(1004 버전).xlsx'

    print("\n\n스키마 어휘 데이터 임포트 시작...")

    with app.app_context():
        # 기존 데이터 삭제
        SchemaQuiz.query.delete()
        db.session.commit()

        total_count = 0

        # 사회 스키마
        print("\n사회 스키마 처리 중...")
        df_social = pd.read_excel(schema_file, sheet_name='사회 스키마')
        df_social = df_social.dropna(subset=['단어명'])

        for idx, row in df_social.iterrows():
            term = str(row['단어명']).strip() if pd.notna(row['단어명']) else ''
            stage = str(row['단계']).strip() if pd.notna(row['단계']) else ''
            definition = str(row['정의']).strip() if pd.notna(row['정의']) else f"{term}에 대한 설명"
            category = f"{row['중분류']}" if pd.notna(row['중분류']) else '사회'

            if not term or stage not in STAGE_GRADE_MAP:
                continue

            grade_start, grade_end = STAGE_GRADE_MAP[stage]

            quiz = SchemaQuiz(
                term=term,
                definition=definition,
                subject='social',
                category=category,
                grade_start=grade_start,
                grade_end=grade_end,
                quiz_type='multiple_choice',
                options=json.dumps([definition, "오답1", "오답2", "오답3"], ensure_ascii=False),
                correct_answer=definition
            )

            db.session.add(quiz)
            total_count += 1

        db.session.commit()
        print(f"사회 스키마 완료: {len(df_social)}개 용어 추가")

        # 과학 스키마
        print("\n과학 스키마 처리 중...")
        df_science = pd.read_excel(schema_file, sheet_name='과학 스키마')
        df_science = df_science.dropna(subset=['단어명'])

        for idx, row in df_science.iterrows():
            term = str(row['단어명']).strip() if pd.notna(row['단어명']) else ''
            stage = str(row['단계']).strip() if pd.notna(row['단계']) else ''
            definition = str(row['정의']).strip() if pd.notna(row['정의']) else f"{term}에 대한 설명"
            category = f"{row['중분류']}" if pd.notna(row['중분류']) else '과학'

            if not term or stage not in STAGE_GRADE_MAP:
                continue

            grade_start, grade_end = STAGE_GRADE_MAP[stage]

            quiz = SchemaQuiz(
                term=term,
                definition=definition,
                subject='science',
                category=category,
                grade_start=grade_start,
                grade_end=grade_end,
                quiz_type='multiple_choice',
                options=json.dumps([definition, "오답1", "오답2", "오답3"], ensure_ascii=False),
                correct_answer=definition
            )

            db.session.add(quiz)
            total_count += 1

        db.session.commit()
        print(f"과학 스키마 완료: {len(df_science)}개 용어 추가")

        print(f"\n총 {total_count}개의 스키마 퀴즈 데이터가 임포트되었습니다.")


if __name__ == '__main__':
    print("=" * 60)
    print("퀴즈 데이터 임포트 시작")
    print("=" * 60)

    try:
        import_vocabulary_quizzes()
        import_schema_quizzes()

        print("\n" + "=" * 60)
        print("모든 데이터 임포트가 완료되었습니다!")
        print("=" * 60)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
