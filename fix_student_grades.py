# -*- coding: utf-8 -*-
"""학생 학년 정보 세부화"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Student

def fix_student_grades():
    """학년 정보를 초등/중등/고등에서 구체적인 학년으로 변경"""
    app = create_app()

    with app.app_context():
        try:
            updated_count = 0

            # 1. 김모모를 중2로 변경
            momo = Student.query.filter_by(name='김모모').first()
            if momo:
                print(f"[UPDATE] {momo.name}: {momo.grade} -> 중2")
                momo.grade = '중2'
                updated_count += 1

            # 2. 초등 -> 초1~초6 중 랜덤
            elementary = Student.query.filter_by(grade='초등').all()
            elementary_grades = ['초1', '초2', '초3', '초4', '초5', '초6']
            for student in elementary:
                new_grade = random.choice(elementary_grades)
                print(f"[UPDATE] {student.name}: {student.grade} -> {new_grade}")
                student.grade = new_grade
                updated_count += 1

            # 3. 중등 -> 중1~중3 중 랜덤 (김모모 제외)
            middle = Student.query.filter(Student.grade == '중등', Student.name != '김모모').all()
            middle_grades = ['중1', '중2', '중3']
            for student in middle:
                new_grade = random.choice(middle_grades)
                print(f"[UPDATE] {student.name}: {student.grade} -> {new_grade}")
                student.grade = new_grade
                updated_count += 1

            # 4. 고등 -> 고1~고3 중 랜덤
            high = Student.query.filter_by(grade='고등').all()
            high_grades = ['고1', '고2', '고3']
            for student in high:
                new_grade = random.choice(high_grades)
                print(f"[UPDATE] {student.name}: {student.grade} -> {new_grade}")
                student.grade = new_grade
                updated_count += 1

            db.session.commit()

            print(f"\n[OK] Successfully updated {updated_count} students' grades")

            # 최종 학년 분포 확인
            print("\nFinal grade distribution:")
            students = Student.query.all()
            grade_counts = {}
            for s in students:
                grade_counts[s.grade] = grade_counts.get(s.grade, 0) + 1

            for grade in ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고1', '고2', '고3']:
                count = grade_counts.get(grade, 0)
                print(f"  {grade}: {count}")

        except Exception as e:
            print(f"[ERROR] {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    fix_student_grades()
