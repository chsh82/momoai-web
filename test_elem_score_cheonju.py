# -*- coding: utf-8 -*-
"""천주안 학생 elementary 점수 추출 테스트 및 저장"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)
os.environ.setdefault('FLASK_ENV', 'production')
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from app import create_app
from app.models import db, Student
from app.models.essay import Essay, EssayResult, EssayVersion
from app.models.essay_score import EssayScore
from app.essays.score_parser import get_parser

app = create_app()
with app.app_context():
    parser = get_parser()

    student = Student.query.filter_by(name='천주안').first()
    if not student:
        print("학생을 찾을 수 없습니다.")
        exit()

    print(f"=== 천주안 학생 초등 점수 추출 테스트 ===\n")

    targets = db.session.query(Essay, EssayResult, EssayVersion)\
        .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
        .join(EssayVersion, EssayResult.version_id == EssayVersion.version_id)\
        .filter(
            Essay.student_id == student.student_id,
            Essay.correction_model == 'elementary',
            EssayResult.total_score.is_(None),
            EssayVersion.html_content.isnot(None)
        ).order_by(Essay.completed_at.asc()).all()

    print(f"처리 대상: {len(targets)}건\n")

    ok = 0
    for essay, result, version in targets:
        parsed = parser.parse_elementary_html(version.html_content)
        title = (essay.title or '')[:20]

        if not parsed.get('success') or parsed.get('total_score') is None:
            print(f"  ❌ [{title}] 파싱 실패")
            continue

        t_scores = parsed.get('thinking_types', {})
        i_scores = parsed.get('integrated_indicators', {})
        total = parsed['total_score']
        grade = parsed.get('final_grade', '-')

        print(f"  📝 [{title}]")
        print(f"     등급: {grade}  총점: {total}")
        if t_scores:
            t_str = ', '.join(f"{k}={v}" for k, v in t_scores.items())
            print(f"     사고유형: {t_str}")
        if i_scores:
            i_str = ', '.join(f"{k}={v}" for k, v in i_scores.items())
            print(f"     통합지표: {i_str}")

        # DB 저장
        result.total_score = total
        result.final_grade = grade
        EssayScore.query.filter_by(version_id=version.version_id).delete()
        for category, indicator_name, score in parser.get_all_scores_list(parsed):
            db.session.add(EssayScore(
                essay_id=essay.essay_id,
                version_id=version.version_id,
                category=category,
                indicator_name=indicator_name,
                score=score
            ))
        db.session.commit()
        ok += 1

    print(f"\n✅ 저장 완료: {ok}건")
    print(f"\n이제 학부모 대시보드에서 천주안 학생의 점수 그래프를 확인하세요.")
