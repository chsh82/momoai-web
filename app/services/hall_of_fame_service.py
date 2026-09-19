# -*- coding: utf-8 -*-
"""명예의 전당 관련 부가 서비스 - 월요일 축하 팝업."""
from datetime import datetime, timedelta

from app.models import db
from app.models.library import HallOfFame


def get_monday_congrats_posts(student):
    """오늘이 월요일이고, 이 학생의 글이 지난주(오늘 기준 최근 7일)에 명예의 전당에
    새로 올라갔으며, 이번 주에 아직 축하 팝업을 보여주지 않았다면 그 게시글 목록을
    반환한다. 조건에 안 맞으면 None(팝업 표시 안 함).

    호출 시 조건을 만족하면 student.hof_congrats_shown_at을 갱신하고 커밋한다
    (같은 주에 페이지를 여러 번 열어도 팝업이 한 번만 뜨게 하기 위함).
    """
    if not student:
        return None

    now = datetime.now()
    if now.weekday() != 0:  # 0 = 월요일
        return None

    today_midnight = datetime(now.year, now.month, now.day)
    week_start = today_midnight - timedelta(days=7)  # 지난주 월요일 00:00
    week_end = today_midnight  # 오늘(이번 주 월요일) 00:00 - 지난 일요일 24:00과 동일

    # 이번 주(오늘)에 이미 팝업을 보여줬으면 다시 안 보여준다.
    if student.hof_congrats_shown_at and student.hof_congrats_shown_at >= today_midnight:
        return None

    posts = (HallOfFame.query
             .filter(HallOfFame.student_id == student.student_id)
             .filter(HallOfFame.is_published == True)  # noqa: E712
             .filter(HallOfFame.created_at >= week_start)
             .filter(HallOfFame.created_at < week_end)
             .order_by(HallOfFame.created_at.asc())
             .all())

    if not posts:
        return None

    student.hof_congrats_shown_at = now
    db.session.commit()
    return posts
