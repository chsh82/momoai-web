# -*- coding: utf-8 -*-
"""학생 이름 검색 공용 헬퍼 - app/admin/routes.py의 search_students API와
app/utils/hermes_resolver.py(헤르메스 학생 조회)가 같은 쿼리를 쓰도록 분리."""
from app.models import Student


def search_students_by_name(name, grade=None, limit=20):
    """이름(부분일치)/학년으로 학생을 찾는다. Student ORM 객체 리스트 반환.

    Student.name은 유니크가 아니므로(app/models/student.py) 0건/1건/여러 건
    전부 호출부가 처리해야 한다."""
    query = Student.query.filter_by(is_temp=False)
    if grade:
        query = query.filter_by(grade=grade)
    if name:
        query = query.filter(Student.name.ilike(f'%{name}%'))
    return query.order_by(Student.name).limit(limit).all()
