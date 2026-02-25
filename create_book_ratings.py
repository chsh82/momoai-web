"""book_ratings 테이블 생성"""
import warnings
warnings.filterwarnings('ignore')
from app import create_app
from app.models import db

app = create_app()
with app.app_context():
    from sqlalchemy import inspect, text
    ins = inspect(db.engine)
    if 'book_ratings' not in ins.get_table_names():
        db.session.execute(text("""
            CREATE TABLE book_ratings (
                rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id VARCHAR(36) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                user_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                fun_score INTEGER NOT NULL,
                usefulness_score INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, user_id)
            )
        """))
        db.session.commit()
        print("book_ratings 테이블 생성 완료")
    else:
        print("book_ratings 테이블 이미 존재")
