# -*- coding: utf-8 -*-
"""ISBN 조회 서비스 - 알라딘 우선(국내도서 최적), Google Books/네이버 fallback"""
import re
import os
import requests


def _strip_html(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r'<[^>]+>', '', text or '').strip()


class ISBNService:

    ALADIN_API = 'https://www.aladin.co.kr/ttb/api/ItemLookUp.aspx'
    NAVER_API  = 'https://openapi.naver.com/v1/search/book_adv.json'  # ISBN 전용 고급 검색
    GOOGLE_API = 'https://www.googleapis.com/books/v1/volumes'

    # ------------------------------------------------------------------ #
    # 알라딘 도서 API (국내도서 전용, 메타데이터 품질 가장 좋음)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _lookup_aladin(isbn_clean: str) -> dict | None:
        """알라딘 Open API로 ISBN 조회"""
        ttb_key = os.environ.get('ALADIN_TTB_KEY')
        if not ttb_key:
            print('[Aladin Books] API 키가 설정되지 않았습니다.')
            return None

        try:
            resp = requests.get(
                ISBNService.ALADIN_API,
                params={
                    'ttbkey': ttb_key,
                    'itemIdType': 'ISBN13' if len(isbn_clean) == 13 else 'ISBN',
                    'ItemId': isbn_clean,
                    'output': 'js',
                    'Version': '20131101',
                    'Cover': 'Big',
                },
                timeout=8,
            )
            if resp.status_code != 200:
                print(f'[Aladin Books] HTTP {resp.status_code}: {resp.text[:200]}')
                return None

            data = resp.json()
            if data.get('errorCode'):
                print(f"[Aladin Books] 오류: {data.get('errorMessage')}")
                return None

            items = data.get('item', [])
            if not items:
                print(f'[Aladin Books] ISBN {isbn_clean} 검색 결과 없음')
                return None

            item = items[0]

            # 출판연도: "2016-09-23" → 2016
            pub_year = None
            pub_date = item.get('pubDate', '')
            if pub_date and len(pub_date) >= 4:
                try:
                    pub_year = int(pub_date[:4])
                except ValueError:
                    pass

            # 저자: "우지영 (지은이), 김은재 (그림)" → "우지영, 김은재"
            author_raw = item.get('author', '')
            author = ', '.join(
                re.sub(r'\s*\([^)]*\)\s*$', '', p.strip())
                for p in author_raw.split(',')
                if p.strip()
            )

            cover = item.get('cover') or None
            if cover and cover.startswith('http://'):
                cover = cover.replace('http://', 'https://')

            result = {
                'title':            item.get('title', ''),
                'author':           author,
                'publisher':        item.get('publisher', ''),
                'publication_year': pub_year,
                'description':      item.get('description', ''),
                'cover_image_url':  cover,
                'isbn':             item.get('isbn13') or isbn_clean,
            }
            print(f'[Aladin Books] 조회 성공: {result["title"]}')
            return result

        except requests.RequestException as e:
            print(f'[Aladin Books] 네트워크 오류: {e}')
            return None
        except Exception as e:
            print(f'[Aladin Books] 예상치 못한 오류: {e}')
            return None

    # ------------------------------------------------------------------ #
    # 네이버 도서 API
    # ------------------------------------------------------------------ #

    @staticmethod
    def _lookup_naver(isbn_clean: str) -> dict | None:
        """네이버 도서 검색 API로 ISBN 조회"""
        client_id     = os.environ.get('NAVER_CLIENT_ID')
        client_secret = os.environ.get('NAVER_CLIENT_SECRET')
        if not client_id or not client_secret:
            print('[Naver Books] API 키가 설정되지 않았습니다.')
            return None

        try:
            resp = requests.get(
                ISBNService.NAVER_API,
                params={'d_isbn': isbn_clean, 'display': 1},
                headers={
                    'X-Naver-Client-Id':     client_id,
                    'X-Naver-Client-Secret': client_secret,
                },
                timeout=8,
            )
            if resp.status_code != 200:
                print(f'[Naver Books] HTTP {resp.status_code}')
                return None

            items = resp.json().get('items', [])
            if not items:
                print(f'[Naver Books] ISBN {isbn_clean} 검색 결과 없음')
                return None

            item = items[0]

            # 출판연도: "20231015" → 2023
            pub_year = None
            pubdate  = item.get('pubdate', '')
            if pubdate and len(pubdate) >= 4:
                try:
                    pub_year = int(pubdate[:4])
                except ValueError:
                    pass

            # 저자: "홍길동 지음^김영희 옮김" → "홍길동, 김영희"
            author_raw = _strip_html(item.get('author', ''))
            author = ', '.join(
                re.sub(r'\s*(지음|옮김|그림|엮음|감수|저|역)\s*$', '', p.strip())
                for p in author_raw.split('^')
                if p.strip()
            )

            cover = item.get('image', '') or None
            if cover and cover.startswith('http://'):
                cover = cover.replace('http://', 'https://')

            result = {
                'title':            _strip_html(item.get('title', '')),
                'author':           author,
                'publisher':        _strip_html(item.get('publisher', '')),
                'publication_year': pub_year,
                'description':      _strip_html(item.get('description', '')),
                'cover_image_url':  cover,
                'isbn':             isbn_clean,
            }
            print(f'[Naver Books] 조회 성공: {result["title"]}')
            return result

        except requests.RequestException as e:
            print(f'[Naver Books] 네트워크 오류: {e}')
            return None
        except Exception as e:
            print(f'[Naver Books] 예상치 못한 오류: {e}')
            return None

    # ------------------------------------------------------------------ #
    # Google Books API (fallback)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _lookup_google(isbn_clean: str) -> dict | None:
        """Google Books API로 ISBN 조회"""
        try:
            params = {'q': f'isbn:{isbn_clean}', 'maxResults': 1}
            api_key = os.environ.get('GOOGLE_BOOKS_API_KEY')
            if api_key:
                params['key'] = api_key

            resp = requests.get(
                ISBNService.GOOGLE_API,
                params=params,
                timeout=10,
            )
            if resp.status_code != 200:
                print(f'[Google Books] HTTP {resp.status_code}: {resp.text[:200]}')
                return None

            items = resp.json().get('items', [])
            if not items:
                print(f'[Google Books] ISBN {isbn_clean} 검색 결과 없음')
                return None

            info = items[0].get('volumeInfo', {})

            pub_year = None
            pubdate  = info.get('publishedDate', '')
            if pubdate:
                try:
                    pub_year = int(pubdate[:4])
                except (ValueError, IndexError):
                    pass

            img_links = info.get('imageLinks', {})
            cover = (
                img_links.get('extraLarge') or img_links.get('large') or
                img_links.get('medium')     or img_links.get('small') or
                img_links.get('thumbnail')  or img_links.get('smallThumbnail')
            )
            if cover and cover.startswith('http://'):
                cover = cover.replace('http://', 'https://')

            result = {
                'title':            info.get('title', ''),
                'author':           ', '.join(info.get('authors', [])),
                'publisher':        info.get('publisher', ''),
                'publication_year': pub_year,
                'description':      info.get('description', ''),
                'cover_image_url':  cover or None,
                'isbn':             isbn_clean,
            }
            print(f'[Google Books] 조회 성공: {result["title"]}')
            return result

        except Exception as e:
            print(f'[Google Books] 오류: {e}')
            return None

    # ------------------------------------------------------------------ #
    # 공개 인터페이스
    # ------------------------------------------------------------------ #

    @staticmethod
    def lookup_isbn(isbn: str) -> dict | None:
        """
        ISBN으로 도서 정보 조회.
        1순위: 알라딘 (국내도서 메타데이터 품질 최상)
        2순위: Google Books (알라딘에 없는 해외도서 등)
        3순위: 네이버 도서 API (2026-08 기준 접근 불가, 복구되면 자동으로 다시 쓰임)
        """
        isbn_clean = isbn.replace('-', '').replace(' ', '')
        print(f'[ISBN Service] 조회: {isbn_clean}')

        # 1순위: 알라딘
        result = ISBNService._lookup_aladin(isbn_clean)
        if result and result.get('title'):
            return result

        # 2순위: Google Books
        print('[ISBN Service] 알라딘 실패 → Google Books fallback')
        result = ISBNService._lookup_google(isbn_clean)
        if result and result.get('title'):
            return result

        # 3순위: 네이버 (fallback)
        print('[ISBN Service] Google Books 실패 → 네이버 fallback')
        result = ISBNService._lookup_naver(isbn_clean)
        if result and result.get('title'):
            return result

        print(f'[ISBN Service] {isbn_clean} 조회 실패 (전체 API)')
        return None
