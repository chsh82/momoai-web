# -*- coding: utf-8 -*-
"""헤르메스 명령의 자연어 필드(학생 이름, 수업 힌트, 날짜)를 실제 DB 엔티티로
해석하는 순수 로직. LLM은 여기에 관여하지 않는다 - 전부 결정적 쿼리/비교다.

0건/여러 건이면 (None, candidates)를 반환해 호출부가 명확화 질문으로
돌리게 한다. 절대 추측해서 하나를 임의로 고르지 않는다."""
from app.models import CourseEnrollment, CourseSession, User
from app.utils.student_lookup import search_students_by_name


def resolve_teacher(name_hint):
    """(teacher_or_none, candidates) 반환 - 보강을 다른 강사에게 맡기는 지시용
    ("최성호 강사와 보강" 등). name_hint가 없으면 (None, [])로 '지정 안 함'을
    나타낸다(원 수업 강사 그대로 쓰라는 뜻 - 호출부가 구분해서 처리)."""
    if not name_hint:
        return None, []
    matches = User.query.filter(
        User.role == 'teacher', User.is_active == True,
        User.name.ilike(f'%{name_hint}%'),
    ).limit(10).all()
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def resolve_student(name_hint):
    """(student_or_none, candidates) 반환. candidates는 0건 또는 2건 이상일 때만 채워진다."""
    if not name_hint:
        return None, []
    matches = search_students_by_name(name_hint, limit=10)
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def resolve_course_for_student(student, course_hint=None):
    """학생의 활성 수강 수업 중 course_hint로 좁혀 하나를 찾는다.
    (course_or_none, candidates) 반환.

    기본적으로 보강(course_type이 '보강'으로 시작) 수업은 후보에서 제외한다 -
    헤르메스 지시("결석 처리", "보강 잡아줘")는 거의 항상 학생의 원래 정규
    수업을 가리키는데, 보강 수업 이름은 항상 원 수업 이름을 포함하는 형태라서
    (예: "[보강] 국어정규반 - 김민준") 제외하지 않으면 보강을 한 번이라도
    받은 학생은 영원히 "수업이 여러 개" 모호함에 걸린다. 정규 수업이 하나도
    없는 예외 상황(보강만 남아있는 경우)에서만 보강 수업도 후보로 돌아온다."""
    enrollments = CourseEnrollment.query.filter_by(
        student_id=student.student_id, status='active',
    ).all()
    courses = [e.course for e in enrollments if e.course]
    regular_courses = [c for c in courses if not (c.course_type or '').startswith('보강')]
    if regular_courses:
        courses = regular_courses
    if not courses:
        return None, []
    if course_hint:
        narrowed = [c for c in courses if course_hint in (c.course_name or '')]
        if len(narrowed) == 1:
            return narrowed[0], []
        if narrowed:
            return None, narrowed
    if len(courses) == 1:
        return courses[0], []
    return None, courses


def resolve_session_for_date(course, target_date):
    """해당 수업의 특정 날짜 세션을 찾는다. 없으면 None."""
    if not course or not target_date:
        return None
    return CourseSession.query.filter_by(
        course_id=course.course_id, session_date=target_date,
    ).first()
