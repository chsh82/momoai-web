"""로그인 테스트"""
from app import create_app, db
from app.models.user import User
from werkzeug.security import check_password_hash

app = create_app('development')

with app.app_context():
    # 이메일로 사용자 찾기
    test_email = 'admin@momoai.com'
    test_password = 'admin123'

    print(f"Testing login for: {test_email}")
    print(f"Password: {test_password}")
    print("="*50)

    user = User.query.filter_by(email=test_email).first()

    if user:
        print(f"\n[FOUND] User found in database")
        print(f"  Email: {user.email}")
        print(f"  Name: {user.name}")
        print(f"  Role: {user.role}")
        print(f"  Role Level: {user.role_level}")
        print(f"  Active: {user.is_active}")
        print(f"  Must Change Password: {user.must_change_password}")

        # check_password 메서드 테스트
        if user.check_password(test_password):
            print(f"\n[SUCCESS] user.check_password() returned TRUE")
            print("Login should work!")
        else:
            print(f"\n[FAIL] user.check_password() returned FALSE")
            print("Password does not match!")

        # 직접 check_password_hash 테스트
        if check_password_hash(user.password_hash, test_password):
            print(f"\n[SUCCESS] check_password_hash() returned TRUE")
        else:
            print(f"\n[FAIL] check_password_hash() returned FALSE")

        # is_active 확인
        if not user.is_active:
            print(f"\n[WARNING] Account is NOT active!")
    else:
        print(f"\n[ERROR] User not found!")
        print("Please check the email address.")

    # 모든 사용자 출력
    print("\n" + "="*50)
    print("All users in database:")
    all_users = User.query.all()
    for u in all_users:
        print(f"  - {u.email} ({u.name}) - Role: {u.role}")
