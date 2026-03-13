import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('instance/momoai.db')
conn.text_factory = lambda b: b.decode('utf-8')
cur = conn.cursor()
wday = ['월', '화', '수', '목', '금', '토', '일']

# 전체 수업현황 (수업관리 기준)
cur.execute('SELECT course_id, course_name, weekday, start_time, end_time, status FROM courses ORDER BY weekday, start_time')
courses = cur.fetchall()
print(f'=== 수업관리 수업 목록 ({len(courses)}개) ===')
for c in courses:
    wd = wday[c[2]] if c[2] is not None else '?'
    print(f'  [{wd}요일] {c[1]} | {c[3]}~{c[4]} | status={c[5]}')

print()

# 전체 세션 현황
cur.execute('SELECT count(*) FROM course_sessions')
total = cur.fetchone()[0]
print(f'=== 전체 세션 수: {total}개 ===')

cur.execute("""
    SELECT cs.session_date, cs.start_time, cs.status, c.course_name, c.weekday, c.course_id
    FROM course_sessions cs
    JOIN courses c ON cs.course_id = c.course_id
    ORDER BY cs.session_date
""")
sessions = cur.fetchall()

mismatches = []
for s in sessions:
    from datetime import date as _date
    d = _date.fromisoformat(s[0][:10])
    session_wd = wday[d.weekday()]
    course_wd = wday[s[4]] if s[4] is not None else '?'
    if s[4] is not None and d.weekday() != s[4]:
        mismatches.append(s)
        flag = ' <-- 요일 불일치'
    else:
        flag = ''
    print(f'  {s[0][:10]}({session_wd}) | {s[3]} | {s[1]} | [{course_wd}설정]{flag}')

print()
print(f'=== 요일 불일치 세션: {len(mismatches)}개 ===')
for m in mismatches:
    from datetime import date as _date
    d = _date.fromisoformat(m[0][:10])
    print(f'  {m[3]}: 세션={m[0][:10]}({wday[d.weekday()]}), 설정={wday[m[4]]}')

conn.close()
