"""
처리 대기 업무(Action Items) 테이블 마이그레이션
실행: python3 migrations/migrate_action_items.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db


def migrate():
    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        # action_items 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                title      VARCHAR(200) NOT NULL,
                content    TEXT,
                category   VARCHAR(50)  DEFAULT '기타',
                priority   VARCHAR(20)  DEFAULT 'medium',
                status     VARCHAR(20)  DEFAULT 'pending',
                created_by VARCHAR(36)  REFERENCES users(user_id),
                assigned_to VARCHAR(36) REFERENCES users(user_id),
                student_id INTEGER      REFERENCES students(student_id) ON DELETE SET NULL,
                due_date   DATE,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ action_items 테이블 생성 완료")

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ 마이그레이션 완료")


if __name__ == '__main__':
    migrate()
