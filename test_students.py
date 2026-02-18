#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""학생 관리 기능 테스트 스크립트"""
from app import create_app
from app.models import db, User, Student

app = create_app('development')

with app.app_context():
    print("=" * 50)
    print("학생 관리 기능 테스트")
    print("=" * 50)

    # 테스트 사용자 확인
    user = User.query.filter_by(email='test@momoai.com').first()
    if not user:
        print("[ERROR] 테스트 사용자가 없습니다. test_auth.py를 먼저 실행하세요.")
        exit(1)

    print(f"\n[OK] 테스트 사용자: {user.name} ({user.email})")

    # 기존 테스트 학생 삭제
    existing_students = Student.query.filter_by(teacher_id=user.user_id).all()
    for s in existing_students:
        db.session.delete(s)
    db.session.commit()
    print(f"[OK] 기존 학생 {len(existing_students)}명 삭제됨")

    # 테스트 학생 생성
    test_students = [
        {
            'name': '김모모',
            'grade': '중등',
            'email': 'momo@example.com',
            'phone': '010-1234-5678',
            'notes': '논술 실력이 우수한 학생'
        },
        {
            'name': '이첨삭',
            'grade': '고등',
            'email': 'cheom@example.com',
            'phone': '010-2345-6789',
            'notes': '꼼꼼한 성격'
        },
        {
            'name': '박글쓰기',
            'grade': '초등',
            'email': None,
            'phone': None,
            'notes': None
        },
        {
            'name': '최논술',
            'grade': '중등',
            'email': 'nonsul@example.com',
            'phone': None,
            'notes': '창의적인 글쓰기'
        },
    ]

    created_students = []
    for data in test_students:
        student = Student(
            teacher_id=user.user_id,
            name=data['name'],
            grade=data['grade'],
            email=data['email'],
            phone=data['phone'],
            notes=data['notes']
        )
        db.session.add(student)
        created_students.append(student)

    db.session.commit()
    print(f"\n[OK] {len(created_students)}명의 테스트 학생 생성")

    # 생성된 학생 목록 출력
    print("\n생성된 학생 목록:")
    for i, student in enumerate(created_students, 1):
        print(f"  {i}. {student.name} ({student.grade})")
        print(f"     - Student ID: {student.student_id}")
        if student.email:
            print(f"     - Email: {student.email}")
        if student.phone:
            print(f"     - Phone: {student.phone}")
        if student.notes:
            print(f"     - Notes: {student.notes}")

    # 학생 조회 테스트
    print(f"\n[TEST] 학생 조회")
    all_students = Student.query.filter_by(teacher_id=user.user_id).all()
    print(f"  [OK] 총 {len(all_students)}명 조회됨")

    # 학생 이름 검색 테스트
    print(f"\n[TEST] 학생 이름 검색 (검색어: '김')")
    search_results = Student.query.filter_by(teacher_id=user.user_id).filter(
        Student.name.contains('김')
    ).all()
    print(f"  [OK] {len(search_results)}명 검색됨: {', '.join([s.name for s in search_results])}")

    # 학년 필터 테스트
    print(f"\n[TEST] 학년 필터 (중등)")
    grade_results = Student.query.filter_by(teacher_id=user.user_id, grade='중등').all()
    print(f"  [OK] {len(grade_results)}명 검색됨: {', '.join([s.name for s in grade_results])}")

    # 학생 수정 테스트
    print(f"\n[TEST] 학생 정보 수정")
    test_student = created_students[0]
    old_name = test_student.name
    test_student.notes = "수정된 메모입니다."
    db.session.commit()
    print(f"  [OK] {old_name}의 메모가 수정됨")

    # 학생 삭제 테스트
    print(f"\n[TEST] 학생 삭제")
    student_to_delete = created_students[-1]
    delete_name = student_to_delete.name
    db.session.delete(student_to_delete)
    db.session.commit()
    print(f"  [OK] {delete_name} 삭제됨")

    # 최종 학생 수 확인
    final_count = Student.query.filter_by(teacher_id=user.user_id).count()
    print(f"\n[OK] 최종 학생 수: {final_count}명")

    print("\n" + "=" * 50)
    print("테스트 완료!")
    print("=" * 50)
    print("\n웹 브라우저에서 테스트:")
    print("1. http://localhost:5000/auth/login")
    print("   - Email: test@momoai.com")
    print("   - Password: testpassword123")
    print("\n2. 로그인 후:")
    print("   - http://localhost:5000/students - 학생 목록")
    print("   - http://localhost:5000/students/new - 새 학생 추가")
