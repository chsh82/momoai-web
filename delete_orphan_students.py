"""
Orphan student deletion script using direct SQL to avoid ORM cascade issues.
Run on production: python3 delete_orphan_students.py
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Show what will be deleted
    result = db.session.execute(text("SELECT student_id, name, is_temp, user_id FROM students WHERE is_temp=1 OR (is_temp=0 AND user_id IS NULL)"))
    rows = result.fetchall()
    print(f"삭제 대상 학생 {len(rows)}명:")
    for r in rows:
        print(f"  - {r[1]} (id={r[0]}, is_temp={r[2]}, user_id={r[3]})")

    if not rows:
        print("삭제 대상 없음.")
    else:
        # Get student IDs to delete
        student_ids = [r[0] for r in rows]
        ids_str = ",".join(f"'{sid}'" for sid in student_ids)

        # Delete related records first (using IF EXISTS style with try/except per table)
        for tbl in ['course_enrollments', 'essays', 'essay_notes', 'essay_versions',
                    'essay_results', 'essay_scores', 'essay_books', 'essay_books',
                    'parent_student', 'makeup_class_requests', 'attendance',
                    'notifications', 'correction_attachments']:
            try:
                db.session.execute(text(f"DELETE FROM {tbl} WHERE student_id IN ({ids_str})"))
            except Exception as e:
                if 'no such column' not in str(e) and 'no such table' not in str(e):
                    raise

        # Now delete the students
        db.session.execute(text(f"DELETE FROM students WHERE student_id IN ({ids_str})"))
        db.session.commit()
        print(f"\n완료: {len(rows)}명 삭제됨")
