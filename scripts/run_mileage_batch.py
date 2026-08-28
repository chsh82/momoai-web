#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""마일리지 배치 수동 실행 스크립트

사용 예:
    python scripts/run_mileage_batch.py confirm --dry-run
    python scripts/run_mileage_batch.py weekly --week 2026-W36 --dry-run
    python scripts/run_mileage_batch.py quarterly --quarter 2026Q1 --dry-run
    python scripts/run_mileage_batch.py ranking --season 2026-08 --dry-run
    python scripts/run_mileage_batch.py ranking --season 2026-08 --finalize
    python scripts/run_mileage_batch.py badges --dry-run
    python scripts/run_mileage_batch.py badges --student-id <id> --dry-run

--dry-run은 DB에 쓰지 않고 결과만 출력한다.
"""
import argparse
import sys
import io
import os
import json
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.mileage import PointEvent
from app.services.mileage_rules import POINT_RULES


def _print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_confirm(args):
    if args.dry_run:
        now = datetime.utcnow()
        pending = PointEvent.query.filter_by(entry_type='award', status='pending').all()
        would_confirm = []
        for p in pending:
            rule = POINT_RULES.get(p.activity_code)
            if not rule:
                continue
            due = p.occurred_at + timedelta(hours=rule['confirm_delay_hours'])
            if now >= due:
                would_confirm.append(p)
        print(f"(dry-run) 확정 대상 {len(would_confirm)}건 / 전체 대기 {len(pending)}건")
        for p in would_confirm[:30]:
            print(f"  - {p.student_id} {p.activity_code} {p.source_id} (occurred_at={p.occurred_at})")
    else:
        from app.services.mileage_service import confirm_pending_points
        count = confirm_pending_points()
        db.session.commit()
        print(f"{count}건 확정 완료")


def cmd_weekly(args):
    from app.services.mileage_batch_service import run_weekly_attendance_batch, parse_iso_week
    monday = parse_iso_week(args.week) if args.week else None
    results = run_weekly_attendance_batch(monday=monday, dry_run=args.dry_run)
    _print_json(results)
    print(f"\n총 {len(results)}명 검토")
    if args.dry_run:
        db.session.rollback()
        print("(dry-run) DB에 반영하지 않음")
    else:
        db.session.commit()
        print("DB에 반영 완료")


def cmd_quarterly(args):
    from app.services.mileage_batch_service import run_quarterly_completion_batch
    year = period_number = None
    if args.quarter:
        year_str, q_str = args.quarter.split('Q')
        year, period_number = int(year_str), int(q_str)
    results = run_quarterly_completion_batch(year=year, period_number=period_number, dry_run=args.dry_run)
    _print_json(results)
    print(f"\n총 {len(results)}명 검토")
    if args.dry_run:
        db.session.rollback()
        print("(dry-run) DB에 반영하지 않음")
    else:
        db.session.commit()
        print("DB에 반영 완료")


def cmd_ranking(args):
    from app.services.ranking_service import build_ranking
    if args.dry_run:
        results = build_ranking(args.season, finalize=False)
        _print_json(results)
        print(f"\n(dry-run) {len(results)}명 - DB에 반영하지 않음")
        return

    is_final = args.finalize
    results = build_ranking(args.season, finalize=True, is_final=is_final)
    db.session.commit()
    _print_json(results)
    print(f"\n{len(results)}명 저장 완료 (is_final={is_final})")


def cmd_badges(args):
    if args.student_id:
        from app.services.badge_service import evaluate_badges
        granted = evaluate_badges(args.student_id, dry_run=args.dry_run)
        _print_json(granted)
        if args.dry_run:
            db.session.rollback()
            print("(dry-run) DB에 반영하지 않음")
        else:
            db.session.commit()
            print("DB에 반영 완료")
    else:
        from app.services.badge_service import run_badge_sweep
        results = run_badge_sweep(dry_run=args.dry_run)
        _print_json(results)
        print(f"\n총 {len(results)}명에게 부여 대상 발생")
        if args.dry_run:
            db.session.rollback()
            print("(dry-run) DB에 반영하지 않음")
        else:
            db.session.commit()
            print("DB에 반영 완료")


def main():
    parser = argparse.ArgumentParser(description='마일리지 배치 수동 실행')
    sub = parser.add_subparsers(dest='batch', required=True)

    p = sub.add_parser('confirm', help='대기 포인트 확정')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_confirm)

    p = sub.add_parser('weekly', help='AT01 주간 출석 집계')
    p.add_argument('--week', help='ISO 주차, 예: 2026-W36 (생략 시 직전 주)')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_weekly)

    p = sub.add_parser('quarterly', help='AT02 분기 완주 판정')
    p.add_argument('--quarter', help='예: 2026Q1 (생략 시 직전 분기)')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_quarterly)

    p = sub.add_parser('ranking', help='월간 랭킹 집계')
    p.add_argument('--season', required=True, help='예: 2026-08')
    p.add_argument('--finalize', action='store_true', help='is_final=True로 확정 저장')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_ranking)

    p = sub.add_parser('badges', help='뱃지 판정')
    p.add_argument('--student-id', help='특정 학생만 (생략 시 전체 스윕)')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_badges)

    args = parser.parse_args()

    app = create_app('development')
    with app.app_context():
        args.func(args)


if __name__ == '__main__':
    main()
