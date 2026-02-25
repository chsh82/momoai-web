"""inquiry_posts 테이블에 recipient_id 컬럼 추가"""
from app import create_app
from app.models import db
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('inquiry_posts')]
    if 'recipient_id' not in cols:
        db.session.execute(text('ALTER TABLE inquiry_posts ADD COLUMN recipient_id VARCHAR(36) REFERENCES users(user_id)'))
        db.session.commit()
        print("recipient_id 컬럼 추가 완료")
    else:
        print("recipient_id 컬럼 이미 존재")
