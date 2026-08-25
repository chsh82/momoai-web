# -*- coding: utf-8 -*-
"""
1회성 수정 스크립트: import_curriculum이 grade_tags에 학년 코드('중1' 등)를 그대로
넣던 버그로 오염된 books.grade_tags를 LV 코드로 정정.

- 학년 코드 패턴(초1~6/중1~3/고1~3)의 태그는 제거
- 해당 도서를 참조하는 curriculum_weeks의 grade를 모아 LV 코드로 변환해 채워 넣음
  (curriculum_weeks가 없는 책은 정리만 하고 새로 채우지 않음)
- 원래 있던 정상 LV 태그는 그대로 보존

사용법: python fix_curriculum_grade_tags.py [--dry-run]
"""
import re
import json
import argparse
import warnings

warnings.filterwarnings('ignore')

from app import create_app
from app.models import db
from app.models.book import Book
from app.models.curriculum import CurriculumWeek
from app.utils.grades import GRADE_TO_LV

_BAD_TAG_RE = re.compile(r'^(초[1-6]|중[1-3]|고[1-3])$')


def main(dry_run: bool):
    weeks = CurriculumWeek.query.filter(CurriculumWeek.book_id.isnot(None)).all()
    grades_by_book: dict[str, set] = {}
    for w in weeks:
        grades_by_book.setdefault(w.book_id, set()).add(w.grade)

    books = Book.query.filter(Book.grade_tags.isnot(None)).all()
    fixed = 0
    for book in books:
        try:
            tags = json.loads(book.grade_tags)
        except (TypeError, ValueError):
            continue
        if not any(_BAD_TAG_RE.match(t) for t in tags):
            continue

        clean_tags = [t for t in tags if not _BAD_TAG_RE.match(t)]
        for grade_code in grades_by_book.get(book.book_id, ()):
            lv = GRADE_TO_LV.get(grade_code)
            if lv and lv not in clean_tags:
                clean_tags.append(lv)

        print(f'{book.book_id} {book.title!r}: {tags} -> {clean_tags}')
        book.grade_tags = json.dumps(clean_tags, ensure_ascii=False) if clean_tags else None
        fixed += 1

    print(f'\n총 {fixed}건 수정')
    if dry_run:
        db.session.rollback()
        print('--dry-run 모드: 실제로 저장하지 않았습니다.')
    else:
        db.session.commit()
        print('저장 완료.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        main(args.dry_run)
