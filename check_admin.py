"""관리자 계정 확인 및 재생성"""
from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app('development')

with app.app_context():
    # 기존 관리자 확인
    admin = User.query.filter_by(email='admin@momoai.com').first()

    if admin:
        print("Admin account found:")
        print(f"  Email: {admin.email}")
        print(f"  Name: {admin.name}")
        print(f"  Role: {admin.role}")
        print(f"  Active: {admin.is_active}")

        # 비밀번호 테스트
        test_password = 'admin123'
        if check_password_hash(admin.password_hash, test_password):
            print(f"\n[OK] Password 'admin123' is CORRECT")
        else:
            print(f"\n[ERROR] Password 'admin123' does NOT match")
            print("\nResetting password to 'admin123'...")
            admin.password_hash = generate_password_hash('admin123')
            db.session.commit()
            print("[OK] Password reset successfully!")
    else:
        print("[ERROR] No admin account found!")
        print("Creating new admin account...")

        admin = User(
            email='admin@momoai.com',
            password_hash=generate_password_hash('admin123'),
            name='Admin',
            role='admin',
            role_level=1,
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print("[OK] Admin account created!")

    print("\n" + "="*50)
    print("Login credentials:")
    print("Email: admin@momoai.com")
    print("Password: admin123")
    print("="*50)
