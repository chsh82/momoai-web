import sqlite3
conn = sqlite3.connect('/home/chsh82/momoai_web/instance/momoai.db')
cur = conn.cursor()
cur.execute("SELECT student_id, name, email, user_id FROM students WHERE name LIKE '%\xc1\xa0%' OR name LIKE '%jane%' OR name LIKE '%Jane%'")
rows = cur.fetchall()
print('name search:', rows)

# 이메일로 찾기
cur.execute("SELECT user_id, name, email FROM users WHERE email='gojane0311@gmail.com'")
print('user by email:', cur.fetchall())

# 모든 student user
cur.execute("SELECT u.user_id, u.name, u.email, s.student_id, s.name FROM users u JOIN students s ON u.user_id=s.user_id WHERE u.role='student' LIMIT 20")
for row in cur.fetchall():
    print('student-user:', row)
conn.close()
