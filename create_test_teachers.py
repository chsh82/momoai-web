# -*- coding: utf-8 -*-
"""테스트용 강사 데이터 10개 생성"""
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
import random

app = create_app()

# 한국 성씨
last_names = ['김', '이', '박', '최', '정', '강', '조', '윤', '장', '임']

# 이름 (교사답게 품위있는 이름)
first_names = [
    '선희', '민준', '서연', '지훈', '수빈',
    '현우', '예진', '동현', '하은', '준서'
]

# 전문 분야
specialties = [
    '영어 독해', '영어 작문', '문학 분석', '논술', '토론',
    '창의적 글쓰기', '비판적 사고', '영어 회화', '학술 영어', '시사 영어'
]

with app.app_context():
    print("=" * 60)
    print("테스트 강사 데이터 10개 생성")
    print("=" * 60)

    created_teachers = []
    existing_count = User.query.filter_by(role='teacher').count()

    print(f"\n기존 강사 수: {existing_count}명")
    print("새 강사 10명 생성 중...\n")

    for i in range(10):
        # 이름 생성
        last_name = last_names[i]
        first_name = first_names[i]
        full_name = last_name + first_name

        # 이메일 생성 (예: kim_teacher1@momoai.com)
        email = f"{last_name.lower()}_teacher{i+1}@momoai.com"

        # 연락처
        phone = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

        # 전문 분야
        specialty = specialties[i]

        # 강사 계정 생성
        teacher = User(
            email=email,
            name=full_name,
            password_hash=generate_password_hash('teacher123'),  # 기본 비밀번호
            role='teacher',
            role_level=3,  # teacher level
            is_active=True
        )

        db.session.add(teacher)
        created_teachers.append({
            'name': full_name,
            'email': email,
            'phone': phone,
            'specialty': specialty
        })

        print(f"  [OK] {i+1}. {full_name} ({email}) - {specialty}")

    # 커밋
    db.session.commit()

    print(f"\n[OK] 총 {len(created_teachers)}명의 강사 생성 완료!")
    print("\n" + "=" * 60)
    print("생성된 강사 계정 정보")
    print("=" * 60)

    for i, teacher in enumerate(created_teachers, 1):
        print(f"\n{i}. {teacher['name']}")
        print(f"   - 이메일: {teacher['email']}")
        print(f"   - 비밀번호: teacher123")
        print(f"   - 연락처: {teacher['phone']}")
        print(f"   - 전문분야: {teacher['specialty']}")

    total_teachers = User.query.filter_by(role='teacher').count()
    print(f"\n현재 전체 강사 수: {total_teachers}명")
    print("\n" + "=" * 60)
    print("✅ 생성 완료! 모든 강사의 비밀번호는 'teacher123' 입니다.")
    print("=" * 60)
