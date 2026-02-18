"""스키마퀴즈 모델 (교과서 배경지식 및 전문용어)"""

from app import db
from datetime import datetime
import uuid


class SchemaQuiz(db.Model):
    """스키마퀴즈 문제 (사회/과학 배경지식)"""
    __tablename__ = 'schema_quizzes'

    quiz_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 용어 정보
    term = db.Column(db.String(200), nullable=False)  # 전문용어/개념
    definition = db.Column(db.Text, nullable=False)  # 정의/설명
    example = db.Column(db.Text)  # 예시 또는 추가 설명

    # 주제 분류
    subject = db.Column(db.String(50), nullable=False)  # 'social' (사회) or 'science' (과학)
    category = db.Column(db.String(100))  # 세부 카테고리 (예: 역사, 지리, 물리, 화학 등)

    # 학년
    grade_start = db.Column(db.String(10), nullable=False)  # 시작 학년
    grade_end = db.Column(db.String(10), nullable=False)  # 끝 학년

    # 퀴즈 타입
    quiz_type = db.Column(db.String(50), default='multiple_choice')  # multiple_choice, true_false, fill_in_blank

    # 객관식 선택지 (JSON 형태)
    options = db.Column(db.Text)  # JSON: ["선택지1", "선택지2", "선택지3", "선택지4"]
    correct_answer = db.Column(db.String(200), nullable=False)

    # 난이도
    difficulty = db.Column(db.String(20))  # easy, medium, hard

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))


class SchemaQuizResult(db.Model):
    """스키마퀴즈 결과"""
    __tablename__ = 'schema_quiz_results'

    result_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=False)
    quiz_id = db.Column(db.String(36), db.ForeignKey('schema_quizzes.quiz_id'), nullable=False)
    session_id = db.Column(db.String(36), db.ForeignKey('schema_quiz_sessions.session_id'))  # 세션 연결

    # 답안 정보
    student_answer = db.Column(db.String(200))
    is_correct = db.Column(db.Boolean, nullable=False)

    # 시간 정보
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_taken_seconds = db.Column(db.Integer)  # 소요 시간 (초)

    # 관계
    student = db.relationship('Student', backref=db.backref('schema_results', lazy='dynamic'))
    quiz = db.relationship('SchemaQuiz', backref=db.backref('results', lazy='dynamic'))
    session = db.relationship('SchemaQuizSession', backref=db.backref('results', lazy='dynamic'))


class SchemaQuizSession(db.Model):
    """스키마퀴즈 세션"""
    __tablename__ = 'schema_quiz_sessions'

    session_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=False)

    # 세션 정보
    subject = db.Column(db.String(50), nullable=False)  # 'social' or 'science'
    grade = db.Column(db.String(10), nullable=False)

    # 결과
    total_questions = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    score = db.Column(db.Float)  # 점수 (%)

    # 시간
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # 관계
    student = db.relationship('Student', backref=db.backref('schema_sessions', lazy='dynamic'))
