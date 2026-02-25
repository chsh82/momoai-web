# -*- coding: utf-8 -*-
"""ISBN 조회 서비스 - Google Books + Open Library 순차 조회"""
import requests


class ISBNService:
    """Google Books + Open Library API를 사용한 ISBN 조회 서비스"""

    GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
    OPEN_LIBRARY_API = "https://openlibrary.org/api/books"

    @staticmethod
    def _extract_book_info(book_data):
        """
        Google Books API 응답에서 도서 정보 추출

        Args:
            book_data (dict): Google Books volumeInfo

        Returns:
            dict: 도서 정보
        """
        book_info = {
            'title': book_data.get('title', ''),
            'author': ', '.join(book_data.get('authors', [])),
            'publisher': book_data.get('publisher', ''),
            'publication_year': None,
            'description': book_data.get('description', ''),
            'cover_image_url': None,
            'isbn': None
        }

        # 출판년도 추출
        published_date = book_data.get('publishedDate', '')
        if published_date:
            try:
                book_info['publication_year'] = int(published_date[:4])
            except (ValueError, IndexError):
                pass

        # 표지 이미지 URL 추출 (큰 것부터 우선)
        if 'imageLinks' in book_data:
            image_links = book_data['imageLinks']
            # 우선순위: extraLarge > large > medium > small > thumbnail > smallThumbnail
            book_info['cover_image_url'] = (
                image_links.get('extraLarge') or
                image_links.get('large') or
                image_links.get('medium') or
                image_links.get('small') or
                image_links.get('thumbnail') or
                image_links.get('smallThumbnail')
            )

            # HTTP를 HTTPS로 변경 (보안)
            if book_info['cover_image_url'] and book_info['cover_image_url'].startswith('http://'):
                book_info['cover_image_url'] = book_info['cover_image_url'].replace('http://', 'https://')

        return book_info

    @staticmethod
    def _search_by_query(query, max_results=5):
        """
        검색어로 도서 정보 조회

        Args:
            query (str): 검색어
            max_results (int): 최대 결과 수

        Returns:
            list: 도서 정보 리스트
        """
        try:
            params = {
                'q': query,
                'maxResults': max_results
            }

            response = requests.get(ISBNService.GOOGLE_BOOKS_API, params=params, timeout=10)

            if response.status_code != 200:
                return []

            data = response.json()

            if 'items' not in data:
                return []

            results = []
            for item in data['items']:
                book_data = item.get('volumeInfo', {})
                book_info = ISBNService._extract_book_info(book_data)
                results.append(book_info)

            return results

        except Exception as e:
            print(f"Search by query error: {e}")
            return []

    @staticmethod
    def _merge_book_info(primary, secondary):
        """
        두 도서 정보를 병합 (primary가 우선, 비어있으면 secondary 사용)

        Args:
            primary (dict): 1차 정보
            secondary (dict): 2차 정보

        Returns:
            dict: 병합된 정보
        """
        merged = primary.copy()

        for key in ['author', 'publisher', 'description', 'cover_image_url']:
            if not merged.get(key) and secondary.get(key):
                merged[key] = secondary[key]
                print(f"[ISBN Service] {key} 보완: {secondary[key][:50]}...")

        return merged

    @staticmethod
    def lookup_isbn(isbn):
        """
        ISBN으로 도서 정보 조회 (2단계 검색 전략)

        1단계: ISBN으로 직접 검색
        2단계: 정보가 부족하면 제목으로 추가 검색하여 보완

        Args:
            isbn (str): ISBN 번호

        Returns:
            dict: 도서 정보 또는 None
        """
        try:
            # ISBN에서 하이픈 제거
            isbn_clean = isbn.replace('-', '').replace(' ', '')
            print(f"[ISBN Service] 1단계: ISBN {isbn_clean} 검색")

            # 1단계: ISBN으로 검색
            params = {
                'q': f'isbn:{isbn_clean}',
                'maxResults': 1
            }

            response = requests.get(ISBNService.GOOGLE_BOOKS_API, params=params, timeout=10)

            if response.status_code != 200:
                print(f"[ISBN Service] API 응답 오류: {response.status_code}")
                return None

            data = response.json()

            if 'items' not in data or len(data['items']) == 0:
                print(f"[ISBN Service] ISBN {isbn_clean}로 검색 결과 없음")
                return None

            # 첫 번째 결과 파싱
            book_data = data['items'][0]['volumeInfo']
            book_info = ISBNService._extract_book_info(book_data)
            book_info['isbn'] = isbn_clean

            print(f"[ISBN Service] 1단계 결과:")
            print(f"  - 제목: {book_info.get('title', 'N/A')}")
            print(f"  - 저자: {book_info.get('author', 'N/A')}")
            print(f"  - 출판사: {book_info.get('publisher', 'N/A')}")
            print(f"  - 표지: {book_info.get('cover_image_url', 'N/A')}")

            # 2단계: 부족한 정보가 있으면 제목으로 추가 검색
            missing_fields = []
            if not book_info.get('author'):
                missing_fields.append('저자')
            if not book_info.get('publisher'):
                missing_fields.append('출판사')
            if not book_info.get('cover_image_url'):
                missing_fields.append('표지')

            if missing_fields and book_info.get('title'):
                print(f"[ISBN Service] 2단계: 부족한 정보 보완 시도 ({', '.join(missing_fields)})")

                # 제목으로 추가 검색
                search_results = ISBNService._search_by_query(book_info['title'], max_results=5)

                if search_results:
                    print(f"[ISBN Service] 제목 검색 결과: {len(search_results)}건")

                    # 가장 유사한 결과 찾기
                    best_match = None
                    for result in search_results:
                        # 제목이 유사하고, 부족한 정보를 가지고 있는 결과 선택
                        if result.get('title') and book_info['title'].lower() in result['title'].lower():
                            # 점수 계산 (부족한 정보를 많이 가지고 있을수록 높음)
                            score = 0
                            if not book_info.get('author') and result.get('author'):
                                score += 3
                            if not book_info.get('publisher') and result.get('publisher'):
                                score += 2
                            if not book_info.get('cover_image_url') and result.get('cover_image_url'):
                                score += 1

                            if score > 0:
                                if not best_match or score > best_match[1]:
                                    best_match = (result, score)

                    # 최적의 결과로 정보 보완
                    if best_match:
                        print(f"[ISBN Service] 최적 매칭 결과로 정보 보완 (점수: {best_match[1]})")
                        book_info = ISBNService._merge_book_info(book_info, best_match[0])

            print(f"[ISBN Service] 최종 결과:")
            print(f"  - 제목: {book_info.get('title', 'N/A')}")
            print(f"  - 저자: {book_info.get('author', 'N/A')}")
            print(f"  - 출판사: {book_info.get('publisher', 'N/A')}")
            print(f"  - 표지: {book_info.get('cover_image_url', 'N/A')}")

            return book_info

        except requests.RequestException as e:
            print(f"[ISBN Service] 네트워크 오류: {e}")
            return None
        except Exception as e:
            print(f"[ISBN Service] 예상치 못한 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
