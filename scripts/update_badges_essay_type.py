#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""이미 배포된 BG01/BG03/BG07 뱃지 행을 과제 유형(essay_type) 기능에 맞게 갱신

scripts/seed_badges.py는 INSERT ONLY라 이미 존재하는 badge_code는 건너뛴다
(2026-08-18 배포에서 이미 10개가 다 들어가 있음). 그래서 essay_type 기능
추가로 바뀐 rule_config/description은 이 스크립트로 따로 UPDATE해야 한다.

바뀌는 내용(app/services/mileage_rules.py, scripts/seed_badges.py와 동일):
  BG01: rule_config {'source_type': 'post', ...} -> {'source_type': 'essay', ...}
        (첫 게시글 -> 첫 과제 제출. essays 테이블 직접 조회로 변경, 마일리지
        시작일 게이트 없음 - 기존에 쌓인 과제에도 소급 적용)
  BG03: rule_config {'activity_code': 'RW01', ...} -> {'source_type': 'essay',
        'essay_type': 'rewriting', ...} (point_events가 아니라 essays 테이블
        직접 조회 - 첨삭 확정 전 업로드 시점에 바로 판정하기 위함)
  BG07: threshold 100/50 -> 30/20 (마일리지 시작일 이후만 집계하도록
        badge_service.py의 카운트 함수도 함께 바뀜 - 이 스크립트는 rule_config만 갱신)

몇 번을 실행해도 안전하다 - 이미 새 값이면 건너뛴다.
"""
import sys
import io
import json
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.mileage import Badge

UPDATES = [
    {
        'badge_code': 'BG01',
        'description': '서비스 내 최초 과제(첨삭) 제출',
        'rule_config': {'source_type': 'essay', 'threshold': 1},
    },
    {
        'badge_code': 'BG03',
        'description': '리라이팅 최초 1편 제출',
        'rule_config': {'source_type': 'essay', 'essay_type': 'rewriting', 'threshold': 1},
    },
    {
        'badge_code': 'BG07',
        'description': '받은 댓글 누적 20개 또는 받은 좋아요 누적 30개(마일리지 시작일 이후)',
        'rule_config': {'metric': 'received_likes', 'threshold': 30,
                        'or_metric': 'received_comments', 'or_threshold': 20},
    },
]


def main():
    app = create_app('production' if '--production' in sys.argv else 'development')
    with app.app_context():
        updated, skipped = 0, 0
        for spec in UPDATES:
            badge = db.session.get(Badge, spec['badge_code'])
            if badge is None:
                print(f"  경고: {spec['badge_code']}가 DB에 없습니다 - seed_badges.py를 먼저 실행하세요.")
                continue

            new_config_json = json.dumps(spec['rule_config'], ensure_ascii=False)
            already_current = (badge.rule_config == new_config_json
                               and badge.description == spec['description'])
            if already_current:
                print(f"  건너뜀 (이미 최신): {spec['badge_code']}")
                skipped += 1
                continue

            print(f"  갱신: {spec['badge_code']}")
            print(f"    description: {badge.description!r} -> {spec['description']!r}")
            print(f"    rule_config: {badge.rule_config!r} -> {new_config_json!r}")
            badge.description = spec['description']
            badge.rule_config = new_config_json
            updated += 1

        db.session.commit()
        print(f"\n완료: 갱신 {updated}건, 건너뜀 {skipped}건")


if __name__ == '__main__':
    main()
