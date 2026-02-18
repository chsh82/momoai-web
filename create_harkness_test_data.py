"""하크니스 게시판 테스트를 위한 데이터 생성 스크립트"""
from app import create_app, db
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.models.student import Student
from datetime import datetime, timedelta, time
import uuid
import sys

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = create_app()

with app.app_context():
    print("=" * 60)
    print("하크니스 게시판 테스트 데이터 생성")
    print("=" * 60)

    # 1. 관리자 계정 확인
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        print("[경고] 관리자 계정이 없습니다.")
        exit()
    print(f"[OK] 관리자: {admin.name} ({admin.email})")

    # 2. 강사 계정 확인
    teachers = User.query.filter_by(role='teacher').all()
    if not teachers:
        print("[경고] 강사 계정이 없습니다. 먼저 강사를 생성해주세요.")
        exit()
    teacher = teachers[0]
    print(f"[OK] 강사: {teacher.name} ({teacher.email})")

    # 3. 학생 계정 확인
    students = Student.query.all()
    if len(students) < 5:
        print(f"[경고] 학생이 {len(students)}명만 있습니다. 최소 5명 필요합니다.")
        exit()
    print(f"[OK] 학생: {len(students)}명")

    # 4. 하크니스 수업 생성 (3개)
    print("\n하크니스 수업 생성 중...")

    courses_created = 0

    # 수업 1: 초등 하크니스
    course1 = Course(
        course_id=str(uuid.uuid4()),
        course_name="초등 하크니스 토론반",
        course_code="초등하250210",
        description="초등학생 대상 하크니스 토론 수업",
        grade="초등",
        course_type="harkness",
        teacher_id=teacher.user_id,
        schedule_type="weekly",
        weekday="월요일",
        start_time=time(15, 0),
        end_time=time(17, 30),
        duration_minutes=150,
        start_date=datetime.now().date(),
        end_date=(datetime.now() + timedelta(days=180)).date(),
        price_per_session=50000,
        total_sessions=20,
        status="active",
        makeup_class_allowed=True,
        created_by=admin.user_id
    )
    db.session.add(course1)
    courses_created += 1
    print(f"  [OK] {course1.course_name}")

    # 수업 2: 중등 하크니스
    course2 = Course(
        course_id=str(uuid.uuid4()),
        course_name="중등 하크니스 독서토론",
        course_code="중등하250210",
        description="중학생 대상 하크니스 독서토론 수업",
        grade="중등",
        course_type="harkness",
        teacher_id=teacher.user_id,
        schedule_type="weekly",
        weekday="수요일",
        start_time=time(16, 0),
        end_time=time(18, 30),
        duration_minutes=150,
        start_date=datetime.now().date(),
        end_date=(datetime.now() + timedelta(days=180)).date(),
        price_per_session=60000,
        total_sessions=20,
        status="active",
        makeup_class_allowed=True,
        created_by=admin.user_id
    )
    db.session.add(course2)
    courses_created += 1
    print(f"  [OK] {course2.course_name}")

    # 수업 3: 고등 하크니스
    course3 = Course(
        course_id=str(uuid.uuid4()),
        course_name="고등 하크니스 심화반",
        course_code="고등하250210",
        description="고등학생 대상 하크니스 심화토론",
        grade="고등",
        course_type="harkness",
        teacher_id=teacher.user_id,
        schedule_type="weekly",
        weekday="금요일",
        start_time=time(17, 0),
        end_time=time(19, 30),
        duration_minutes=150,
        start_date=datetime.now().date(),
        end_date=(datetime.now() + timedelta(days=180)).date(),
        price_per_session=70000,
        total_sessions=20,
        status="active",
        makeup_class_allowed=True,
        created_by=admin.user_id
    )
    db.session.add(course3)
    courses_created += 1
    print(f"  [OK] {course3.course_name}")

    db.session.commit()
    print(f"\n[OK] {courses_created}개 하크니스 수업 생성 완료")

    # 5. 학생 등록 (각 수업에 3명씩)
    print("\n학생 등록 중...")
    enrollments_created = 0

    for i, course in enumerate([course1, course2, course3]):
        # 각 수업에 3명씩 등록
        for j in range(3):
            student_idx = (i * 3 + j) % len(students)
            student = students[student_idx]

            enrollment = CourseEnrollment(
                enrollment_id=str(uuid.uuid4()),
                course_id=course.course_id,
                student_id=student.student_id,
                status='active'
            )
            db.session.add(enrollment)
            enrollments_created += 1
            print(f"  [OK] {course.course_name} - {student.name}")

    db.session.commit()
    print(f"\n[OK] {enrollments_created}명 학생 등록 완료")

    print("\n" + "=" * 60)
    print("테스트 데이터 생성 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("1. 브라우저에서 http://localhost:5000 접속")
    print("2. 관리자 또는 강사 계정으로 로그인")
    print("3. 사이드바에서 '💭 하크니스 게시판' 클릭")
    print("4. '게시판 생성' 버튼으로 새 게시판 만들기")
    print("   - 하크니스 전체 게시판 (모든 하크니스 학생)")
    print("   - 또는 수업별 게시판 (특정 수업 학생만)")
    print("5. 게시글 작성 및 댓글 테스트")
    print("=" * 60)
