"""
teaching_materials.end_date 컬럼을 nullable로 변경
SQLite는 ALTER COLUMN을 지원하지 않아 테이블 재생성 방식 사용
"""
import sqlite3
import os
import sys

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'momoai.db'))

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 현재 end_date 상태 확인
    cur.execute("PRAGMA table_info(teaching_materials)")
    cols = cur.fetchall()
    for col in cols:
        if col['name'] == 'end_date':
            print(f"현재 end_date: notnull={col['notnull']}")
            if col['notnull'] == 0:
                print("이미 nullable입니다. 마이그레이션 불필요.")
                conn.close()
                return

    print("teaching_materials 테이블 재생성 중...")

    cur.executescript("""
        BEGIN;

        CREATE TABLE teaching_materials_new (
            material_id VARCHAR(36) NOT NULL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            grade VARCHAR(20) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            storage_path VARCHAR(500) NOT NULL,
            file_size INTEGER NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            publish_date DATE NOT NULL,
            end_date DATE,
            is_public BOOLEAN NOT NULL,
            target_audience TEXT NOT NULL,
            download_count INTEGER NOT NULL,
            view_count INTEGER NOT NULL,
            created_at DATETIME NOT NULL,
            created_by VARCHAR(36) NOT NULL REFERENCES users(user_id)
        );

        INSERT INTO teaching_materials_new
        SELECT material_id, title, grade, original_filename, storage_path,
               file_size, file_type, publish_date, end_date, is_public,
               target_audience, download_count, view_count, created_at, created_by
        FROM teaching_materials;

        DROP TABLE teaching_materials;
        ALTER TABLE teaching_materials_new RENAME TO teaching_materials;

        CREATE INDEX IF NOT EXISTS ix_teaching_materials_grade ON teaching_materials(grade);
        CREATE INDEX IF NOT EXISTS ix_teaching_materials_publish_date ON teaching_materials(publish_date);
        CREATE INDEX IF NOT EXISTS ix_teaching_materials_end_date ON teaching_materials(end_date);
        CREATE INDEX IF NOT EXISTS ix_teaching_materials_is_public ON teaching_materials(is_public);
        CREATE INDEX IF NOT EXISTS ix_teaching_materials_created_at ON teaching_materials(created_at);

        COMMIT;
    """)

    conn.close()
    print("마이그레이션 완료: end_date를 nullable로 변경했습니다.")

if __name__ == '__main__':
    migrate()
