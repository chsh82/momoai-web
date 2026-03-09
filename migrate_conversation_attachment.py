"""DB 마이그레이션: conversation_messages 테이블에 attachment 컬럼 추가"""
import sqlite3, os
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(conversation_messages)")
cols = [r[1] for r in cursor.fetchall()]
for col, typ in [('attachment_url', 'VARCHAR(500)'), ('attachment_name', 'VARCHAR(200)')]:
    if col not in cols:
        cursor.execute(f"ALTER TABLE conversation_messages ADD COLUMN {col} {typ}")
        print(f"{col} 컬럼 추가됨")
    else:
        print(f"{col} 이미 존재")
conn.commit()
conn.close()
print("마이그레이션 완료")
