# -*- coding: utf-8 -*-
"""
MBTI 기반 상담 기록 테스트 스크립트
"""
import sys
import io

# Windows 콘솔 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app, db
from app.models import Student, User
from app.models.consultation import ConsultationRecord
from app.models.reading_mbti import ReadingMBTIResult
from app.utils.mbti_recommendations import (
    get_student_latest_mbti,
    generate_teaching_recommendations,
    format_recommendations_for_consultation
)
from datetime import date

app = create_app()

with app.app_context():
    print("=" * 60)
    print("MBTI 기반 상담 기록 시스템 테스트")
    print("=" * 60)

    # 1. 테스트할 학생 선택 (MBTI 결과가 있는 학생)
    students_with_mbti = db.session.query(Student).join(
        ReadingMBTIResult, Student.student_id == ReadingMBTIResult.student_id
    ).all()

    print(f"\n✅ MBTI 검사를 완료한 학생: {len(students_with_mbti)}명\n")

    if not students_with_mbti:
        print("❌ MBTI 검사 결과가 있는 학생이 없습니다.")
        print("먼저 독서 논술 MBTI 검사를 진행해주세요.")
        exit()

    # 첫 번째 학생으로 테스트
    test_student = students_with_mbti[0]

    print(f"📚 테스트 학생: {test_student.name} ({test_student.grade})")
    print(f"   학생 ID: {test_student.student_id}")

    # 2. 학생의 최신 MBTI 결과 조회
    mbti_result = get_student_latest_mbti(test_student.student_id)

    if mbti_result:
        print(f"\n🎯 MBTI 유형: {mbti_result.mbti_type.type_name}")
        print(f"   유형 코드: {mbti_result.type_combination}")
        print(f"   검사일: {mbti_result.created_at.strftime('%Y-%m-%d')}")

        # 3. 추천 생성
        print("\n" + "=" * 60)
        print("📊 MBTI 기반 수업 추천 생성 중...")
        print("=" * 60)

        recommendations = generate_teaching_recommendations(mbti_result)

        if recommendations:
            print(f"\n✨ 유형명: {recommendations['type_name']}")
            print(f"📝 조합 설명: {recommendations['combo_description']}\n")

            print("━" * 60)
            print("📚 독서 스타일:")
            print(f"   {recommendations['reading_style']}\n")

            print("💬 말하기 스타일:")
            print(f"   {recommendations['speaking_style']}\n")

            print("✍️ 쓰기 스타일:")
            print(f"   {recommendations['writing_style']}\n")

            print("━" * 60)
            print("✨ 강점:")
            for i, strength in enumerate(recommendations['strengths'], 1):
                print(f"   {i}. {strength}")

            print("\n⚠️ 보완 필요 영역:")
            for i, weakness in enumerate(recommendations['weaknesses'], 1):
                print(f"   {i}. {weakness}")

            print("\n💡 수업 진행 팁:")
            for i, tip in enumerate(recommendations['tips'], 1):
                print(f"   {i}. {tip}")

            print("\n" + "━" * 60)
            print("🎓 추천 교수법:")
            for approach in recommendations['recommended_approaches']:
                print(f"   • {approach}")

            # 4. 상담 기록에 사용할 텍스트 생성
            print("\n" + "=" * 60)
            print("📝 상담 기록용 텍스트 생성")
            print("=" * 60 + "\n")

            consultation_text = format_recommendations_for_consultation(mbti_result)
            print(consultation_text)

            # 5. 실제 상담 기록 생성 예시
            print("\n" + "=" * 60)
            print("💾 상담 기록 생성 테스트")
            print("=" * 60)

            # 관리자/강사 찾기
            counselor = User.query.filter(User.role_level <= 2).first()

            if counselor:
                # 테스트 상담 기록 생성
                test_consultation = ConsultationRecord(
                    consultation_date=date.today(),
                    counselor_id=counselor.user_id,
                    student_id=test_student.student_id,
                    major_category='신규상담',
                    title=f'{test_student.name} 학생 MBTI 기반 수업 계획',
                    content=f"""
{test_student.name} 학생의 독서 논술 MBTI 검사 결과를 바탕으로 맞춤형 수업 계획을 수립했습니다.

[상담 내용]
- MBTI 검사 결과 분석
- 학생의 학습 스타일 파악
- 강점 및 보완 영역 확인
- 최적화된 교수법 선정

[향후 계획]
- 학생의 MBTI 유형에 맞는 수업 진행
- 주기적인 학습 성과 모니터링
- 필요시 교수법 조정
                    """.strip(),
                    student_mbti_type=mbti_result.type_combination,
                    recommended_teaching_style=recommendations['type_name'],
                    teaching_recommendations=consultation_text,
                    share_with_parents=True  # 학부모 공유
                )

                db.session.add(test_consultation)
                db.session.commit()

                print(f"\n✅ 상담 기록이 생성되었습니다!")
                print(f"   상담 ID: {test_consultation.consultation_id}")
                print(f"   제목: {test_consultation.title}")
                print(f"   상담자: {counselor.name}")
                print(f"   학부모 공유: {'예' if test_consultation.share_with_parents else '아니오'}")

                # 생성된 상담 기록 확인
                print("\n" + "━" * 60)
                print("📋 생성된 상담 기록 내용:")
                print("━" * 60)
                print(f"\n제목: {test_consultation.title}")
                print(f"\n상담 내용:")
                print(test_consultation.content)
                print(f"\n\nMBTI 기반 추천:")
                print(test_consultation.teaching_recommendations)
            else:
                print("\n❌ 상담자(관리자/강사)를 찾을 수 없습니다.")
        else:
            print("\n❌ 추천 생성 실패")
    else:
        print(f"\n❌ {test_student.name} 학생의 MBTI 결과를 찾을 수 없습니다.")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
