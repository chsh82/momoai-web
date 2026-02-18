"""하크니스 수업에 학생 등록"""
from app import create_app, db
from app.models.course import Course, CourseEnrollment
from app.models.student import Student
import uuid
import sys

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = create_app()

with app.app_context():
    print("=" * 60)
    print("하크니스 수업 학생 등록")
    print("=" * 60)

    # 하크니스 수업 조회
    harkness_courses = Course.query.filter_by(course_type='harkness').all()
    print(f"\n[OK] 하크니스 수업: {len(harkness_courses)}개")
    for course in harkness_courses:
        print(f"  - {course.course_name}")

    # 학생 조회
    students = Student.query.limit(15).all()
    print(f"\n[OK] 등록할 학생: {len(students)}명")

    # 각 수업에 5명씩 등록
    print("\n학생 등록 중...")
    enrollments_created = 0

    for i, course in enumerate(harkness_courses):
        # 이미 등록된 학생 확인
        existing_enrollments = CourseEnrollment.query.filter_by(course_id=course.course_id).all()
        existing_student_ids = [e.student_id for e in existing_enrollments]

        print(f"\n{course.course_name} (기존: {len(existing_enrollments)}명)")

        # 각 수업에 5명씩 등록 (아직 등록 안 된 학생만)
        enrolled_count = 0
        for j in range(15):  # 최대 15명까지 시도
            student_idx = (i * 5 + j) % len(students)
            student = students[student_idx]

            # 이미 등록된 학생은 건너뛰기
            if student.student_id in existing_student_ids:
                continue

            enrollment = CourseEnrollment(
                enrollment_id=str(uuid.uuid4()),
                course_id=course.course_id,
                student_id=student.student_id,
                status='active'
            )
            db.session.add(enrollment)
            enrollments_created += 1
            enrolled_count += 1
            print(f"  [OK] {student.name}")

            if enrolled_count >= 5:
                break

    db.session.commit()
    print(f"\n[OK] {enrollments_created}명 학생 등록 완료")

    print("\n" + "=" * 60)
    print("등록 완료!")
    print("=" * 60)
    print("\n테스트 방법:")
    print("1. 브라우저에서 http://localhost:5000 접속")
    print("2. 관리자, 강사, 또는 학생 계정으로 로그인")
    print("3. 사이드바에서 '💭 하크니스 게시판' 클릭")
    print("4. 게시판 생성 -> 게시글 작성 -> 댓글 작성 테스트")
    print("=" * 60)
