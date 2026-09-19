# -*- coding: utf-8 -*-
"""명예의 전당 지도교사 표시 점검 (읽기 전용 - 아무 것도 수정하지 않음).

Student.main_teacher(app/models/student.py)가 실제로 무엇을 보여줄지 전체 학생
기준으로 점검한다. teacher_id는 그대로 두고(접근 권한 필드라 안 건드림), "정규 수업
기준 현재 담당 강사"로 대체 표시가 안 되는 경우(= 여전히 마스터/매니저 관리자 이름이
보이는 경우)를 찾아 수동 확인이 필요한 목록으로 보여준다.

실행: python scripts/check_hof_teacher_display.py
"""
import sys
import logging

sys.path.insert(0, '.')
logging.disable(logging.CRITICAL)

from app import create_app, db  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.library import HallOfFame  # noqa: E402


def main():
    app = create_app()
    with app.app_context():
        students = Student.query.filter_by(is_temp=False).order_by(Student.name).all()

        still_admin = []
        resolved = []
        no_teacher = []

        for s in students:
            mt = s.main_teacher
            if not mt:
                no_teacher.append(s)
            elif mt.role_level <= 2:
                still_admin.append((s, mt))
            elif s.teacher_id != mt.user_id:
                resolved.append((s, mt))

        print(f"전체 학생(임시 제외): {len(students)}명\n")

        print(f"[자동으로 정규 수업 담당 강사로 대체 표시됨] {len(resolved)}명")
        for s, mt in resolved:
            print(f"  - {s.name}({s.student_id}) : teacher_id는 관리자({s.teacher.name})지만 "
                  f"화면에는 '{mt.name}'로 표시됨")

        print(f"\n[여전히 마스터/매니저 관리자 이름이 표시됨 - 수동 확인 필요] {len(still_admin)}명")
        for s, mt in still_admin:
            hof_count = HallOfFame.query.filter_by(student_id=s.student_id, is_published=True).count()
            print(f"  - {s.name}({s.student_id}) : 표시명='{mt.name}' "
                  f"(teacher_id={s.teacher_id}) / 명예의 전당 게시글 {hof_count}건"
                  + ("  <- 실제로 화면에 노출됨, 확인 필요" if hof_count else ""))
            print("      원인: 이 학생의 현재 수강 중(active)이고 종료되지 않은 '정규'(보강수업 아님) "
                  "수업 등록을 찾지 못함 - 수강 등록이 없거나, 있는 수업이 전부 보강수업이거나, "
                  "수업 담당 강사가 비어있거나 역시 관리자 계정으로 설정됨.")

        print(f"\n[teacher_id 자체가 없음] {len(no_teacher)}명")
        for s in no_teacher:
            print(f"  - {s.name}({s.student_id})")

        print("\n이 스크립트는 아무 것도 수정하지 않았습니다. "
              "'수동 확인 필요' 목록은 해당 학생의 수강 등록(course_enrollments)을 "
              "직접 확인해 정규 수업 등록을 정리하면 다음 조회부터 자동으로 반영됩니다.")


if __name__ == '__main__':
    main()
