"""Check 윤영기 teacher's schedule discrepancy"""
from app import create_app, db
from sqlalchemy import text
from datetime import date, timedelta

app = create_app()
with app.app_context():
    # 윤영기 강사 찾기
    r = db.session.execute(text("SELECT user_id, name FROM users WHERE name LIKE '%윤영기%'"))
    teacher = r.fetchone()
    if not teacher:
        print('강사를 찾을 수 없습니다.')
        exit()

    tid = teacher[0]
    print(f'강사: {teacher[1]} (id={tid})\n')

    wday = ['월', '화', '수', '목', '금', '토', '일']

    # 수업 목록 (수업관리 기준)
    r2 = db.session.execute(text(
        f"SELECT course_id, course_name, weekday, start_time, end_time, status, is_terminated "
        f"FROM courses WHERE teacher_id='{tid}' ORDER BY weekday, start_time"
    ))
    courses = r2.fetchall()
    print(f"=== 수업관리 수업 목록 ({len(courses)}개) ===")
    for c in courses:
        wd = wday[c[2]] if c[2] is not None else '미정'
        terminated = '(종료됨)' if c[6] else ''
        print(f"  [{wd}요일] {c[1]} | {c[3]}~{c[4]} | status={c[5]} {terminated} | id={c[0][:8]}..")

    print()

    # 이번 주 세션 목록 (수업현황 시간표 기준)
    today = date.today()
    weekday = today.weekday()
    week_start = today - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)

    course_ids = [c[0] for c in courses]
    ids_str = ",".join(f"'{cid}'" for cid in course_ids)

    print(f"=== 이번주 세션 ({week_start} ~ {week_end}) ===")
    if ids_str:
        r3 = db.session.execute(text(
            f"SELECT cs.session_id, cs.course_id, cs.session_date, cs.start_time, cs.end_time, cs.status, "
            f"c.course_name, c.weekday "
            f"FROM course_sessions cs JOIN courses c ON cs.course_id = c.course_id "
            f"WHERE cs.course_id IN ({ids_str}) "
            f"AND cs.session_date >= '{week_start}' AND cs.session_date <= '{week_end}' "
            f"ORDER BY cs.session_date, cs.start_time"
        ))
        sessions = r3.fetchall()
        print(f"세션 수: {len(sessions)}개")
        for s in sessions:
            session_wd = wday[s[2].weekday()] if s[2] else '?'
            course_wd = wday[s[7]] if s[7] is not None else '미정'
            mismatch = ' ⚠️ 요일 불일치!' if s[7] is not None and s[2].weekday() != s[7] else ''
            print(f"  [{session_wd}요일 {s[2]}] {s[6]} | {s[3]}~{s[4]} | status={s[5]}{mismatch}")
            print(f"    (수업 설정요일: {course_wd}요일, 세션날짜 요일: {session_wd}요일)")
    else:
        print("  수업 없음")

    print()

    # 전체 미래 예정 세션 중 요일 불일치 확인
    print("=== 미래 예정 세션 중 요일 불일치 ===")
    if ids_str:
        r4 = db.session.execute(text(
            f"SELECT cs.session_date, cs.start_time, c.course_name, c.weekday "
            f"FROM course_sessions cs JOIN courses c ON cs.course_id = c.course_id "
            f"WHERE cs.course_id IN ({ids_str}) "
            f"AND cs.status = 'scheduled' AND cs.session_date >= '{today}' "
            f"ORDER BY cs.session_date"
        ))
        all_future = r4.fetchall()
        mismatches = [(s[0], s[1], s[2], s[3]) for s in all_future if s[3] is not None and s[0].weekday() != s[3]]
        if mismatches:
            for m in mismatches:
                print(f"  ⚠️ {m[2]}: 세션날짜={m[0]}({wday[m[0].weekday()]}), 설정요일={wday[m[3]]}")
        else:
            print("  불일치 없음")
