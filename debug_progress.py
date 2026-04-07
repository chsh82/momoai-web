import sqlite3
conn = sqlite3.connect('/home/chsh82/momoai_web/instance/momoai.db')
cur = conn.cursor()

# 첫 번째 active enrollment 가진 학생 찾기
cur.execute("""
    SELECT s.student_id, s.name, ce.enrollment_id, ce.status, c.course_name, c.is_terminated
    FROM students s
    JOIN course_enrollments ce ON s.student_id = ce.student_id
    JOIN courses c ON ce.course_id = c.course_id
    WHERE ce.status = 'active' AND c.is_terminated = 0
    LIMIT 3
""")
rows = cur.fetchall()
print("Active enrolled students:")
for row in rows:
    print(" ", row)

# 첫 번째 학생으로 직접 ProgressTracker 테스트
if rows:
    student_id = rows[0][0]
    print(f"\nTesting student_id: {student_id}")

    # course_progress 쿼리 재현
    cur.execute("""
        SELECT ce.enrollment_id, c.course_name, c.total_sessions, ce.attended_sessions
        FROM course_enrollments ce
        JOIN courses c ON ce.course_id = c.course_id
        WHERE ce.student_id = ? AND ce.status = 'active' AND c.is_terminated = 0
    """, (student_id,))
    cp = cur.fetchall()
    print("course_progress rows:", cp)

    # weekly activity 쿼리 재현
    from datetime import datetime, timedelta, date
    start_date = (date.today() - timedelta(days=28)).isoformat()
    cur.execute("""
        SELECT strftime('%Y-%W', cs.session_date) as week, count(a.attendance_id)
        FROM attendance a
        JOIN course_sessions cs ON a.session_id = cs.session_id
        WHERE a.student_id = ? AND cs.session_date >= ? AND a.status IN ('present','late')
        GROUP BY week
    """, (student_id, start_date))
    wa = cur.fetchall()
    print("weekly_activity rows:", wa)

conn.close()
