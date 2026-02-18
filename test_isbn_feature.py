#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ISBN 자동 채우기 기능 테스트"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("ISBN 자동 채우기 기능 테스트")
print("=" * 60)

# 1. 라이브러리 확인
print("\n[1단계] requests 라이브러리 확인")
print("-" * 60)

try:
    import requests
    print(f"[OK] requests 설치됨 (버전: {requests.__version__})")
except ImportError:
    print("[ERROR] requests가 설치되어 있지 않습니다.")
    print("        해결: pip install requests")
    sys.exit(1)

# 2. ISBNService import 테스트
print("\n[2단계] ISBNService 모듈 확인")
print("-" * 60)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.books.isbn_service import ISBNService
    print("[OK] ISBNService 모듈 import 성공")
except Exception as e:
    print(f"[ERROR] ISBNService import 실패: {e}")
    sys.exit(1)

# 3. ISBN 조회 테스트 (여러 예시)
print("\n[3단계] ISBN 조회 기능 테스트")
print("-" * 60)

test_isbns = [
    ("9788968483417", "한국 도서 예시 1"),
    ("9788932917245", "한국 도서 예시 2"),
    ("9780134685991", "영문 도서 예시"),
]

for isbn, description in test_isbns:
    print(f"\n📖 테스트: {description}")
    print(f"   ISBN: {isbn}")

    try:
        book_info = ISBNService.lookup_isbn(isbn)

        if book_info:
            print(f"   [OK] 도서 정보 조회 성공!")
            print(f"   제목: {book_info.get('title', 'N/A')}")
            print(f"   저자: {book_info.get('author', 'N/A')}")
            print(f"   출판사: {book_info.get('publisher', 'N/A')}")
            print(f"   출판년도: {book_info.get('publication_year', 'N/A')}")
            print(f"   설명: {book_info.get('description', 'N/A')[:100]}..." if book_info.get('description') else "   설명: N/A")
            print(f"   표지 이미지: {book_info.get('cover_image_url', 'N/A')}")
        else:
            print(f"   [WARNING] ISBN {isbn}로 도서를 찾을 수 없습니다.")

    except Exception as e:
        print(f"   [ERROR] 조회 중 오류 발생: {e}")

# 4. API 엔드포인트 확인
print("\n[4단계] API 엔드포인트 확인")
print("-" * 60)

try:
    from app import create_app
    app = create_app('development')

    # URL 규칙 확인
    with app.app_context():
        rules = [rule for rule in app.url_map.iter_rules() if 'isbn' in rule.rule.lower()]

        if rules:
            print("[OK] ISBN 관련 엔드포인트 발견:")
            for rule in rules:
                print(f"     {rule.methods} {rule.rule}")
        else:
            print("[WARNING] ISBN 관련 엔드포인트를 찾을 수 없습니다.")

except Exception as e:
    print(f"[ERROR] 엔드포인트 확인 실패: {e}")

# 5. 템플릿 파일 확인
print("\n[5단계] 템플릿 파일 확인")
print("-" * 60)

template_path = os.path.join(os.path.dirname(__file__), 'templates', 'books', 'form.html')
if os.path.exists(template_path):
    print(f"[OK] form.html 존재")

    # lookupISBN 함수 확인
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'lookupISBN' in content:
            print("[OK] lookupISBN() JavaScript 함수 발견")
        if 'isbn-lookup' in content:
            print("[OK] API 호출 코드 발견")
        if 'isbnLookupBtn' in content:
            print("[OK] 조회 버튼 발견")
else:
    print(f"[ERROR] form.html을 찾을 수 없습니다.")

# 최종 결과
print("\n" + "=" * 60)
print("✅ 테스트 완료!")
print("=" * 60)
print("\n📝 사용 방법:")
print("1. 서버 실행: python run.py")
print("2. 추천도서 등록 페이지 접속:")
print("   http://localhost:5000/books/new")
print("3. ISBN 입력 (예: 9788968483417)")
print("4. '조회' 버튼 클릭")
print("5. 자동으로 제목, 저자, 출판사 등이 입력됨!")
print("\n💡 자동 입력되는 정보:")
print("   - 제목 (title)")
print("   - 저자 (author)")
print("   - 출판사 (publisher)")
print("   - 출판년도 (publication_year)")
print("   - 표지 이미지 URL (cover_image_url)")
print("   - 설명 (description)")
print("\n" + "=" * 60)
