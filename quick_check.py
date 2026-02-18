#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
빠른 검증 스크립트
템플릿, 라우트, 데이터베이스 연결 등을 자동으로 확인합니다.
"""
import sys
import io
import os
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_templates():
    """템플릿 파일 존재 확인"""
    print("\n📄 템플릿 파일 확인...")

    required_templates = [
        'templates/base.html',
        'templates/auth/login.html',
        'templates/auth/register.html',
        'templates/dashboard/index.html',
        'templates/essays/index.html',
        'templates/essays/new.html',
        'templates/essays/detail.html',
        'templates/students/index.html',
        'templates/students/new.html',
        'templates/students/detail.html',
    ]

    missing = []
    for template in required_templates:
        if not Path(template).exists():
            missing.append(template)
            print(f"  ❌ {template}")
        else:
            print(f"  ✅ {template}")

    if missing:
        print(f"\n⚠️  {len(missing)}개의 템플릿 파일이 없습니다!")
        return False
    else:
        print(f"\n✅ 모든 템플릿 파일 존재 ({len(required_templates)}개)")
        return True

def check_jinja_syntax():
    """Jinja2 템플릿 구문 확인"""
    print("\n🔍 Jinja2 구문 확인...")

    from jinja2 import Environment, FileSystemLoader, TemplateError

    env = Environment(loader=FileSystemLoader('templates'))

    templates = [
        'base.html',
        'auth/login.html',
        'dashboard/index.html',
        'essays/index.html',
        'students/detail.html',
    ]

    errors = []
    for template_name in templates:
        try:
            env.get_template(template_name)
            print(f"  ✅ {template_name}")
        except TemplateError as e:
            errors.append((template_name, str(e)))
            print(f"  ❌ {template_name}: {e}")

    if errors:
        print(f"\n⚠️  {len(errors)}개의 템플릿에 구문 오류가 있습니다!")
        return False
    else:
        print(f"\n✅ 모든 템플릿 구문 정상 ({len(templates)}개)")
        return True

def check_database():
    """데이터베이스 연결 확인"""
    print("\n💾 데이터베이스 연결 확인...")

    from app import create_app
    from app.models import db, User, Student, Essay

    app = create_app()

    with app.app_context():
        try:
            # 간단한 쿼리로 연결 확인
            user_count = User.query.count()
            student_count = Student.query.count()
            essay_count = Essay.query.count()

            print(f"  ✅ 데이터베이스 연결 성공")
            print(f"  📊 사용자: {user_count}명")
            print(f"  📊 학생: {student_count}명")
            print(f"  📊 첨삭: {essay_count}건")
            return True
        except Exception as e:
            print(f"  ❌ 데이터베이스 오류: {e}")
            return False

def check_blueprints():
    """블루프린트 등록 확인"""
    print("\n🔗 블루프린트 등록 확인...")

    from app import create_app

    app = create_app()

    required_blueprints = ['auth', 'dashboard', 'essays', 'students']
    registered = [bp.name for bp in app.blueprints.values()]

    for bp_name in required_blueprints:
        if bp_name in registered:
            print(f"  ✅ {bp_name}")
        else:
            print(f"  ❌ {bp_name}")

    if all(bp in registered for bp in required_blueprints):
        print(f"\n✅ 모든 블루프린트 등록됨 ({len(required_blueprints)}개)")
        return True
    else:
        print(f"\n⚠️  일부 블루프린트가 등록되지 않았습니다!")
        return False

def check_jinja_globals():
    """Jinja2 글로벌 함수 확인"""
    print("\n🌍 Jinja2 글로벌 함수 확인...")

    from app import create_app

    app = create_app()

    required_globals = ['now']

    for global_name in required_globals:
        if global_name in app.jinja_env.globals:
            print(f"  ✅ {global_name}()")
        else:
            print(f"  ❌ {global_name}()")

    if all(g in app.jinja_env.globals for g in required_globals):
        print(f"\n✅ 모든 글로벌 함수 등록됨")
        return True
    else:
        print(f"\n⚠️  일부 글로벌 함수가 등록되지 않았습니다!")
        return False

def main():
    print("=" * 60)
    print("🔧 MOMOAI 빠른 검증 스크립트")
    print("=" * 60)

    checks = [
        ("템플릿 파일", check_templates),
        ("Jinja2 구문", check_jinja_syntax),
        ("데이터베이스", check_database),
        ("블루프린트", check_blueprints),
        ("Jinja2 글로벌", check_jinja_globals),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 확인 중 오류 발생: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("📋 검증 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{status}  {name}")

    print("\n" + "=" * 60)
    if passed == total:
        print(f"🎉 모든 검증 통과! ({passed}/{total})")
        print("=" * 60)
        print("\n✅ 서버를 실행해도 좋습니다: python run.py")
        return 0
    else:
        print(f"⚠️  일부 검증 실패 ({passed}/{total})")
        print("=" * 60)
        print("\n❌ 문제를 해결한 후 다시 시도하세요.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
