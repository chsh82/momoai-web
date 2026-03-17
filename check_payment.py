import sqlite3
conn = sqlite3.connect("/home/chsh82/momoai_web/instance/momoai.db")
cur = conn.cursor()

parent_id = '2242f9f5-b8a0-42b9-992e-72d3fcc55259'

# index() 로직 그대로 재현
cur.execute("SELECT ps.student_id FROM parent_student ps WHERE ps.parent_id=? AND ps.is_active=1", (parent_id,))
child_ids = [r[0] for r in cur.fetchall()]
print("자녀 student_id 목록:", child_ids)

total_unpaid = 0
for sid in child_ids:
    cur.execute("SELECT enrollment_id FROM course_enrollments WHERE student_id=? AND status='active'", (sid,))
    enrollment_ids = [r[0] for r in cur.fetchall()]
    print(f"\nstudent_id={sid}, active enrollment_ids: {enrollment_ids}")
    if enrollment_ids:
        placeholders = ','.join('?' * len(enrollment_ids))
        cur.execute(f"SELECT SUM(amount) FROM payments WHERE enrollment_id IN ({placeholders}) AND status='pending'", enrollment_ids)
        pending_sum = cur.fetchone()[0] or 0
        print(f"  pending payment 합계: {pending_sum}")
        total_unpaid += pending_sum

print(f"\n최종 total_unpaid: {total_unpaid}")

# 혹시 모든 payment 확인 (status 무관)
print("\n강지영 자녀 전체 payment 레코드:")
for sid in child_ids:
    cur.execute("SELECT p.payment_id, p.amount, p.status, p.payment_type, p.enrollment_id, p.student_id FROM payments p WHERE p.student_id=? OR p.enrollment_id IN (SELECT enrollment_id FROM course_enrollments WHERE student_id=?)", (sid, sid))
    rows = cur.fetchall()
    print(f"  student {sid}: {rows}")

conn.close()
