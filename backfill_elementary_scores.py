# -*- coding: utf-8 -*-
"""
초등(elementary) 모델 첨삭의 점수를 기존 HTML에서 역산하여 DB에 저장.
- EssayResult.total_score == NULL 인 elementary 첨삭 대상
- EssayVersion.html_content 에서 polygon 좌표 역산
- AI 재호출 없음
"""
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
from app.models import db
from app.models.essay import Essay, EssayResult, EssayVersion
from app.models.essay_score import EssayScore
from app.essays.score_parser import get_parser

app = create_app()
with app.app_context():
    parser = get_parser()

    # elementary 모델이며 total_score가 없는 essay 대상
    targets = db.session.query(Essay, EssayResult, EssayVersion)\
        .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
        .join(EssayVersion, EssayResult.version_id == EssayVersion.version_id)\
        .filter(
            Essay.correction_model == 'elementary',
            EssayResult.total_score.is_(None),
            EssayVersion.html_content.isnot(None)
        ).all()

    print(f"대상 첨삭: {len(targets)}건\n")

    ok = 0
    failed = 0
    for essay, result, version in targets:
        student_name = essay.student.name if essay.student else '알수없음'
        try:
            parsed = parser.parse_elementary_html(version.html_content)
            if not parsed.get('success') or parsed.get('total_score') is None:
                print(f"  ❌ SKIP {essay.essay_id} [{student_name}] - 파싱 실패")
                failed += 1
                continue

            result.total_score = parsed['total_score']
            result.final_grade = parsed.get('final_grade')

            # 기존 점수 삭제 후 재저장
            EssayScore.query.filter_by(version_id=version.version_id).delete()
            scores_list = parser.get_all_scores_list(parsed)
            for category, indicator_name, score in scores_list:
                db.session.add(EssayScore(
                    essay_id=essay.essay_id,
                    version_id=version.version_id,
                    category=category,
                    indicator_name=indicator_name,
                    score=score
                ))

            db.session.commit()
            print(f"  ✅ {essay.essay_id} [{student_name}] 총점={parsed['total_score']} 등급={parsed.get('final_grade')} 지표={len(scores_list)}개")
            ok += 1

        except Exception as e:
            db.session.rollback()
            print(f"  ❌ ERROR {essay.essay_id} [{student_name}]: {e}")
            failed += 1

    print(f"\n완료: 성공={ok}, 실패={failed}")
