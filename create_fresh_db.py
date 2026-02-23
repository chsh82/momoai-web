"""
완전히 새로운 데이터베이스를 생성하는 스크립트
"""
import os
from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

# 기존 DB 삭제
db_path = 'momoai.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"[1/3] Deleted old database: {db_path}")

# 앱 생성
app = create_app('development')

with app.app_context():
    # 기존 테이블 모두 삭제
    db.drop_all()
    print("[2/4] Dropped all existing tables")

    # 모든 테이블 생성
    db.create_all()
    print("[3/4] Created all database tables")

    # 관리자 계정 생성
    admin = User(
        email='admin@momoai.com',
        password_hash=generate_password_hash('admin123'),
        name='관리자',
        role='admin',
        role_level=1,
        is_active=True
    )
    db.session.add(admin)
    db.session.commit()
    print("[4/4] Created admin account")
    print("\n✅ Database created successfully!")
    print("\nLogin credentials:")
    print("Email: admin@momoai.com")
    print("Password: admin123")
