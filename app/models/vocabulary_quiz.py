"""어휘퀴즈 모델"""

from app import db
from datetime import datetime
import uuid


class VocabularyQuiz(db.Model):
    """어휘퀴즈 문제"""
    __tablename__ = 'vocabulary_quizzes'

    quiz_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 어휘 정보
    word = db.Column(db.String(100), nullable=False)  # 어휘
    meaning = db.Column(db.Text, nullable=False)  # 뜻
    example = db.Column(db.Text)  # 예문

    # 레벨 및 학년
    level = db.Column(db.Integer, nullable=False)  # 1~6 레벨
    grade_start = db.Column(db.String(10), nullable=False)  # 시작 학년 (예: 초1)
    grade_end = db.Column(db.String(10), nullable=False)  # 끝 학년 (예: 초2)

    # 퀴즈 타입
    quiz_type = db.Column(db.String(50), default='multiple_choice')  # multiple_choice, fill_in_blank

    # 객관식 선택지 (JSON 형태)
    options = db.Column(db.Text)  # JSON: ["선택지1", "선택지2", "선택지3", "선택지4"]
    correct_answer = db.Column(db.String(200), nullable=False)

    # 메타 정보
    category = db.Column(db.String(50), default='학습도구어')  # 카테고리
    difficulty = db.Column(db.String(20))  # easy, medium, hard

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))


class VocabularyQuizResult(db.Model):
    """어휘퀴즈 결과"""
    __tablename__ = 'vocabulary_quiz_results'

    result_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=False)
    quiz_id = db.Column(db.String(36), db.ForeignKey('vocabulary_quizzes.quiz_id'), nullable=False)

    # 답안 정보
    student_answer = db.Column(db.String(200))
    is_correct = db.Column(db.Boolean, nullable=False)

    # 시간 정보
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_taken_seconds = db.Column(db.Integer)  # 소요 시간 (초)

    # 관계
    student = db.relationship('Student', backref=db.backref('vocabulary_results', lazy='dynamic'))
    quiz = db.relationship('VocabularyQuiz', backref=db.backref('results', lazy='dynamic'))


class VocabularyQuizSession(db.Model):
    """어휘퀴즈 세션 (학생이 특정 레벨/학년 퀴즈를 풀 때)"""
    __tablename__ = 'vocabulary_quiz_sessions'

    session_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=False)

    # 세션 정보
    level = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(10), nullable=False)

    # 결과
    total_questions = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    score = db.Column(db.Float)  # 점수 (%)

    # 시간
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    # 관계
    student = db.relationship('Student', backref=db.backref('vocabulary_sessions', lazy='dynamic'))
