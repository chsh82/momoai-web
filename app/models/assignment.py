# -*- coding: utf-8 -*-
"""Assignment 모델 (과제/숙제)"""
from datetime import datetime
import uuid
from app.models import db


class Assignment(db.Model):
    """과제 모델"""
    __tablename__ = 'assignments'

    assignment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 과제 기본 정보
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # 연결 정보
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=True, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    # 개별 학생 지정 (NULL이면 수업 전체 학생, 값이 있으면 해당 학생만)
    target_student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'),
                                  nullable=True, index=True)

    # 과제 설정
    assignment_type = db.Column(db.String(20), default='essay')  # essay, reading, quiz, project
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    max_score = db.Column(db.Integer, default=100)

    # 마감일
    due_date = db.Column(db.DateTime, nullable=False, index=True)
    late_submission_allowed = db.Column(db.Boolean, default=True)
    late_penalty_percent = db.Column(db.Integer, default=10)  # 지각 제출 시 감점 비율

    # 제출 방식
    submission_type = db.Column(db.String(20), default='text')  # text, file, both

    # 상태
    status = db.Column(db.String(20), default='active')  # active, closed, archived
    is_published = db.Column(db.Boolean, default=True)

    # 통계
    total_submissions = db.Column(db.Integer, default=0)
    graded_submissions = db.Column(db.Integer, default=0)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref='assignments')
    teacher = db.relationship('User', backref='created_assignments')
    target_student = db.relationship('Student', backref='targeted_assignments', foreign_keys=[target_student_id])
    submissions = db.relationship('AssignmentSubmission', back_populates='assignment',
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Assignment {self.assignment_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(Assignment, self).__init__(**kwargs)
        if not self.assignment_id:
            self.assignment_id = str(uuid.uuid4())

    @property
    def is_overdue(self):
        """마감일 경과 여부"""
        return datetime.utcnow() > self.due_date

    @property
    def days_until_due(self):
        """마감까지 남은 일수"""
        if self.is_overdue:
            return 0
        delta = self.due_date - datetime.utcnow()
        return delta.days

    @property
    def submission_rate(self):
        """제출률"""
        if not self.course:
            return 0
        total_students = len(self.course.enrollments)
        if total_students == 0:
            return 0
        return round(self.total_submissions / total_students * 100, 1)

    def get_submission_by_student(self, student_id):
        """특정 학생의 제출물 가져오기"""
        return AssignmentSubmission.query.filter_by(
            assignment_id=self.assignment_id,
            student_id=student_id
        ).first()


class AssignmentSubmission(db.Model):
    """과제 제출 모델"""
    __tablename__ = 'assignment_submissions'

    submission_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 연결 정보
    assignment_id = db.Column(db.String(36), db.ForeignKey('assignments.assignment_id', ondelete='CASCADE'),
                             nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 제출 내용
    content = db.Column(db.Text, nullable=True)  # 텍스트 제출
    file_path = db.Column(db.String(500), nullable=True)  # 파일 제출
    file_name = db.Column(db.String(200), nullable=True)

    # 제출 정보
    submitted_at = db.Column(db.DateTime, nullable=True, index=True)
    is_late = db.Column(db.Boolean, default=False)  # 지각 제출 여부

    # 채점 정보
    score = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                         nullable=True)

    # 상태
    status = db.Column(db.String(20), default='draft')  # draft, submitted, graded

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignment = db.relationship('Assignment', back_populates='submissions')
    student = db.relationship('Student', backref='assignment_submissions')
    grader = db.relationship('User', foreign_keys=[graded_by], backref='graded_assignments')

    def __repr__(self):
        return f'<AssignmentSubmission {self.submission_id}>'

    def __init__(self, **kwargs):
        super(AssignmentSubmission, self).__init__(**kwargs)
        if not self.submission_id:
            self.submission_id = str(uuid.uuid4())

    @property
    def is_submitted(self):
        """제출 여부"""
        return self.status in ['submitted', 'graded']

    @property
    def is_graded(self):
        """채점 완료 여부"""
        return self.status == 'graded'

    def submit(self):
        """제출 처리"""
        if not self.submitted_at:
            self.submitted_at = datetime.utcnow()
            # 지각 여부 확인
            if self.submitted_at > self.assignment.due_date:
                self.is_late = True
        self.status = 'submitted'

        # 과제 통계 업데이트
        if self.assignment:
            self.assignment.total_submissions = AssignmentSubmission.query.filter_by(
                assignment_id=self.assignment_id,
                status='submitted'
            ).count() + AssignmentSubmission.query.filter_by(
                assignment_id=self.assignment_id,
                status='graded'
            ).count()

    def grade(self, score, feedback, grader_id):
        """채점 처리"""
        self.score = score
        self.feedback = feedback
        self.graded_by = grader_id
        self.graded_at = datetime.utcnow()
        self.status = 'graded'

        # 과제 통계 업데이트
        if self.assignment:
            self.assignment.graded_submissions = AssignmentSubmission.query.filter_by(
                assignment_id=self.assignment_id,
                status='graded'
            ).count()

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'student_id', name='unique_assignment_submission'),
    )
