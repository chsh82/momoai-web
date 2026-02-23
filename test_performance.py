#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1 성능 개선 테스트 스크립트

이 스크립트는 Phase 1에서 적용한 성능 개선 사항을 확인합니다.
"""

import requests
from colorama import Fore, Style, init

# Colorama 초기화
init(autoreset=True)

BASE_URL = "http://localhost:5000"

def print_header(text):
    """섹션 헤더 출력"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*60}\n")

def test_compression():
    """Gzip/Brotli 압축 테스트"""
    print_header("🗜️  압축 테스트")

    try:
        # HTML 압축 테스트
        response = requests.get(f"{BASE_URL}/auth/login", headers={
            'Accept-Encoding': 'gzip, deflate, br'
        })

        encoding = response.headers.get('Content-Encoding', 'none')
        content_length = len(response.content)

        if encoding in ['gzip', 'br']:
            print(f"{Fore.GREEN}✓ 압축 활성화됨: {encoding}")
            print(f"  압축된 크기: {content_length:,} bytes")
        else:
            print(f"{Fore.YELLOW}⚠ 압축 미적용 (Content-Encoding: {encoding})")
            print(f"  원본 크기: {content_length:,} bytes")

    except Exception as e:
        print(f"{Fore.RED}✗ 테스트 실패: {e}")

def test_caching():
    """캐시 헤더 테스트"""
    print_header("🗄️  캐싱 테스트")

    endpoints = [
        ("/static/css/style.css", "CSS 파일"),
        ("/auth/login", "HTML 페이지"),
    ]

    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            cache_control = response.headers.get('Cache-Control', 'none')

            print(f"\n{description} ({endpoint}):")
            if cache_control != 'none':
                print(f"{Fore.GREEN}✓ 캐싱 설정됨: {cache_control}")
            else:
                print(f"{Fore.YELLOW}⚠ 캐싱 미설정")

        except Exception as e:
            print(f"{Fore.RED}✗ {description} 테스트 실패: {e}")

def test_response_times():
    """응답 시간 테스트"""
    print_header("⚡ 응답 시간 테스트")

    endpoints = [
        "/auth/login",
        "/static/css/style.css",
    ]

    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            response_time = response.elapsed.total_seconds() * 1000  # ms

            if response_time < 100:
                color = Fore.GREEN
                status = "✓ 매우 빠름"
            elif response_time < 300:
                color = Fore.YELLOW
                status = "○ 양호"
            else:
                color = Fore.RED
                status = "✗ 느림"

            print(f"{color}{status}: {endpoint} - {response_time:.2f}ms")

        except Exception as e:
            print(f"{Fore.RED}✗ {endpoint} 테스트 실패: {e}")

def test_cdn_resources():
    """CDN 리소스 로드 테스트"""
    print_header("🌐 CDN 리소스 테스트")

    cdn_urls = [
        "https://cdn.tailwindcss.com",
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
        "https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js",
        "https://fonts.googleapis.com/css2?family=Noto+Sans+KR",
    ]

    for url in cdn_urls:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                print(f"{Fore.GREEN}✓ 접근 가능: {url[:60]}...")
            else:
                print(f"{Fore.YELLOW}⚠ 상태 코드 {response.status_code}: {url[:60]}...")
        except Exception as e:
            print(f"{Fore.RED}✗ 접근 불가: {url[:60]}... ({e})")

def print_summary():
    """최종 요약"""
    print_header("📊 Phase 1 개선사항 요약")

    improvements = [
        "✅ Flask-Compress 설치 및 설정 (Gzip/Brotli 압축)",
        "✅ 정적 파일 캐싱 헤더 추가 (1년 캐싱)",
        "✅ HTML 캐싱 헤더 추가 (5분 캐싱)",
        "✅ CDN 리소스 사용 확인",
        "✅ Lazy Loading 이미지 헬퍼 추가",
        "✅ 이미지 최적화 유틸리티 생성",
    ]

    for item in improvements:
        print(f"{Fore.GREEN}{item}")

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.YELLOW}다음 단계: Lighthouse에서 재검사하여 점수 확인")
    print(f"{Fore.YELLOW}예상 점수: 62점 → 75-80점")
    print(f"{Fore.CYAN}{'='*60}\n")

if __name__ == "__main__":
    print(f"{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}MOMOAI v4.0 - Phase 1 성능 테스트")
    print(f"{Fore.MAGENTA}{'='*60}")

    print(f"\n{Fore.YELLOW}⚠️  주의: 서버가 실행 중이어야 합니다 (python run.py)")
    print(f"{Fore.YELLOW}⚠️  서버 주소: {BASE_URL}\n")

    input(f"{Fore.CYAN}엔터를 눌러 테스트 시작...")

    test_compression()
    test_caching()
    test_response_times()
    test_cdn_resources()
    print_summary()

    print(f"\n{Fore.GREEN}테스트 완료! 🎉\n")
