#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""강사 포털 MBTI 데이터 디버깅"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User, Student
from app.models.reading_mbti import ReadingMBTIResult
from sqlalchemy import desc

print("=" * 70)
print("🔍 강사 포털 MBTI 데이터 디버깅")
print("=" * 70)

app = create_app('development')

with app.app_context():
    # 박선진 선생님
    teacher = User.query.filter_by(name='박선진', role='teacher').first()

    if not teacher:
        print("\n❌ 박선진 선생님을 찾을 수 없습니다.")
        sys.exit(1)

    print(f"\n✅ 박선진 선생님 (ID: {teacher.user_id})")

    # 담당 학생 목록
    my_students = Student.query.filter_by(teacher_id=teacher.user_id).all()
    print(f"\n📚 담당 학생: {len(my_students)}명")

    for student in my_students:
        print(f"  - {student.name} (ID: {student.student_id})")

    # 학생 ID 리스트
    student_ids = [s.student_id for s in my_students]
    print(f"\n🔑 Student IDs 리스트: {len(student_ids)}개")

    # MBTI 결과 조회
    results = ReadingMBTIResult.query.filter(
        ReadingMBTIResult.student_id.in_(student_ids)
    ).order_by(desc(ReadingMBTIResult.created_at)).all()

    print(f"\n📊 MBTI 검사 결과: {len(results)}개")

    for result in results:
        student = Student.query.get(result.student_id)
        print(f"\n  학생: {student.name if student else '알 수 없음'}")
        print(f"  Student ID: {result.student_id}")
        print(f"  유형: {result.mbti_type.type_name} ({result.mbti_type.type_code})")
        print(f"  검사일: {result.created_at.strftime('%Y-%m-%d')}")
        print(f"  독해력: {result.read_type}, 사고력: {result.speech_type}, 서술력: {result.write_type}")

    # latest_results 딕셔너리 구성
    latest_results = {}
    for result in results:
        if result.student_id not in latest_results:
            latest_results[result.student_id] = result

    print(f"\n📋 latest_results 딕셔너리: {len(latest_results)}개")
    for student_id, result in latest_results.items():
        student = Student.query.get(student_id)
        print(f"  [{student.name if student else '알 수 없음'}] {result.mbti_type.type_name}")

    # 박지원 학생 특별 확인
    print("\n" + "=" * 70)
    print("🔍 박지원 학생 특별 확인")
    print("=" * 70)

    jiwon = Student.query.filter_by(name='박지원').first()
    if jiwon:
        print(f"\n✅ 박지원 학생 찾음")
        print(f"  Student ID: {jiwon.student_id}")
        print(f"  Teacher ID: {jiwon.teacher_id}")
        print(f"  담당 선생님: {jiwon.teacher.name if jiwon.teacher else '없음'}")
        print(f"  박선진 선생님의 담당 학생인가? {jiwon.student_id in student_ids}")

        # 박지원의 MBTI 결과
        jiwon_results = ReadingMBTIResult.query.filter_by(
            student_id=jiwon.student_id
        ).order_by(desc(ReadingMBTIResult.created_at)).all()

        print(f"\n  박지원의 MBTI 결과: {len(jiwon_results)}개")
        for r in jiwon_results:
            print(f"    - {r.created_at.strftime('%Y-%m-%d')}: {r.mbti_type.type_name} ({r.mbti_type.type_code})")

        print(f"\n  latest_results에 포함되어 있나? {jiwon.student_id in latest_results}")
        if jiwon.student_id in latest_results:
            r = latest_results[jiwon.student_id]
            print(f"    → {r.mbti_type.type_name} ({r.created_at.strftime('%Y-%m-%d')})")
    else:
        print("\n❌ 박지원 학생을 찾을 수 없습니다.")

    print("\n" + "=" * 70)
    print("완료!")
    print("=" * 70)
