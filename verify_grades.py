# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import Student

app = create_app()
with app.app_context():
    # Check Kim MoMo
    momo = Student.query.filter_by(name='김모모').first()
    if momo:
        print(f'Kim MoMo (김모모) grade: {momo.grade}')
    else:
        print('Kim MoMo not found')

    # Grade distribution
    students = Student.query.all()
    grade_counts = {}
    for s in students:
        if s.grade:
            grade_counts[s.grade] = grade_counts.get(s.grade, 0) + 1

    print('\nGrade distribution:')
    grades_order = ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고1', '고2', '고3']
    for grade in grades_order:
        count = grade_counts.get(grade, 0)
        if count > 0:
            print(f'  {grade}: {count} students')

    # Check for any non-standard grades
    non_standard = [g for g in grade_counts.keys() if g not in grades_order]
    if non_standard:
        print('\nNon-standard grades found:')
        for g in non_standard:
            print(f'  {g}: {grade_counts[g]} students')

    print(f'\nTotal: {len(students)} students')
