#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BG01~BG10 뱃지 정의 초기 데이터 삽입

정책 문서 docs/mileage/01_마일리지_운영정책.md 8.1절을 그대로 옮긴 것.
이미 있는 badge_code는 건너뛰므로 여러 번 실행해도 안전하다.

rule_config의 activity_code는 app/services/mileage_rules.py의 POINT_RULES
코드를 가리킨다. 실제 판정 로직(badge_service.py)은 3단계에서 구현한다 -
이 스크립트는 정의(데이터)만 넣는다.
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

BADGES = [
    {
        'badge_code': 'BG01', 'name': '첫 문장',
        'description': '서비스 내 최초 게시글 작성',
        'category': '초급', 'sort_order': 1, 'is_repeatable': False,
        'rule_type': 'first_event',
        'rule_config': {'source_type': 'post', 'threshold': 1},
    },
    {
        'badge_code': 'BG02', 'name': '첫 물음표',
        'description': '질문 최초 1건 승인',
        'category': '초급', 'sort_order': 2, 'is_repeatable': False,
        'rule_type': 'first_event',
        'rule_config': {'activity_code': 'QS01', 'threshold': 1},
    },
    {
        'badge_code': 'BG03', 'name': '첫 고쳐쓰기',
        'description': '리라이팅 최초 1편 제출',
        'category': '초급', 'sort_order': 3, 'is_repeatable': False,
        'rule_type': 'first_event',
        'rule_config': {'activity_code': 'RW01', 'threshold': 1},
    },
    {
        'badge_code': 'BG04', 'name': '빛나는 문장',
        'description': '우수답안 최초 1회 선정',
        'category': '중급', 'sort_order': 4, 'is_repeatable': True,
        'rule_type': 'first_event',
        'rule_config': {'activity_code': 'EX01', 'threshold': 1},
    },
    {
        'badge_code': 'BG05', 'name': '깊은 물음',
        'description': '우수질문 최초 1회 선정',
        'category': '중급', 'sort_order': 5, 'is_repeatable': True,
        'rule_type': 'first_event',
        'rule_config': {'activity_code': 'QS02', 'threshold': 1},
    },
    {
        'badge_code': 'BG06', 'name': '성실의 발자국',
        'description': '분기 무결석 완주 1회',
        'category': '중급', 'sort_order': 6, 'is_repeatable': True,
        'rule_type': 'first_event',
        'rule_config': {'activity_code': 'AT02', 'threshold': 1},
    },
    {
        'badge_code': 'BG07', 'name': '모두의 글',
        'description': '받은 댓글 누적 50개 또는 받은 좋아요 누적 100개',
        'category': '고급', 'sort_order': 7, 'is_repeatable': False,
        'rule_type': 'count_threshold',
        'rule_config': {'metric': 'received_likes', 'threshold': 100,
                        'or_metric': 'received_comments', 'or_threshold': 50},
    },
    {
        'badge_code': 'BG08', 'name': '사계절 독서가',
        'description': '4개 분기(1년) 수강 이수',
        'category': '고급', 'sort_order': 8, 'is_repeatable': False,
        'rule_type': 'count_threshold',
        'rule_config': {'metric': 'quarter_completed', 'threshold': 4},
    },
    {
        'badge_code': 'BG09', 'name': '장원',
        'description': '정기 모의고사에서 소속 레벨 1위',
        'category': '고급', 'sort_order': 9, 'is_repeatable': True,
        'rule_type': 'manual',
        'rule_config': {'note': '모의고사 성적 데이터가 서비스에 도입되기 전까지는 관리자가 수동으로 수여. '
                                '도입 후 external_metric으로 전환 예정(정책 8.2.5)'},
    },
    {
        'badge_code': 'BG10', 'name': '책장의 주인',
        'description': 'BG01~BG09 아홉 개 뱃지 전부 획득',
        'category': '최종', 'sort_order': 10, 'is_repeatable': False,
        'rule_type': 'all_badges',
        'rule_config': {'required_badges': ['BG01', 'BG02', 'BG03', 'BG04', 'BG05',
                                            'BG06', 'BG07', 'BG08', 'BG09']},
    },
]


def main():
    app = create_app('development')
    with app.app_context():
        created, skipped = 0, 0
        for spec in BADGES:
            if db.session.get(Badge, spec['badge_code']) is not None:
                print(f"  건너뜀 (이미 존재): {spec['badge_code']} {spec['name']}")
                skipped += 1
                continue

            badge = Badge(
                badge_code=spec['badge_code'],
                name=spec['name'],
                description=spec['description'],
                category=spec['category'],
                icon_path=None,  # 아이콘 자산은 4단계(화면) 작업에서 채움
                sort_order=spec['sort_order'],
                is_repeatable=spec['is_repeatable'],
                rule_type=spec['rule_type'],
                rule_config=json.dumps(spec['rule_config'], ensure_ascii=False),
                is_active=True,
            )
            db.session.add(badge)
            print(f"  추가: {spec['badge_code']} {spec['name']}")
            created += 1

        db.session.commit()
        print(f"\n완료: 신규 {created}건, 건너뜀 {skipped}건 (전체 {Badge.query.count()}건)")


if __name__ == '__main__':
    main()
