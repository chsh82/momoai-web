# -*- coding: utf-8 -*-
"""
모모의 책장 연간 커리큘럼 엑셀을 curriculum_weeks + books 테이블로 임포트하는 CLI 도구.
평상시에는 웹 화면(/curriculum/upload)을 쓰고, 이 스크립트는 서버 접속 상태에서
직접 파일을 다룰 때 쓰는 백업 경로.

사용법:
    python import_curriculum.py "경로/모모의책장_커리큘럼.xlsx" [--dry-run]

파싱/반영 로직은 app/curriculum/importer.py 를 공유함(웹 업로드와 동일 동작).
"""
import argparse
import warnings

warnings.filterwarnings('ignore')

from app import create_app
from app.models import db
from app.curriculum.importer import parse_workbook, apply_import

ADMIN_USER_ID = '6e1291bc-ef79-475f-ae52-10dcec9cc045'  # Master Admin (admin@momoai.com)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('excel_path')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = parse_workbook(args.excel_path)
        if not rows:
            print('파싱된 데이터가 없습니다.')
            return

        stats = apply_import(rows, ADMIN_USER_ID)
        print(f'파싱된 행: {stats["rows_parsed"]}건')
        print(f'주차 추가: {stats["weeks_added"]}건 / 갱신: {stats["weeks_updated"]}건 (휴강 {stats["holiday_weeks"]}건 포함)')
        print(f'도서 신규 생성: {stats["books_created"]}건 / 기존 도서 갱신: {stats["books_updated"]}건')

        if args.dry_run:
            db.session.rollback()
            print('--dry-run 모드: 실제로 저장하지 않았습니다.')
        else:
            db.session.commit()
            print('저장 완료.')


if __name__ == '__main__':
    main()
