# -*- coding: utf-8 -*-
"""학부모 대시보드 점수 데이터 진단"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('FLASK_ENV', 'production')
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import logging
logging.disable(logging.CRITICAL)

from app import create_app
from app.models import db, Student, User
from app.models.essay import Essay, EssayResult
from app.models.course import CourseEnrollment

app = create_app()
with app.app_context():
    from app.models.parent_student import ParentStudent

    # 모든 학부모 계정 조회
    parents = User.query.filter_by(role='parent').all()
    print(f"전체 학부모 계정: {len(parents)}명\n")

    for parent in parents:
        relations = ParentStudent.query.filter_by(
            parent_id=parent.user_id, is_active=True
        ).all()
        children = [r.student for r in relations if r.student]
        if not children:
            continue

        print(f"[학부모] {parent.name} (user_id={parent.user_id})")
        for child in children:
            essays = Essay.query.filter_by(student_id=child.student_id).all()
            scored = [e for e in essays if e.result and e.result.total_score is not None]
            completed = [e for e in essays if e.status == 'completed']
            print(f"  └ 자녀: {child.name} (student_id={child.student_id})")
            print(f"      전체 첨삭: {len(essays)}건 | 완료: {len(completed)}건 | 점수있음: {len(scored)}건")
            if scored:
                for e in scored[:3]:
                    print(f"      → {e.title[:20]} | total_score={e.result.total_score} | completed_at={e.completed_at}")
            elif essays:
                # EssayResult 존재 여부 확인
                for e in essays[:3]:
                    has_result = e.result is not None
                    score = e.result.total_score if has_result else 'N/A'
                    print(f"      → {e.title[:20]} | result존재={has_result} | total_score={score} | status={e.status}")
        print()
