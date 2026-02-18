# -*- coding: utf-8 -*-
"""권한 레벨 마이그레이션 스크립트

기존:
- 1=master_admin, 2=manager, 3=teacher, 4=parent, 5=student

새로운:
- 1=master, 2=manager, 3=staff, 4=teacher, 5=parent, 6=student
"""
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    print("권한 레벨 마이그레이션 시작...")

    # 기존 데이터 업데이트
    # level 5 (student) → level 6
    students = User.query.filter_by(role_level=5).all()
    for user in students:
        user.role_level = 6
        print(f"  {user.name} ({user.role}): level 5 → 6")

    # level 4 (parent) → level 5
    parents = User.query.filter_by(role_level=4).all()
    for user in parents:
        user.role_level = 5
        print(f"  {user.name} ({user.role}): level 4 → 5")

    # level 3 (teacher) → level 4
    teachers = User.query.filter_by(role_level=3).all()
    for user in teachers:
        user.role_level = 4
        print(f"  {user.name} ({user.role}): level 3 → 4")

    # level 1, 2는 그대로 유지 (master, manager)

    db.session.commit()

    print("\n마이그레이션 완료!")
    print("\n현재 권한 레벨:")
    all_users = User.query.order_by(User.role_level).all()
    for user in all_users:
        level_name = {
            1: 'master',
            2: 'manager',
            3: 'staff',
            4: 'teacher',
            5: 'parent',
            6: 'student'
        }.get(user.role_level, 'unknown')
        print(f"  {user.name} ({user.role}): level {user.role_level} ({level_name})")
