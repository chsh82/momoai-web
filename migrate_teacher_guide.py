# -*- coding: utf-8 -*-
"""teacher_guide 컬럼 추가 + teacher_prompt_templates 테이블 생성"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. essays.teacher_guide 컬럼 추가
cursor.execute("PRAGMA table_info(essays)")
columns = [row[1] for row in cursor.fetchall()]
if 'teacher_guide' not in columns:
    cursor.execute("ALTER TABLE essays ADD COLUMN teacher_guide TEXT")
    print("essays.teacher_guide 컬럼 추가 완료")
else:
    print("essays.teacher_guide 컬럼 이미 존재")

# 2. teacher_prompt_templates 테이블 생성
cursor.execute("""
    CREATE TABLE IF NOT EXISTS teacher_prompt_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        title VARCHAR(100) NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_tpt_teacher ON teacher_prompt_templates(teacher_id)")
print("teacher_prompt_templates 테이블 생성 완료")

conn.commit()
conn.close()
print("마이그레이션 완료")
