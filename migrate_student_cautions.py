# -*- coding: utf-8 -*-
"""student_cautions 테이블 마이그레이션"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS student_cautions (
    caution_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      VARCHAR(36) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    author_id       VARCHAR(36) REFERENCES users(user_id) ON DELETE SET NULL,
    category        VARCHAR(30) NOT NULL DEFAULT 'other',
    severity        VARCHAR(20) NOT NULL DEFAULT 'caution',
    title           VARCHAR(200) NOT NULL,
    content         TEXT NOT NULL,
    is_resolved     BOOLEAN NOT NULL DEFAULT 0,
    resolved_by_id  VARCHAR(36) REFERENCES users(user_id) ON DELETE SET NULL,
    resolved_at     DATETIME,
    resolve_note    TEXT,
    consultation_id INTEGER REFERENCES consultation_records(consultation_id) ON DELETE SET NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_SQLS = [
    "CREATE INDEX IF NOT EXISTS ix_student_cautions_student_id  ON student_cautions(student_id);",
    "CREATE INDEX IF NOT EXISTS ix_student_cautions_is_resolved ON student_cautions(is_resolved);",
    "CREATE INDEX IF NOT EXISTS ix_student_cautions_created_at  ON student_cautions(created_at);",
]

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()
cur.execute(CREATE_SQL)
for sql in INDEX_SQLS:
    cur.execute(sql)
conn.commit()
conn.close()
print("student_cautions 테이블 생성 완료")
