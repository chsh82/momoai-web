#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""완료된 첨삭 중 total_score가 비어있는 건을 세부 지표(essay_scores)
평균으로 역산해서 채운다.

score_parser.py의 parse_html()이 AI가 생성한 HTML에서 "최종점수" 표기를
못 찾으면 total_score를 그냥 None으로 남기는 버그가 있었다(2026-09-04
발견 - 완료된 첨삭 2,509건 중 1,339건/53%에서 발생). 사고유형/통합지표
18개 세부 점수는 별도 경로(SVG 파싱)로 항상 정상 저장되므로, 이 스크립트는
parse_html()에 새로 추가한 것과 동일한 공식(0.5×사고유형평균×10 +
0.5×통합지표평균×10)으로 이미 저장된 essay_results 중 total_score만
비어있는 행을 채운다. 원본 데이터를 지우거나 바꾸지 않고 NULL인 필드만
채우므로 몇 번을 실행해도 안전하다(이미 채워진 행은 건드리지 않음).

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
from app.models.essay import EssayResult
from app.models.essay_score import EssayScore


def compute_total_score(version_id):
    rows = EssayScore.query.filter_by(version_id=version_id).all()
    t_vals = [float(r.score) for r in rows if r.category == '사고유형']
    i_vals = [float(r.score) for r in rows if r.category == '통합지표']
    if not t_vals and not i_vals:
        return None
    t_mean = sum(t_vals) / len(t_vals) if t_vals else 0.0
    i_mean = sum(i_vals) / len(i_vals) if i_vals else 0.0
    return round(0.50 * (t_mean * 10) + 0.50 * (i_mean * 10), 1)


def main():
    dry_run = '--dry-run' in sys.argv
    app = create_app('production' if '--production' in sys.argv else 'development')
    with app.app_context():
        targets = EssayResult.query.filter(EssayResult.total_score.is_(None)).all()
        print(f"total_score가 비어있는 essay_results {len(targets)}건 대상")

        filled, skipped = 0, 0
        for r in targets:
            score = compute_total_score(r.version_id)
            if score is None:
                skipped += 1
                continue
            if dry_run:
                print(f"  [dry-run] essay_id={r.essay_id} version_id={r.version_id} -> {score}")
            else:
                r.total_score = score
            filled += 1

        if dry_run:
            print(f"\n[dry-run] 채울 수 있는 건: {filled}건, 세부지표도 없어 못 채우는 건: {skipped}건")
            print("[dry-run] --dry-run 없이 재실행하면 실제로 저장합니다.")
        else:
            db.session.commit()
            print(f"\n완료: {filled}건 채움, 세부지표도 없어 못 채운 건: {skipped}건")


if __name__ == '__main__':
    main()
