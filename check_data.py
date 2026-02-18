"""데이터 확인 스크립트"""
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import Essay, EssayResult, EssayScore, Student

app = create_app()
with app.app_context():
    # 전체 첨삭 수
    total_essays = Essay.query.count()
    print(f'📝 전체 첨삭 수: {total_essays}건')

    # 점수가 있는 첨삭 수
    essays_with_scores = Essay.query.join(EssayResult).filter(
        EssayResult.total_score.isnot(None)
    ).count()
    print(f'📊 점수가 있는 첨삭: {essays_with_scores}건')

    # 학생 수
    students = Student.query.count()
    print(f'👥 전체 학생 수: {students}명')

    # 18개 지표가 있는 첨삭 확인
    score_count = EssayScore.query.count()
    print(f'🎯 저장된 지표 점수: {score_count}개')

    if essays_with_scores > 0:
        print('\n✅ 차트를 확인할 수 있습니다!')
        # 점수가 있는 첨삭 정보 출력
        essay = Essay.query.join(EssayResult).filter(
            EssayResult.total_score.isnot(None)
        ).first()
        if essay:
            print(f'\n예시 첨삭:')
            print(f'  - 학생: {essay.student.name}')
            print(f'  - 총점: {essay.result.total_score}점')
            print(f'  - 등급: {essay.result.final_grade}')
            print(f'  - 버전: v{essay.current_version}')

            # 학생 ID 출력
            print(f'\n학생 상세 페이지 URL:')
            print(f'http://localhost:5000/students/{essay.student.student_id}')
    else:
        print('\n⚠️  점수 데이터가 없습니다.')
        print('새 첨삭을 생성하면 자동으로 점수가 파싱됩니다!')
        print('\n테스트용 학생 목록:')
        for student in Student.query.limit(3).all():
            print(f'  - {student.name} ({student.grade})')
            print(f'    URL: http://localhost:5000/students/{student.student_id}')
