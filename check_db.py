import database

task_id = '05f14bec-5478-459a-b7a0-73b4d1db1201'
task = database.get_task(task_id)

if task:
    print(f"Task ID: {task['task_id']}")
    print(f"Student: {task['student_name']} ({task['grade']})")
    print(f"Status: {task['status']}")
    print(f"HTML Path: {task['html_path']}")
    print(f"PDF Path: {task['pdf_path']}")
else:
    print(f"Task {task_id} not found")
