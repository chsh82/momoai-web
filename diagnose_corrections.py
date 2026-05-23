# -*- coding: utf-8 -*-
"""최근 첨삭 실패/성공 현황 및 API 사용량 진단."""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for env_file in ['.env.production', '.env']:
    env_path = os.path.join(BASE_DIR, env_file)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        break

sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app('production')

with app.app_context():
    # 1. 최근 7일 첨삭 현황
    print("\n" + "="*60)
    print("최근 7일 첨삭 현황")
    print("="*60)
    rows = db.session.execute(text("""
        SELECT status, correction_model, api_provider, COUNT(*) as cnt
        FROM essays
        WHERE created_at >= NOW() - INTERVAL '7 days'
        GROUP BY status, correction_model, api_provider
        ORDER BY cnt DESC
    """)).fetchall()
    for r in rows:
        print(f"  {r.status:12} | {r.correction_model:10} | {r.api_provider:8} | {r.cnt}건")

    # 2. 최근 실패한 첨삭 에러 메시지
    print("\n" + "="*60)
    print("최근 실패 첨삭 (최근 20건)")
    print("="*60)
    rows = db.session.execute(text("""
        SELECT e.essay_id, e.correction_model, e.api_provider,
               e.created_at, e.error_message
        FROM essays e
        WHERE e.status = 'failed'
        ORDER BY e.created_at DESC
        LIMIT 20
    """)).fetchall()
    if not rows:
        print("  실패 기록 없음")
    for r in rows:
        err = r.error_message or '(에러 메시지 없음 — 이번 배포 이전 실패)'
        print(f"\n  [{r.created_at}] {r.essay_id[:8]}... "
              f"모델={r.correction_model} 제공자={r.api_provider}")
        print(f"  에러: {err[:200]}")

    # 3. 최근 Claude API 성공 호출 시간 통계
    print("\n" + "="*60)
    print("최근 7일 Claude API 호출 통계")
    print("="*60)
    rows = db.session.execute(text("""
        SELECT usage_type, model_name,
               COUNT(*) as cnt,
               AVG(output_tokens) as avg_out,
               MAX(output_tokens) as max_out,
               AVG(cost_usd) as avg_cost,
               SUM(cost_usd) as total_cost
        FROM api_usage_logs
        WHERE api_type = 'claude'
          AND created_at >= NOW() - INTERVAL '7 days'
        GROUP BY usage_type, model_name
        ORDER BY cnt DESC
    """)).fetchall()
    if not rows:
        print("  API 사용 기록 없음")
    for r in rows:
        print(f"  {r.usage_type:15} | {r.model_name:25} | {r.cnt}건 | "
              f"평균출력={int(r.avg_out or 0):,}tok | "
              f"최대={int(r.max_out or 0):,}tok | "
              f"총비용=${r.total_cost or 0:.4f}")

    # 4. Rate Limit 에러 추정 (출력이 0인 실패 또는 처리 중 stuck)
    print("\n" + "="*60)
    print("장기 'processing' stuck 첨삭 (30분 이상)")
    print("="*60)
    rows = db.session.execute(text("""
        SELECT essay_id, correction_model, api_provider, created_at
        FROM essays
        WHERE status = 'processing'
          AND created_at < NOW() - INTERVAL '30 minutes'
        ORDER BY created_at DESC
    """)).fetchall()
    if not rows:
        print("  없음")
    for r in rows:
        print(f"  [{r.created_at}] {r.essay_id[:8]}... {r.correction_model} / {r.api_provider}")
