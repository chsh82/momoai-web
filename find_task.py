import database
from pathlib import Path

# 최근 HTML 파일명
html_filename = "김응_중등_20260205_215201.html"
html_path = str(Path("C:/Users/aproa/momoai_web/outputs/html") / html_filename)

# 데이터베이스에서 이 HTML 경로를 가진 task 찾기
import sqlite3
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

cursor.execute("SELECT task_id, student_name, grade, status, html_path, pdf_path FROM tasks ORDER BY created_at DESC LIMIT 10")
rows = cursor.fetchall()

print("Recent tasks:")
for row in rows:
    task_id, student_name, grade, status, html_path_db, pdf_path = row
    print(f"\nTask ID: {task_id}")
    print(f"  Student: {student_name} ({grade})")
    print(f"  Status: {status}")
    print(f"  HTML: {html_path_db}")
    print(f"  PDF: {pdf_path}")

conn.close()
