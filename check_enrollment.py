from app import create_app
from app.models import Student, CourseEnrollment, User
app = create_app()
with app.app_context():
    user = User.query.filter_by(email='gojane0311@gmail.com').first()
    print('user_id:', user.user_id if user else None)
    s = Student.query.filter_by(user_id=user.user_id).first() if user else None
    print('student:', s.student_id if s else None)
    if s:
        enrollments = CourseEnrollment.query.filter_by(student_id=s.student_id).all()
        for e in enrollments:
            print('course:', e.course_id, 'status:', e.status)
