"""teaching_materials 테이블에 book_id 컬럼 추가"""
import sqlite3, os

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db'))

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(teaching_materials)")
    cols = [r[1] for r in cur.fetchall()]
    if 'book_id' in cols:
        print("이미 book_id 컬럼이 있습니다.")
        conn.close()
        return
    cur.execute("ALTER TABLE teaching_materials ADD COLUMN book_id VARCHAR(36) REFERENCES books(book_id) ON DELETE SET NULL")
    conn.commit()
    conn.close()
    print("마이그레이션 완료: book_id 컬럼 추가")

if __name__ == '__main__':
    migrate()
