#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""강화된 ISBN 서비스 테스트"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.books.isbn_service import ISBNService

print("=" * 70)
print("📚 강화된 ISBN 서비스 테스트 (2단계 검색 전략)")
print("=" * 70)

# 테스트할 ISBN 목록
test_cases = [
    ("9788968483417", "마이크로서비스 아키텍처 구축 (정보 부족한 경우)"),
    ("9788932917245", "어린 왕자 (한국 도서)"),
    ("9780134685991", "Effective Java (영문 도서)"),
    ("9788937460449", "1984 (조지 오웰)"),
]

for isbn, description in test_cases:
    print("\n" + "=" * 70)
    print(f"📖 테스트: {description}")
    print(f"🔍 ISBN: {isbn}")
    print("-" * 70)

    book_info = ISBNService.lookup_isbn(isbn)

    print("\n" + "=" * 70)
    if book_info:
        print("✅ 조회 성공!")
        print("-" * 70)
        print(f"📚 제목: {book_info.get('title', 'N/A')}")
        print(f"✍️  저자: {book_info.get('author', 'N/A')}")
        print(f"🏢 출판사: {book_info.get('publisher', 'N/A')}")
        print(f"📅 출판년도: {book_info.get('publication_year', 'N/A')}")
        print(f"🖼️  표지: {book_info.get('cover_image_url', 'N/A')}")

        description = book_info.get('description', '')
        if description:
            print(f"📝 설명: {description[:100]}...")
        else:
            print(f"📝 설명: N/A")

        # 정보 완성도 체크
        missing = []
        if not book_info.get('title'):
            missing.append('제목')
        if not book_info.get('author'):
            missing.append('저자')
        if not book_info.get('publisher'):
            missing.append('출판사')
        if not book_info.get('cover_image_url'):
            missing.append('표지')

        if missing:
            print(f"\n⚠️  부족한 정보: {', '.join(missing)}")
        else:
            print(f"\n🎉 모든 정보 완벽!")

    else:
        print("❌ ISBN으로 도서 정보를 찾을 수 없습니다.")

    print("=" * 70)
    input("\n다음 테스트로 넘어가려면 Enter를 누르세요...")

print("\n" + "=" * 70)
print("✅ 모든 테스트 완료!")
print("=" * 70)
print("\n💡 이제 웹 페이지에서 테스트해보세요:")
print("   1. python run.py 로 서버 실행")
print("   2. http://localhost:5000/books/new 접속")
print("   3. ISBN 입력 후 '조회' 버튼 클릭")
print("   4. 저자, 출판사, 표지 이미지까지 자동으로 채워지는지 확인!")
print("=" * 70)
