# -*- coding: utf-8 -*-
"""대시보드 통계 확인 스크립트"""
from app import create_app, db
from app.models import User, Student, Course, CourseEnrollment, Payment
from app.models.essay import Essay

app = create_app()

with app.app_context():
    print("="*60)
    print("MOMOAI 시스템 통계")
    print("="*60)

    # 통계 데이터
    total_courses_active = Course.query.filter_by(status='active').count()
    total_courses_all = Course.query.count()
    total_students = Student.query.count()
    total_teachers = User.query.filter_by(role='teacher').count()
    total_parents = User.query.filter_by(role='parent').count()
    total_admins = User.query.filter_by(role='admin').count()
    total_essays = Essay.query.count()
    total_enrollments_active = CourseEnrollment.query.filter_by(status='active').count()
    total_enrollments_all = CourseEnrollment.query.count()
    total_payments = Payment.query.count()

    print(f"\n[수업 현황]")
    print(f"  - 진행 중인 수업: {total_courses_active}개")
    print(f"  - 전체 수업: {total_courses_all}개")

    print(f"\n[사용자 현황]")
    print(f"  - 전체 학생: {total_students}명")
    print(f"  - 전체 강사: {total_teachers}명")
    print(f"  - 전체 학부모: {total_parents}명")
    print(f"  - 전체 관리자: {total_admins}명")

    print(f"\n[첨삭 현황]")
    print(f"  - 전체 첨삭: {total_essays}개")

    essays_by_status = db.session.query(
        Essay.status,
        db.func.count(Essay.essay_id)
    ).group_by(Essay.status).all()

    for status, count in essays_by_status:
        print(f"    - {status}: {count}개")

    print(f"\n[수강 신청]")
    print(f"  - 활성 수강 신청: {total_enrollments_active}개")
    print(f"  - 전체 수강 신청: {total_enrollments_all}개")

    print(f"\n[결제 현황]")
    print(f"  - 전체 결제: {total_payments}개")

    if total_payments > 0:
        total_amount = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
        print(f"  - 총 결제 금액: {total_amount:,}원")

    print(f"\n[최근 활동]")
    recent_essays = Essay.query.order_by(Essay.created_at.desc()).limit(3).all()
    if recent_essays:
        print("  최근 첨삭 3개:")
        for essay in recent_essays:
            print(f"    - {essay.student.name} / {essay.user.name} / {essay.status} / {essay.created_at.strftime('%m/%d %H:%M')}")
    else:
        print("  최근 첨삭: 없음")

    recent_enrollments = CourseEnrollment.query.order_by(CourseEnrollment.enrolled_at.desc()).limit(3).all()
    if recent_enrollments:
        print("\n  최근 수강 신청 3개:")
        for enrollment in recent_enrollments:
            print(f"    - {enrollment.student.name} → {enrollment.course.course_name} / {enrollment.enrolled_at.strftime('%m/%d %H:%M')}")
    else:
        print("\n  최근 수강 신청: 없음")

    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(3).all()
    if recent_payments:
        print("\n  최근 결제 3개:")
        for payment in recent_payments:
            print(f"    - {payment.student.name} / {payment.amount:,}원 / {payment.created_at.strftime('%m/%d %H:%M')}")
    else:
        print("\n  최근 결제: 없음")

    print("\n" + "="*60)
