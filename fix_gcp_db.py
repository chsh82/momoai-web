"""GCP DB 누락 컬럼 추가 스크립트"""
import sys
sys.path.insert(0, '/home/chsh82/momoai_web')
import os
os.chdir('/home/chsh82/momoai_web')

from app import create_app
from app.models import db

app = create_app()

COLUMNS = [
    "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN locked_until DATETIME",
    "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN zoom_link VARCHAR(500)",
    "ALTER TABLE users ADD COLUMN zoom_token TEXT",
    "ALTER TABLE students ADD COLUMN school VARCHAR(200)",
    "ALTER TABLE students ADD COLUMN birth_date DATE",
]

with app.app_context():
    for sql in COLUMNS:
        try:
            db.session.execute(db.text(sql))
            print("OK:", sql[:70])
        except Exception as e:
            print("SKIP:", str(e)[:70])
    db.session.commit()
    print("\n=== 완료 ===")
