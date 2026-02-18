# -*- coding: utf-8 -*-
"""검색 라우트"""
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.search import search_bp
from app.models import db, Student, Course, User
from app.models.material import Material
from app.models.community import Post
from app.models.assignment import Assignment


@search_bp.route('/')
@login_required
def index():
    """통합 검색"""
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'all')

    if not query:
        return render_template('search/index.html',
                             query='',
                             category=category,
                             results={})

    results = {}

    # 학생 검색 (admin, teacher만)
    if current_user.role in ['admin', 'teacher'] and category in ['all', 'students']:
        students = Student.query.filter(
            or_(
                Student.name.contains(query),
                Student.email.contains(query),
                Student.grade.contains(query)
            )
        ).limit(10).all()
        results['students'] = students

    # 수업 검색
    if category in ['all', 'courses']:
        courses_query = Course.query.filter(
            or_(
                Course.course_name.contains(query),
                Course.description.contains(query)
            )
        )

        # 권한에 따라 필터링
        if current_user.role == 'teacher':
            courses_query = courses_query.filter_by(teacher_id=current_user.user_id)
        elif current_user.role == 'student':
            # 학생은 자신이 수강하는 수업만
            from app.models import CourseEnrollment
            student = Student.query.filter_by(email=current_user.email).first()
            if student:
                enrolled_course_ids = [e.course_id for e in student.enrollments if e.status == 'active']
                courses_query = courses_query.filter(Course.course_id.in_(enrolled_course_ids))

        courses = courses_query.limit(10).all()
        results['courses'] = courses

    # 학습 자료 검색
    if category in ['all', 'materials']:
        materials_query = Material.query.filter(
            or_(
                Material.title.contains(query),
                Material.description.contains(query),
                Material.tags.contains(query)
            ),
            Material.is_published == True
        )

        materials = materials_query.limit(10).all()

        # 접근 권한 필터링
        if current_user.role == 'student':
            student = Student.query.filter_by(email=current_user.email).first()
            if student:
                accessible_materials = [m for m in materials if m.can_access(current_user, student)]
                results['materials'] = accessible_materials
            else:
                results['materials'] = []
        else:
            results['materials'] = materials

    # 과제 검색
    if category in ['all', 'assignments']:
        assignments_query = Assignment.query.filter(
            or_(
                Assignment.title.contains(query),
                Assignment.description.contains(query)
            ),
            Assignment.is_published == True
        )

        # 권한에 따라 필터링
        if current_user.role == 'teacher':
            assignments_query = assignments_query.filter_by(teacher_id=current_user.user_id)
        elif current_user.role == 'student':
            # 학생은 자신이 수강하는 수업의 과제만
            student = Student.query.filter_by(email=current_user.email).first()
            if student:
                enrolled_course_ids = [e.course_id for e in student.enrollments if e.status == 'active']
                assignments_query = assignments_query.filter(
                    or_(
                        Assignment.course_id.in_(enrolled_course_ids),
                        Assignment.course_id == None
                    )
                )

        assignments = assignments_query.limit(10).all()
        results['assignments'] = assignments

    # 게시글 검색
    if category in ['all', 'posts']:
        posts = Post.query.filter(
            or_(
                Post.title.contains(query),
                Post.content.contains(query)
            )
        ).order_by(Post.created_at.desc()).limit(10).all()
        results['posts'] = posts

    # 사용자 검색 (admin만)
    if current_user.role == 'admin' and category in ['all', 'users']:
        users = User.query.filter(
            or_(
                User.name.contains(query),
                User.email.contains(query)
            )
        ).limit(10).all()
        results['users'] = users

    return render_template('search/index.html',
                         query=query,
                         category=category,
                         results=results)


@search_bp.route('/api/autocomplete')
@login_required
def autocomplete():
    """자동완성 API"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'suggestions': []})

    suggestions = []

    # 학생 이름
    if current_user.role in ['admin', 'teacher']:
        students = Student.query.filter(Student.name.contains(query)).limit(5).all()
        for student in students:
            suggestions.append({
                'type': 'student',
                'text': student.name,
                'subtitle': student.grade
            })

    # 수업명
    courses_query = Course.query.filter(Course.course_name.contains(query))
    if current_user.role == 'teacher':
        courses_query = courses_query.filter_by(teacher_id=current_user.user_id)
    courses = courses_query.limit(5).all()
    for course in courses:
        suggestions.append({
            'type': 'course',
            'text': course.course_name,
            'subtitle': f'{course.teacher.name} 강사'
        })

    # 자료명
    materials = Material.query.filter(
        Material.title.contains(query),
        Material.is_published == True
    ).limit(5).all()
    for material in materials:
        suggestions.append({
            'type': 'material',
            'text': material.title,
            'subtitle': material.category_display if hasattr(material, 'category_display') else ''
        })

    return jsonify({'suggestions': suggestions})
