# -*- coding: utf-8 -*-
"""
표지 이미지가 비어있는 Book 레코드를 ISBN 재조회로 복구.
- Book.cover_image_url이 NULL/빈 문자열이고 isbn이 있는 레코드 대상
- ISBNService.lookup_isbn()으로 알라딘→Google Books→네이버 순 재조회
- 조회된 cover_image_url만 채움(title/author 등 기존 값은 건드리지 않음)
- ISBN이 없는 레코드는 자동 복구 대상이 아니므로 건드리지 않고 목록만 출력
"""
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

from app import create_app
from app.models import db
from app.models.book import Book
from app.books.isbn_service import ISBNService

app = create_app()
with app.app_context():
    targets = Book.query.filter(
        db.or_(Book.cover_image_url.is_(None), Book.cover_image_url == ''),
        Book.isbn.isnot(None), Book.isbn != '',
    ).all()
    no_isbn = Book.query.filter(
        db.or_(Book.cover_image_url.is_(None), Book.cover_image_url == ''),
        db.or_(Book.isbn.is_(None), Book.isbn == ''),
    ).all()

    print(f"대상(ISBN 보유, 표지 없음): {len(targets)}건")
    print(f"ISBN 미보유(수동 처리 필요): {len(no_isbn)}건\n")

    fixed = failed = 0
    for book in targets:
        info = ISBNService.lookup_isbn(book.isbn)
        cover = info.get('cover_image_url') if info else None
        if cover:
            book.cover_image_url = cover
            fixed += 1
            print(f"  OK  {book.title} ({book.isbn})")
        else:
            failed += 1
            print(f"  FAIL {book.title} ({book.isbn}) - API에서도 표지 못 찾음")

    db.session.commit()

    print(f"\n복구됨: {fixed}건 / 실패(여전히 표지 없음): {failed}건")
    if no_isbn:
        print("\nISBN 미보유(제목으로 직접 확인 후 수동 등록 필요):")
        for b in no_isbn:
            print(f"  - {b.title} (book_id={b.book_id})")
