#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ISBN 기능 디버깅"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("ISBN 기능 디버깅")
print("=" * 60)

# 1. Flask 앱 생성 및 테스트 클라이언트
print("\n[1] Flask 앱 및 테스트 클라이언트 생성")
print("-" * 60)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User

app = create_app('development')

with app.app_context():
    # 2. 테스트 사용자 확인
    print("\n[2] 테스트 사용자 확인")
    print("-" * 60)

    test_user = User.query.filter_by(role='admin').first()
    if test_user:
        print(f"[OK] 관리자 계정 존재: {test_user.email}")
    else:
        print("[WARNING] 관리자 계정을 찾을 수 없습니다.")

    # 3. 엔드포인트 직접 호출 테스트
    print("\n[3] API 엔드포인트 직접 테스트")
    print("-" * 60)

    with app.test_client() as client:
        # 로그인
        if test_user:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(test_user.user_id)

        # ISBN 조회 API 호출
        test_isbn = "9788968483417"
        print(f"테스트 ISBN: {test_isbn}")

        response = client.post(
            '/books/api/isbn-lookup',
            json={'isbn': test_isbn},
            content_type='application/json'
        )

        print(f"응답 상태 코드: {response.status_code}")
        print(f"응답 데이터: {response.get_json()}")

        if response.status_code == 200:
            data = response.get_json()
            if data.get('success'):
                book = data.get('book')
                print("\n[OK] ISBN 조회 성공!")
                print(f"  제목: {book.get('title')}")
                print(f"  저자: {book.get('author')}")
                print(f"  출판사: {book.get('publisher')}")
                print(f"  출판년도: {book.get('publication_year')}")
            else:
                print(f"[ERROR] 조회 실패: {data.get('message')}")
        else:
            print(f"[ERROR] API 호출 실패")
            print(f"응답 본문: {response.data.decode('utf-8')}")

# 4. ISBNService 직접 테스트
print("\n[4] ISBNService 직접 테스트")
print("-" * 60)

from app.books.isbn_service import ISBNService

test_isbn = "9788968483417"
print(f"테스트 ISBN: {test_isbn}")

try:
    book_info = ISBNService.lookup_isbn(test_isbn)
    if book_info:
        print("[OK] ISBNService 조회 성공!")
        print(f"  제목: {book_info.get('title')}")
        print(f"  저자: {book_info.get('author')}")
        print(f"  출판사: {book_info.get('publisher')}")
        print(f"  출판년도: {book_info.get('publication_year')}")
        print(f"  표지 이미지: {book_info.get('cover_image_url')}")
    else:
        print("[ERROR] ISBNService가 None을 반환했습니다.")
except Exception as e:
    print(f"[ERROR] ISBNService 호출 중 오류: {e}")
    import traceback
    traceback.print_exc()

# 5. 브라우저 콘솔 확인 가이드
print("\n" + "=" * 60)
print("브라우저에서 확인할 사항")
print("=" * 60)
print("""
1. 브라우저 개발자 도구 열기 (F12)
2. Console 탭 확인
3. ISBN 조회 버튼 클릭
4. 다음 오류 메시지 확인:
   - CORS 오류
   - 401 Unauthorized (로그인 필요)
   - 404 Not Found (엔드포인트 없음)
   - Network Error (서버 미실행)
   - JavaScript 오류

Network 탭에서 확인:
- /books/api/isbn-lookup 요청이 전송되는지
- 응답 상태 코드 (200, 400, 404, 500 등)
- 응답 본문 내용
""")

print("\n" + "=" * 60)
print("문제 해결 체크리스트")
print("=" * 60)
print("""
✓ 서버가 실행 중인지 확인: python run.py
✓ 로그인이 되어 있는지 확인
✓ ISBN 입력 필드에 값이 제대로 입력되었는지 확인
✓ 조회 버튼을 클릭했는지 확인
✓ 브라우저 콘솔에 오류가 있는지 확인
✓ 인터넷 연결 확인 (Google Books API 접근 필요)
""")
print("=" * 60)
