#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""완료된 첨삭 중 total_score가 비어있는 건을, 서버에 남아있는 원본 HTML을
새 파서(score_parser.py, 2026-09-04 수정)로 다시 읽어서 채운다.

처음엔 "총점만 못 뽑고 세부지표 18개는 이미 저장돼 있다"고 생각해서 그
세부지표 평균으로 총점만 역산하려 했으나, 실제로는 원인이 달랐다:
AI가 생성하는 첨삭 HTML에 신/구 두 템플릿이 섞여 있고, 요즘 템플릿(cc/ct/
il/iv/ss 같은 축약 클래스, parse_elementary_html용으로 만든 것과 동일한
체계)을 correction_model='standard'/'harkness'인 essay에도 그대로 쓰는데
parse_html()의 풀네임 클래스 기반 추출기가 이걸 전혀 인식 못 해서 총점은
물론 세부지표 18개까지 통째로 저장이 안 되고 있었다. 그래서 이 스크립트는
essay_scores에서 역산하는 게 아니라 essay_results.html_path의 원본
HTML 파일을 다시 파싱해서 total_score와 essay_scores(18개 지표)를 모두
새로 채운다.

"manual_" 접두사 파일(html_path에 포함)은 건너뛴다 - 교사가 첨부파일로
직접 첨삭한 케이스라 애초에 파싱할 점수 데이터가 없는 게 정상이다.
부모 Essay가 이미 삭제된 고아 essay_results도 건너뛴다(사이트 전체에
26건뿐, 학생이 볼 화면 자체가 없어 채워도 의미 없음).

같은 version_id의 기존 essay_scores를 지우고 새로 쓰므로(momoai_service.py
의 저장 로직과 동일 패턴) 재실행해도 안전하다 - 이미 total_score가 채워진
행은 애초에 대상에서 제외되므로 두 번 실행해도 중복 저장되지 않는다.

실행:
    python scripts/backfill_essay_total_score.py --production --dry-run   # 먼저 확인
    python scripts/backfill_essay_total_score.py --production             # 실제 적용
"""
import sys
import io
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.essay import Essay, EssayResult
from app.models.essay_score import EssayScore
from app.essays.score_parser import get_parser


def main():
    dry_run = '--dry-run' in sys.argv
    app = create_app('production' if '--production' in sys.argv else 'development')
    with app.app_context():
        parser = get_parser()

        targets = EssayResult.query.filter(EssayResult.total_score.is_(None)).all()
        print(f"total_score가 비어있는 essay_results {len(targets)}건 대상")

        filled, manual_skipped, orphan_skipped, no_file, parse_failed = 0, 0, 0, 0, 0

        for r in targets:
            if r.html_path and '/manual_' in r.html_path.replace('\\', '/'):
                manual_skipped += 1
                continue

            essay = Essay.query.get(r.essay_id)
            if essay is None:
                orphan_skipped += 1
                continue

            if not r.html_path or not os.path.exists(r.html_path):
                no_file += 1
                continue

            with open(r.html_path, encoding='utf-8') as f:
                html_content = f.read()

            parsed = parser.parse_html(html_content)
            if not parsed.get('success') or parsed.get('total_score') is None:
                parse_failed += 1
                continue

            if dry_run:
                print(f"  [dry-run] essay_id={r.essay_id} version_id={r.version_id} "
                      f"-> total_score={parsed['total_score']}, "
                      f"지표 {len(parsed['thinking_types']) + len(parsed['integrated_indicators'])}개")
            else:
                r.total_score = parsed['total_score']
                if parsed.get('final_grade'):
                    r.final_grade = parsed['final_grade']

                EssayScore.query.filter_by(version_id=r.version_id).delete()
                for category, indicator_name, score in parser.get_all_scores_list(parsed):
                    db.session.add(EssayScore(
                        essay_id=r.essay_id,
                        version_id=r.version_id,
                        category=category,
                        indicator_name=indicator_name,
                        score=score,
                    ))
            filled += 1

        if dry_run:
            print(f"\n[dry-run] 채울 수 있는 건: {filled}건")
        else:
            db.session.commit()
            print(f"\n완료: {filled}건 채움(총점 + 세부지표)")
        print(f"제외 - manual(교사 첨부파일): {manual_skipped}건, "
              f"고아(부모 essay 없음): {orphan_skipped}건, "
              f"HTML 파일 없음: {no_file}건, 재파싱해도 실패: {parse_failed}건")


if __name__ == '__main__':
    main()
