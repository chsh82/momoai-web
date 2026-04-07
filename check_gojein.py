import sqlite3
conn = sqlite3.connect('/home/chsh82/momoai_web/instance/momoai.db')
cur = conn.cursor()

student_id = '26a5174c-7eb3-46f9-bc75-8d2637a1f319'

# enrollment 확인
cur.execute("SELECT enrollment_id, course_id, status FROM course_enrollments WHERE student_id=?", (student_id,))
enrollments = cur.fetchall()
print('Enrollments:', enrollments)

for enrollment_id, course_id, status in enrollments:
    cur.execute("SELECT course_name, is_terminated FROM courses WHERE course_id=?", (course_id,))
    course = cur.fetchone()
    print('  Course:', course, 'status:', status)

# 출석 확인
from datetime import datetime, timedelta
start_date = (datetime.utcnow() - timedelta(days=28)).strftime('%Y-%m-%d')
cur.execute("SELECT count(*) FROM attendance WHERE student_id=?", (student_id,))
print('Total attendance:', cur.fetchone())
cur.execute("SELECT count(*) FROM attendance WHERE student_id=? AND created_at>=?", (student_id, start_date))
print('Recent attendance (4w):', cur.fetchone())

conn.close()
