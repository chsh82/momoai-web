#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""공지사항 테스트 데이터 생성"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User
from app.models.announcement import Announcement
from datetime import datetime, timedelta

def create_test_announcements():
    """테스트용 공지사항 생성"""
    app = create_app('development')

    with app.app_context():
        # 관리자 계정 찾기
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("[ERROR] 관리자 계정을 찾을 수 없습니다.")
            return

        print(f"[OK] 관리자 계정: {admin.name} ({admin.email})")

        # 기존 테스트 공지사항 삭제
        existing = Announcement.query.filter(
            Announcement.title.like('%테스트%')
        ).all()
        for ann in existing:
            db.session.delete(ann)
        db.session.commit()
        print(f"[OK] 기존 테스트 공지사항 {len(existing)}개 삭제")

        # 테스트 공지사항 생성
        announcements = [
            {
                'title': '[테스트] 전체 공지사항 - 일반',
                'content': '이것은 전체 사용자를 대상으로 하는 일반 공지사항입니다.\n\n모든 사용자가 볼 수 있습니다.',
                'announcement_type': 'general',
                'target_roles': 'all',
                'is_pinned': True,
                'is_popup': False
            },
            {
                'title': '[테스트] 팝업 공지 - 긴급',
                'content': '이것은 로그인 시 팝업으로 표시되는 긴급 공지사항입니다!\n\n반드시 확인해주세요.',
                'announcement_type': 'urgent',
                'target_roles': 'all',
                'is_pinned': True,
                'is_popup': True
            },
            {
                'title': '[테스트] 학부모 전용 공지',
                'content': '학부모님들께 드리는 안내 말씀입니다.\n\n자녀의 학습 현황을 정기적으로 확인해 주세요.',
                'announcement_type': 'general',
                'target_roles': 'parent',
                'is_pinned': False,
                'is_popup': False
            },
            {
                'title': '[테스트] 강사 전용 공지',
                'content': '강사님들께 드리는 공지사항입니다.\n\n출석 체크를 빠짐없이 해주세요.',
                'announcement_type': 'general',
                'target_roles': 'teacher',
                'is_pinned': False,
                'is_popup': False
            },
            {
                'title': '[테스트] 학생 전용 공지 - 행사',
                'content': '학생 여러분! 다음 주에 특별 행사가 있습니다.\n\n많은 참여 부탁드립니다.',
                'announcement_type': 'event',
                'target_roles': 'student',
                'is_pinned': False,
                'is_popup': False
            },
            {
                'title': '[테스트] 시스템 점검 안내',
                'content': '시스템 정기 점검이 예정되어 있습니다.\n\n점검 시간: 2026년 2월 15일 02:00~04:00',
                'announcement_type': 'system',
                'target_roles': 'all',
                'is_pinned': False,
                'is_popup': True
            }
        ]

        created_count = 0
        for data in announcements:
            announcement = Announcement(
                author_id=admin.user_id,
                title=data['title'],
                content=data['content'],
                announcement_type=data['announcement_type'],
                target_roles=data['target_roles'],
                is_pinned=data['is_pinned'],
                is_popup=data['is_popup'],
                is_published=True,
                publish_start=datetime.utcnow() - timedelta(days=1),
                publish_end=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(announcement)
            created_count += 1

        db.session.commit()
        print(f"[OK] 테스트 공지사항 {created_count}개 생성 완료")

        # 생성된 공지사항 목록 출력
        print("\n=== 생성된 공지사항 목록 ===")
        all_announcements = Announcement.query.filter(
            Announcement.title.like('%테스트%')
        ).all()

        for ann in all_announcements:
            print(f"\n- {ann.title}")
            print(f"  유형: {ann.announcement_type}")
            print(f"  대상: {ann.target_roles}")
            print(f"  고정: {'예' if ann.is_pinned else '아니오'}")
            print(f"  팝업: {'예' if ann.is_popup else '아니오'}")

if __name__ == '__main__':
    print("=" * 50)
    print("공지사항 테스트 데이터 생성")
    print("=" * 50)
    create_test_announcements()
    print("\n[OK] 완료!")
