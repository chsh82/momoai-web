"""
데모 데이터 생성 스크립트
차트 확인용 테스트 데이터를 생성합니다.
"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db, Essay, EssayVersion, EssayResult, EssayScore
from datetime import datetime, timedelta
import random

app = create_app()

def create_demo_essay(student_id, user_id, version_num=1, days_ago=0):
    """데모 첨삭 생성"""

    # 랜덤 점수 생성 (70-95점 범위)
    base_score = random.uniform(70, 95)

    # Essay 생성
    essay = Essay(
        student_id=student_id,
        user_id=user_id,
        title=f'논술문 {version_num}',
        original_text='테스트용 논술문입니다.',
        grade='중등',
        status='completed',
        current_version=version_num,
        is_finalized=True,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
        completed_at=datetime.utcnow() - timedelta(days=days_ago),
        finalized_at=datetime.utcnow() - timedelta(days=days_ago)
    )
    db.session.add(essay)
    db.session.flush()  # essay_id 생성

    # EssayVersion 생성
    version = EssayVersion(
        essay_id=essay.essay_id,
        version_number=version_num,
        html_content='<html><body>Demo HTML</body></html>',
        html_path='/demo/path.html'
    )
    db.session.add(version)
    db.session.flush()  # version_id 생성

    # 등급 계산
    if base_score >= 90:
        grade = 'A+'
    elif base_score >= 85:
        grade = 'A'
    elif base_score >= 80:
        grade = 'B+'
    elif base_score >= 75:
        grade = 'B'
    else:
        grade = 'C+'

    # EssayResult 생성
    result = EssayResult(
        essay_id=essay.essay_id,
        version_id=version.version_id,
        html_path='/demo/path.html',
        total_score=base_score,
        final_grade=grade
    )
    db.session.add(result)

    # 18개 지표 점수 생성
    thinking_types = ['요약', '비교', '적용', '평가', '비판', '문제해결', '자료해석', '견해제시', '종합']
    integrated_indicators = ['결론', '구조/논리성', '표현/명료성', '문제인식', '개념/정보',
                             '목적/적절성', '관점/다각성', '심층성', '완전성']

    # 사고유형 점수 (0-10점, 평균이 base_score/10 정도 되도록)
    for indicator in thinking_types:
        score = random.uniform(
            max(0, (base_score/10) - 2),
            min(10, (base_score/10) + 2)
        )
        essay_score = EssayScore(
            essay_id=essay.essay_id,
            version_id=version.version_id,
            category='사고유형',
            indicator_name=indicator,
            score=round(score, 1)
        )
        db.session.add(essay_score)

    # 통합지표 점수
    for indicator in integrated_indicators:
        score = random.uniform(
            max(0, (base_score/10) - 2),
            min(10, (base_score/10) + 2)
        )
        essay_score = EssayScore(
            essay_id=essay.essay_id,
            version_id=version.version_id,
            category='통합지표',
            indicator_name=indicator,
            score=round(score, 1)
        )
        db.session.add(essay_score)

    return essay

def main():
    print("=" * 60)
    print("📊 데모 데이터 생성 스크립트")
    print("=" * 60)

    with app.app_context():
        # 학생과 사용자 가져오기
        from app.models import Student, User

        student = Student.query.first()
        user = User.query.first()

        if not student or not user:
            print("❌ 학생이나 사용자가 없습니다.")
            print("먼저 test_students.py와 test_auth.py를 실행하세요.")
            return

        print(f"\n학생: {student.name}")
        print(f"사용자: {user.name}")

        # 5개의 첨삭 생성 (시간차를 두고)
        print("\n📝 첨삭 생성 중...")

        essays = []
        for i in range(1, 6):
            days_ago = (6 - i) * 3  # 15일 전, 12일 전, 9일 전, 6일 전, 3일 전
            essay = create_demo_essay(
                student_id=student.student_id,
                user_id=user.user_id,
                version_num=i,
                days_ago=days_ago
            )
            essays.append(essay)
            print(f"  ✅ 첨삭 {i} 생성 (총점: {essay.result.total_score:.1f}점, 등급: {essay.result.final_grade})")

        # 커밋
        db.session.commit()

        print("\n" + "=" * 60)
        print("✅ 데모 데이터 생성 완료!")
        print("=" * 60)

        print(f"\n📊 생성된 데이터:")
        print(f"  - 첨삭: {len(essays)}건")
        print(f"  - 지표 점수: {len(essays) * 18}개")

        print(f"\n🌐 학생 상세 페이지:")
        print(f"http://localhost:5000/students/{student.student_id}")

        print("\n💡 이제 브라우저에서 위 URL을 열어보세요!")
        print("   📈 점수 변화 추이 라인 차트")
        print("   🎯 18개 지표 레이더 차트 2개")
        print("   💪📈 강점/약점 분석")
        print("   이 모두를 확인하실 수 있습니다!")

if __name__ == '__main__':
    main()
