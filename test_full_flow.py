#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""전체 플로우 테스트"""
import sys
import requests
import time
import json

BASE_URL = "http://localhost:5000"

# 테스트 데이터
test_data = {
    "student_name": "테스트학생",
    "grade": "중등",
    "essay_text": "스마트폰 사용을 제한해야 하는가\n\n요즘 스마트폰은 필수품이 되었다. 하지만 청소년들의 과도한 사용이 문제다.\n\n첫째, 건강에 안좋다. 눈이 나빠지고 거북목이 생긴다.\n\n둘째로, 공부에 집중을 못한다. 알림이 오면 자꾸 확인하게 된다.\n\n결론적으로 적절한 제한이 필요하다."
}

print("=== MOMOAI 전체 플로우 테스트 ===\n")

# 1. 첨삭 요청
print("1. 첨삭 요청 중...")
try:
    response = requests.post(f"{BASE_URL}/api/review", json=test_data)
    result = response.json()
    task_id = result['task_id']
    print(f"   ✓ Task ID: {task_id}")
    print(f"   Status: {result['status']}")
except Exception as e:
    print(f"   ✗ 오류: {e}")
    sys.exit(1)

# 2. 작업 완료 대기
print("\n2. 첨삭 완료 대기 중...")
max_wait = 300  # 5분
waited = 0
while waited < max_wait:
    try:
        response = requests.get(f"{BASE_URL}/api/task_status/{task_id}")
        status = response.json()

        if status['status'] == 'completed':
            print(f"   ✓ 첨삭 완료!")
            print(f"   Student: {status['student_name']} ({status['grade']})")
            break
        elif status['status'] == 'failed':
            print(f"   ✗ 첨삭 실패")
            sys.exit(1)
        else:
            print(f"   ... 진행 중 ({waited}초)")
            time.sleep(10)
            waited += 10
    except Exception as e:
        print(f"   오류: {e}")
        time.sleep(10)
        waited += 10

if waited >= max_wait:
    print("   ✗ 타임아웃")
    sys.exit(1)

# 3. 데이터베이스 확인
print("\n3. 데이터베이스 확인 중...")
import database
task = database.get_task(task_id)
print(f"   HTML Path: {task['html_path']}")
print(f"   PDF Path: {task['pdf_path']}")

if not task['html_path']:
    print("   ✗ HTML 경로가 저장되지 않았습니다!")
    sys.exit(1)

# 4. PDF 생성
print("\n4. PDF 생성 중...")
try:
    response = requests.post(f"{BASE_URL}/api/generate_pdf/{task_id}")
    result = response.json()
    if response.ok:
        print(f"   ✓ PDF 생성 완료: {result['pdf_filename']}")
    else:
        print(f"   ✗ PDF 생성 실패: {result.get('error', 'Unknown error')}")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ 오류: {e}")
    sys.exit(1)

# 5. 데이터베이스 재확인
print("\n5. PDF 경로 확인 중...")
task = database.get_task(task_id)
print(f"   PDF Path: {task['pdf_path']}")

if not task['pdf_path']:
    print("   ✗ PDF 경로가 저장되지 않았습니다!")
    sys.exit(1)

print("\n=== 모든 테스트 통과! ===")
print(f"\n결과 페이지: {BASE_URL}/result/{task_id}")
