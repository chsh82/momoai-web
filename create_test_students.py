# -*- coding: utf-8 -*-
"""테스트용 학생 데이터 100개 생성"""
from app import create_app, db
from app.models import Student, User
import random

app = create_app()

# 한국 성씨 (가장 흔한 50개)
last_names = [
    '김', '이', '박', '최', '정', '강', '조', '윤', '장', '임',
    '한', '오', '서', '신', '권', '황', '안', '송', '전', '홍',
    '유', '고', '문', '양', '손', '배', '백', '허', '남', '심',
    '노', '하', '곽', '성', '차', '주', '우', '구', '민', '원',
    '나', '지', '엄', '채', '류', '천', '방', '표', '변', '석'
]

# 한국 이름 (2글자 이름)
first_names_first = [
    '서', '지', '민', '예', '수', '하', '은', '준', '현', '유',
    '도', '시', '재', '정', '승', '태', '영', '선', '미', '경',
    '윤', '진', '아', '소', '다', '나', '라', '가', '호', '건'
]

first_names_second = [
    '준', '윤', '서', '현', '우', '진', '민', '아', '영', '은',
    '희', '주', '연', '빈', '호', '원', '수', '하', '경', '미',
    '지', '예', '나', '혁', '재', '석', '범', '철', '훈', '성'
]

# 학년 목록
grades = [
    '초1', '초2', '초3', '초4', '초5', '초6',
    '중1', '중2', '중3',
    '고1', '고2', '고3'
]

with app.app_context():
    print("=" * 60)
    print("테스트 학생 데이터 100개 생성")
    print("=" * 60)

    # 강사 계정 가져오기 (학생들의 담당 강사)
    teacher = User.query.filter_by(role='teacher').first()
    if not teacher:
        print("[ERROR] 강사 계정이 없습니다. 먼저 강사를 생성하세요.")
        exit(1)

    print(f"\n담당 강사: {teacher.name} ({teacher.email})")

    # 기존 테스트 학생 삭제 (선택사항)
    # Student.query.delete()
    # db.session.commit()

    created_students = []
    existing_count = Student.query.count()

    print(f"\n기존 학생 수: {existing_count}명")
    print("새 학생 100명 생성 중...\n")

    for i in range(100):
        # 랜덤 이름 생성
        last_name = random.choice(last_names)
        first_name = random.choice(first_names_first) + random.choice(first_names_second)
        full_name = last_name + first_name

        # 랜덤 학년
        grade = random.choice(grades)

        # 랜덤 연락처 (010-XXXX-XXXX)
        phone = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

        # 이메일 (선택사항, 50%만)
        email = None
        if random.random() > 0.5:
            email = f"{last_name.lower()}{first_name.lower()}{random.randint(100, 999)}@example.com"

        # Tier (등급) 랜덤 할당
        tier = random.choice(['A', 'B', 'C', 'VIP', None])

        # 학생 생성
        student = Student(
            teacher_id=teacher.user_id,
            name=full_name,
            grade=grade,
            phone=phone,
            email=email,
            tier=tier,
            notes=f"테스트 학생 #{i+1}"
        )

        db.session.add(student)
        created_students.append(student)

        # 진행상황 출력 (10명마다)
        if (i + 1) % 10 == 0:
            print(f"  [OK] {i+1}명 생성 완료...")

    # 커밋
    db.session.commit()

    print(f"\n[OK] 총 {len(created_students)}명의 학생 생성 완료!")

    # 학년별 통계
    print("\n" + "=" * 60)
    print("학년별 학생 수:")
    print("=" * 60)

    for grade in grades:
        count = Student.query.filter_by(grade=grade).count()
        print(f"  {grade}: {count}명")

    print("\n" + "=" * 60)
    print("생성 완료!")
    print("=" * 60)

    # 샘플 학생 5명 출력
    print("\n샘플 학생 (처음 5명):")
    for i, student in enumerate(created_students[:5], 1):
        print(f"\n  {i}. {student.name}")
        print(f"     - 학년: {student.grade}")
        print(f"     - 연락처: {student.phone}")
        if student.email:
            print(f"     - 이메일: {student.email}")
        if student.tier:
            print(f"     - 등급: {student.tier}")

    print(f"\n현재 전체 학생 수: {Student.query.count()}명")
