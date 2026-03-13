"""
Fix CourseSession dates that don't match their Course.weekday setting.
Run: python3 fix_session_weekdays.py [--dry-run] [--teacher-name NAME]

--dry-run: show what would be changed without making changes
--teacher-name: filter to specific teacher (partial name match)
"""
import sys
from app import create_app, db
from sqlalchemy import text
from datetime import date, timedelta

dry_run = '--dry-run' in sys.argv
teacher_filter = None
for i, arg in enumerate(sys.argv):
    if arg == '--teacher-name' and i + 1 < len(sys.argv):
        teacher_filter = sys.argv[i + 1]

app = create_app()
wday = ['월', '화', '수', '목', '금', '토', '일']

with app.app_context():
    # 강사 목록 (필터 적용)
    if teacher_filter:
        teachers_q = db.session.execute(text(
            f"SELECT user_id, name FROM users WHERE role='teacher' AND name LIKE '%{teacher_filter}%'"
        ))
    else:
        teachers_q = db.session.execute(text(
            "SELECT user_id, name FROM users WHERE role='teacher'"
        ))
    teachers = teachers_q.fetchall()

    if not teachers:
        print('강사를 찾을 수 없습니다.')
        exit()

    total_fixed = 0

    for teacher in teachers:
        tid, tname = teacher[0], teacher[1]
        print(f'\n강사: {tname}')

        # 해당 강사의 수업
        courses_q = db.session.execute(text(
            f"SELECT course_id, course_name, weekday FROM courses "
            f"WHERE teacher_id='{tid}' AND weekday IS NOT NULL "
            f"ORDER BY weekday"
        ))
        courses = courses_q.fetchall()

        for course in courses:
            cid, cname, course_weekday = course[0], course[1], course[2]

            # 이 수업의 scheduled 세션 중 요일이 맞지 않는 것 찾기
            sessions_q = db.session.execute(text(
                f"SELECT session_id, session_date FROM course_sessions "
                f"WHERE course_id='{cid}' AND status='scheduled' "
                f"ORDER BY session_date"
            ))
            sessions = sessions_q.fetchall()

            mismatches = []
            for s in sessions:
                sid = s[0]
                sdate = date.fromisoformat(s[1][:10])
                if sdate.weekday() != course_weekday:
                    # 같은 주의 올바른 요일로 이동
                    day_shift = course_weekday - sdate.weekday()
                    new_date = sdate + timedelta(days=day_shift)
                    mismatches.append((sid, sdate, new_date))

            if mismatches:
                print(f'  [{wday[course_weekday]}요일] {cname} - 불일치 {len(mismatches)}개:')
                for sid, old_date, new_date in mismatches:
                    old_wd = wday[old_date.weekday()]
                    new_wd = wday[new_date.weekday()]
                    print(f'    {old_date}({old_wd}) → {new_date}({new_wd})')
                    if not dry_run:
                        db.session.execute(text(
                            f"UPDATE course_sessions SET session_date='{new_date}' "
                            f"WHERE session_id='{sid}'"
                        ))
                total_fixed += len(mismatches)
            else:
                print(f'  [{wday[course_weekday]}요일] {cname} - 정상')

    if dry_run:
        print(f'\n[DRY RUN] 수정 대상: {total_fixed}개 세션')
        db.session.rollback()
    else:
        if total_fixed > 0:
            db.session.commit()
            print(f'\n완료: {total_fixed}개 세션 날짜 수정됨')
        else:
            print('\n수정할 항목 없음')
