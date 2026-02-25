"""books 테이블에 is_curriculum, is_recommended 컬럼 추가"""
import warnings
warnings.filterwarnings('ignore')
from app import create_app
from app.models import db
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    ins = inspect(db.engine)
    cols = [c['name'] for c in ins.get_columns('books')]
    changed = False
    if 'is_curriculum' not in cols:
        db.session.execute(text('ALTER TABLE books ADD COLUMN is_curriculum BOOLEAN NOT NULL DEFAULT 0'))
        print('is_curriculum 컬럼 추가 완료')
        changed = True
    else:
        print('is_curriculum 이미 존재')
    if 'is_recommended' not in cols:
        db.session.execute(text('ALTER TABLE books ADD COLUMN is_recommended BOOLEAN NOT NULL DEFAULT 0'))
        print('is_recommended 컬럼 추가 완료')
        changed = True
    else:
        print('is_recommended 이미 존재')
    if changed:
        db.session.commit()
