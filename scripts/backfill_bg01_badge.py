#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BG01(과제 제출) 소급 부여 - 알림 없이 조용히 채운다

essay_type 기능 도입으로 BG01 판정 기준이 "게시글 작성"에서 "essays 테이블에
1건 이상 존재"로 바뀌었다(app/services/badge_service.py의 _first_event_count).
그 결과 운영 DB에 이미 쌓여 있던 과제(2026-08-29 기준 2,579건 이상)를 가진
재원생 대부분이 이 스크립트/야간 배치(run_badge_sweep)가 처음 도는 순간
동시에 BG01을 받게 된다.

evaluate_badges()가 기본적으로 뱃지 획득 시 학생·학부모에게 알림을 보내므로,
아무 조치 없이 두면 재원생 다수에게 "뱃지 획득: 첫 문장" 알림이 한꺼번에
발송된다 - 이건 실제 신규 성취가 아니라 판정 기준 변경의 부작용이므로
알림을 보내면 안 된다(2026-08-29 결정사항).

이 스크립트는 evaluate_badges(..., notify=False)로 그 소급분만 조용히
채운다. trigger_codes=['essay']로 범위를 BG01/BG03(essay 기반 뱃지)만으로
좁힌다 - 다른 뱃지가 이 스크립트 실행 시점에 우연히 조건을 满족해도
함께 침묵되지 않게 하기 위함이다. (BG03은 이번 마이그레이션이 기존 essay를
전부 essay_type='basic'으로 백필하기 때문에 실제로는 소급 대상이 아니다 -
그래도 같은 first_event 판정 경로를 타므로 trigger_codes에 포함해 둔다.)

실행 시점이 중요하다: 배포 직후, 다음 야간 run_badge_sweep() 배치가 돌기
전에 반드시 먼저 실행해야 한다. 그렇지 않으면 야간 배치가 notify=True로
먼저 돌면서 이 스크립트가 막으려는 알림이 그대로 나가버린다.
(docs/mileage/10_배포절차서.md 배포 순서: 마이그레이션 -> seed_badges.py
-> update_badges_essay_type.py -> 이 스크립트 -> 서비스 재시작)

몇 번을 실행해도 안전하다 - 이미 획득한 학생은 evaluate_badges()가
건너뛴다(반복 불가 뱃지).
"""
import sys
import io
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.essay import Essay
from app.services import badge_service


def main():
    app = create_app('production' if '--production' in sys.argv else 'development')
    with app.app_context():
        student_ids = [row[0] for row in
                      db.session.query(Essay.student_id).distinct().all()]
        print(f"과제를 1건 이상 제출한 학생 {len(student_ids)}명 대상으로 판정합니다 (알림 없음).")

        granted_count, error_count = 0, 0
        for student_id in student_ids:
            try:
                granted = badge_service.evaluate_badges(
                    student_id, trigger_codes=['essay'], notify=False,
                )
                if granted:
                    codes = [g.badge_code for g in granted]
                    print(f"  {student_id}: {codes} 부여(알림 없음)")
                    granted_count += 1
            except Exception as e:
                error_count += 1
                print(f"  경고: {student_id} 처리 중 오류 - {e}")

        db.session.commit()
        print(f"\n완료: {granted_count}명 신규 부여(알림 없음), 오류 {error_count}건, "
              f"대상 외 {len(student_ids) - granted_count - error_count}명(이미 보유 또는 미충족)")


if __name__ == '__main__':
    main()
