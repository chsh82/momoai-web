# -*- coding: utf-8 -*-
"""Course 모델"""
from datetime import datetime, time
import uuid
from app.models import db


class Course(db.Model):
    """수업/강좌 모델"""
    __tablename__ = 'courses'

    course_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_name = db.Column(db.String(200), nullable=False)
    course_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # 학년
    grade = db.Column(db.String(50), nullable=True, index=True)

    # 수업 타입
    course_type = db.Column(db.String(50), nullable=True, index=True)  # 베이직, 프리미엄, 정규반, 하크니스, 체험단, 보강수업, 기타

    # 종료 여부
    is_terminated = db.Column(db.Boolean, default=False)

    # 등급/티어 (A, B, C 등)
    tier = db.Column(db.String(20), nullable=True, index=True)

    # 사용 여부 (사용, 대기, 불가)
    availability_status = db.Column(db.String(20), default='available', index=True)  # available, waiting, unavailable

    # 수업 정원
    max_students = db.Column(db.Integer, default=15)

    # 담당 강사
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                          nullable=True, index=True)

    # 스케줄 정보
    schedule_type = db.Column(db.String(20), default='weekly')  # weekly, custom
    weekday = db.Column(db.Integer, nullable=True)  # 0=월, 1=화, ..., 6=일
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    duration_minutes = db.Column(db.Integer, default=60)

    # 수업 기간
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    # 가격 정보
    price_per_session = db.Column(db.Integer, default=0)  # 회당 수업료
    total_sessions = db.Column(db.Integer, default=0)  # 총 수업 회차

    # 상태
    status = db.Column(db.String(20), default='active', index=True)  # active, completed, cancelled

    # 보강수업 신청 가능 여부
    makeup_class_allowed = db.Column(db.Boolean, default=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))

    # Relationships
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='teaching_courses')
    creator = db.relationship('User', foreign_keys=[created_by])
    enrollments = db.relationship('CourseEnrollment', back_populates='course',
                                 cascade='all, delete-orphan')
    sessions = db.relationship('CourseSession', back_populates='course',
                              cascade='all, delete-orphan',
                              order_by='CourseSession.session_number')

    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'

    def __init__(self, **kwargs):
        super(Course, self).__init__(**kwargs)
        if not self.course_id:
            self.course_id = str(uuid.uuid4())

    @property
    def enrolled_count(self):
        """현재 수강 중인 학생 수"""
        return len([e for e in self.enrollments if e.status == 'active'])

    @property
    def is_full(self):
        """정원 초과 여부"""
        return self.enrolled_count >= self.max_students

    @property
    def total_price(self):
        """총 수업료"""
        return self.price_per_session * self.total_sessions

    @property
    def completed_sessions(self):
        """완료된 세션 수"""
        return len([s for s in self.sessions if s.status == 'completed'])


class CourseEnrollment(db.Model):
    """수강 신청 모델 (학생-수업 연결)"""
    __tablename__ = 'course_enrollments'

    enrollment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 수강 상태
    status = db.Column(db.String(20), default='active', index=True)  # active, completed, dropped
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # 결제 정보
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid
    paid_sessions = db.Column(db.Integer, default=0)  # 결제 완료된 회차 수

    # 출석 통계
    attended_sessions = db.Column(db.Integer, default=0)
    absent_sessions = db.Column(db.Integer, default=0)
    late_sessions = db.Column(db.Integer, default=0)

    # Relationships
    course = db.relationship('Course', back_populates='enrollments')
    student = db.relationship('Student', backref='course_enrollments')
    payments = db.relationship('Payment', back_populates='enrollment',
                              cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Enrollment {self.student_id} in {self.course_id}>'

    def __init__(self, **kwargs):
        super(CourseEnrollment, self).__init__(**kwargs)
        if not self.enrollment_id:
            self.enrollment_id = str(uuid.uuid4())

    @property
    def attendance_rate(self):
        """출석률 계산"""
        total = self.attended_sessions + self.absent_sessions + self.late_sessions
        if total == 0:
            return 0
        return (self.attended_sessions / total) * 100

    @property
    def remaining_payment(self):
        """남은 미납 금액"""
        if not self.course:
            return 0
        total_amount = self.course.total_price
        paid_amount = self.paid_sessions * self.course.price_per_session
        return max(0, total_amount - paid_amount)


class CourseSession(db.Model):
    """수업 세션 모델 (개별 수업 회차)"""
    __tablename__ = 'course_sessions'

    session_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 세션 정보
    session_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3, ...
    session_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    # 수업 내용
    topic = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)

    # 상태
    status = db.Column(db.String(20), default='scheduled', index=True)  # scheduled, completed, cancelled

    # 출석 체크 정보
    attendance_checked = db.Column(db.Boolean, default=False)
    attendance_checked_at = db.Column(db.DateTime, nullable=True)
    attendance_checked_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', back_populates='sessions')
    attendance_records = db.relationship('Attendance', back_populates='session',
                                        cascade='all, delete-orphan')
    checker = db.relationship('User', foreign_keys=[attendance_checked_by])

    def __repr__(self):
        return f'<Session {self.session_number} of {self.course_id}>'

    def __init__(self, **kwargs):
        super(CourseSession, self).__init__(**kwargs)
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

    @property
    def attendance_count(self):
        """출석 학생 수"""
        return len([a for a in self.attendance_records if a.status == 'present'])

    @property
    def total_students(self):
        """총 수강 학생 수"""
        return len(self.attendance_records)

    @property
    def attendance_rate(self):
        """출석률"""
        if self.total_students == 0:
            return 0
        return (self.attendance_count / self.total_students) * 100
