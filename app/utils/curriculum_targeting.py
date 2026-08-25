# -*- coding: utf-8 -*-
"""
학습 교재를 커리큘럼(도서 + 차시)에 연동해서 대상 학년을 자동 계산하는 유틸리티.

한 도서가 여러 주차에 걸쳐 배정될 수 있어서(예: "동물농장" 1주차 + "(연장)" 1주차),
자료를 "도서 + 몇 번째 주차(차시)"로 등록해두면 매년 커리큘럼만 새로 임포트해도
자동으로 그 해 학년/주차에 맞는 대상이 계산됨(자료 재등록/대상 재설정 불필요).

차시는 같은 (연도, 분기, 학년) 안에서 week_number가 연속인 구간 단위로 계산함
(분기를 건너뛴 재등장은 지원하지 않음 - 실제 운영상 발생하지 않는다고 확인됨).
"""
from datetime import date
from itertools import groupby

from app.models.curriculum import CurriculumWeek


def _sequence_runs_by_grade(book_id: str, year: int) -> dict:
    """book_id가 해당 연도에 배정된 학년별 연속 주차 구간들을 {grade: [[week,...], ...]} 형태로 반환.
    (같은 학년이라도 분기가 다르면 별도 구간으로 취급)"""
    weeks = CurriculumWeek.query.filter_by(year=year, book_id=book_id).order_by(
        CurriculumWeek.grade, CurriculumWeek.quarter, CurriculumWeek.week_number
    ).all()

    runs_by_grade: dict = {}
    for (grade, quarter), group in groupby(weeks, key=lambda w: (w.grade, w.quarter)):
        group = list(group)
        run_start = 0
        for i in range(1, len(group) + 1):
            if i == len(group) or group[i].week_number != group[i - 1].week_number + 1:
                runs_by_grade.setdefault(grade, []).append(group[run_start:i])
                run_start = i
    return runs_by_grade


def compute_curriculum_grades(book_id: str, sequence: int | None, year: int | None = None) -> list:
    """book_id(+sequence 차시)가 해당 연도 커리큘럼에서 배정된 학년 목록.
    sequence가 None이면 차시 구분 없이 그 도서가 배정된 모든 학년을 반환."""
    if not book_id:
        return []
    year = year or date.today().year
    runs_by_grade = _sequence_runs_by_grade(book_id, year)

    if sequence is None:
        return sorted(runs_by_grade.keys())

    matched = set()
    for grade, runs in runs_by_grade.items():
        for run in runs:
            if 1 <= sequence <= len(run):
                matched.add(grade)
                break
    return sorted(matched)


def compute_curriculum_sequences(book_id: str, year: int | None = None) -> list:
    """관리자 화면에서 "N주차 - 배정 학년" 미리보기용. [{"sequence": 1, "grades": [...]}, ...] 반환."""
    if not book_id:
        return []
    year = year or date.today().year
    runs_by_grade = _sequence_runs_by_grade(book_id, year)

    seq_grades: dict = {}
    for grade, runs in runs_by_grade.items():
        for run in runs:
            for pos in range(1, len(run) + 1):
                seq_grades.setdefault(pos, set()).add(grade)

    return [{'sequence': seq, 'grades': sorted(grades)} for seq, grades in sorted(seq_grades.items())]
