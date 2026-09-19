# -*- coding: utf-8 -*-
"""명예의 전당 - 주간/월간 성적 랭킹.

첨삭 완료(is_finalized)된 글의 EssayResult.total_score를 기준으로, 학생별 그 기간
최고 점수 글 1건만 반영해(같은 학생이 여러 번 나오지 않게) 학년별 상위 5명을 뽑고,
초등부(초1~6)/중등부(중1~3) 두 섹션으로 묶어서 반환한다. 글 내용은 절대 노출하지
않고 점수·이름(마스킹)·지도교사·글 제목만 다룬다.
"""
from datetime import datetime, timedelta

from app.models import db
from app.models.essay import Essay
from app.models.essay import EssayResult
from app.models.student import Student

GRADE_BANDS = [
    ('초등부', ['초1', '초2', '초3', '초4', '초5', '초6']),
    ('중등부', ['중1', '중2', '중3']),
]
TOP_N = 5


def mask_name(name):
    """이름 가운데를 *로 가린다. 2글자면 그대로, 3글자 이상이면 가운데를 전부 마스킹."""
    if not name:
        return name
    if len(name) <= 2:
        return name
    return name[0] + ('*' * (len(name) - 2)) + name[-1]


def week_range(now=None):
    """'지난 주'(지난 월요일 00:00 ~ 이번 주 월요일 00:00) - 이번 주 안에는 요일과
    무관하게 항상 같은 범위를 가리킨다(다음 월요일이 되면 자동으로 한 주 밀림)."""
    now = now or datetime.now()
    today_midnight = datetime(now.year, now.month, now.day)
    this_monday = today_midnight - timedelta(days=now.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, this_monday


def month_range(now=None):
    """'지난 달'(지난달 1일 00:00 ~ 이번 달 1일 00:00)."""
    now = now or datetime.now()
    first_of_this_month = datetime(now.year, now.month, 1)
    if now.month == 1:
        first_of_last_month = datetime(now.year - 1, 12, 1)
    else:
        first_of_last_month = datetime(now.year, now.month - 1, 1)
    return first_of_last_month, first_of_this_month


def _period_range(period, now=None):
    if period == 'month':
        return month_range(now)
    return week_range(now)


def build_ranking(period='week', now=None):
    """반환: (bands, start, end)
    bands = [(band_label, [(grade, [entry, ...]), ...]), ...]
    entry = {'masked_name': str, 'score': float, 'teacher_name': str|None,
             'title': str, 'grade': str}
    """
    start, end = _period_range(period, now)

    rows = (db.session.query(Essay, EssayResult)
            .join(EssayResult, EssayResult.essay_id == Essay.essay_id)
            .filter(Essay.is_finalized == True)  # noqa: E712
            .filter(Essay.finalized_at >= start)
            .filter(Essay.finalized_at < end)
            .filter(EssayResult.total_score.isnot(None))
            .all())

    # 학생별 이 기간 최고 점수 글 1건만 남긴다(동점이면 먼저 확정된 글).
    best_by_student = {}
    for essay, result in rows:
        sid = essay.student_id
        score = float(result.total_score)
        cur = best_by_student.get(sid)
        if cur is None:
            best_by_student[sid] = (essay, score)
            continue
        cur_essay, cur_score = cur
        if score > cur_score or (score == cur_score and essay.finalized_at < cur_essay.finalized_at):
            best_by_student[sid] = (essay, score)

    grade_allowed = {g for _, grades in GRADE_BANDS for g in grades}
    by_grade = {}
    for sid, (essay, score) in best_by_student.items():
        student = essay.student
        if not student or student.grade not in grade_allowed:
            continue
        entry = {
            'masked_name': mask_name(student.name),
            'score': score,
            'teacher_name': student.main_teacher.name if student.main_teacher else None,
            'title': essay.title or '(제목 없음)',
            'grade': student.grade,
        }
        by_grade.setdefault(student.grade, []).append(entry)

    for grade in by_grade:
        by_grade[grade].sort(key=lambda e: e['score'], reverse=True)
        by_grade[grade] = by_grade[grade][:TOP_N]

    bands = []
    for band_label, grades in GRADE_BANDS:
        grade_lists = [(g, by_grade[g]) for g in grades if by_grade.get(g)]
        bands.append((band_label, grade_lists))

    return bands, start, end
