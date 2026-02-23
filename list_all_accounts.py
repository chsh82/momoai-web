"""모든 계정 목록 조회"""
from app import create_app, db
from app.models.user import User
from app.models.student import Student

app = create_app('development')

with app.app_context():
    print("=" * 80)
    print("MOMOAI v4.0 - 전체 계정 목록")
    print("=" * 80)

    # User 테이블의 모든 계정
    users = User.query.order_by(User.role_level, User.email).all()

    print(f"\n[총 {len(users)}개의 계정]\n")

    role_groups = {
        'admin': [],
        'teacher': [],
        'parent': [],
        'student': []
    }

    for user in users:
        role_groups[user.role].append(user)

    # 관리자 계정
    if role_groups['admin']:
        print("\n" + "=" * 80)
        print("[관리자 계정]")
        print("=" * 80)
        for user in role_groups['admin']:
            print(f"\n이메일: {user.email}")
            print(f"이름: {user.name}")
            print(f"역할: {user.role} (레벨 {user.role_level})")
            print(f"활성화: {user.is_active}")
            print(f"전화번호: {user.phone or 'N/A'}")
            print(f"생성일: {user.created_at}")
            print(f"마지막 로그인: {user.last_login or 'Never'}")

    # 강사 계정
    if role_groups['teacher']:
        print("\n" + "=" * 80)
        print(f"[강사 계정] - {len(role_groups['teacher'])}명")
        print("=" * 80)
        for idx, user in enumerate(role_groups['teacher'], 1):
            print(f"\n{idx}. {user.name} ({user.email})")
            print(f"   활성화: {user.is_active}, 전화번호: {user.phone or 'N/A'}")

    # 학부모 계정
    if role_groups['parent']:
        print("\n" + "=" * 80)
        print(f"[학부모 계정] - {len(role_groups['parent'])}명")
        print("=" * 80)
        for idx, user in enumerate(role_groups['parent'], 1):
            print(f"\n{idx}. {user.name} ({user.email})")
            print(f"   활성화: {user.is_active}, 전화번호: {user.phone or 'N/A'}")

    # 학생 계정
    if role_groups['student']:
        print("\n" + "=" * 80)
        print(f"[학생 계정] - {len(role_groups['student'])}명")
        print("=" * 80)
        for idx, user in enumerate(role_groups['student'], 1):
            # Student 테이블 정보도 가져오기
            student_record = Student.query.filter_by(user_id=user.user_id).first()
            grade_info = f", 학년: {student_record.grade}" if student_record else ""
            tier_info = f", 등급: {student_record.tier}" if student_record and student_record.tier else ""

            print(f"\n{idx}. {user.name} ({user.email})")
            print(f"   활성화: {user.is_active}{grade_info}{tier_info}")

    print("\n" + "=" * 80)
    print("[비밀번호 정보]")
    print("=" * 80)
    print("\n관리자 계정 (admin@momoai.com):")
    print("  비밀번호: admin123")
    print("\n기타 테스트 계정:")
    print("  - 데이터베이스를 재생성했기 때문에 기존 테스트 계정은 없을 수 있습니다.")
    print("  - 필요한 테스트 계정을 새로 생성하시거나, 회원가입을 통해 계정을 만들 수 있습니다.")
    print("\n" + "=" * 80)
