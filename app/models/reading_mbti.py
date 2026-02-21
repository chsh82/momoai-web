# -*- coding: utf-8 -*-
"""독서 논술 MBTI 모델"""
from app.models import db
from datetime import datetime


class ReadingMBTITest(db.Model):
    """독서 논술 MBTI 테스트"""
    __tablename__ = 'reading_mbti_tests'

    test_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    version = db.Column(db.String(20), default='standard')  # 'standard' or 'elementary'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    questions = db.relationship('ReadingMBTIQuestion', backref='test', lazy='dynamic', cascade='all, delete-orphan')
    responses = db.relationship('ReadingMBTIResponse', backref='test', lazy='dynamic', cascade='all, delete-orphan')
    results = db.relationship('ReadingMBTIResult', backref='test', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ReadingMBTITest {self.title}>'


class ReadingMBTIQuestion(db.Model):
    """독서 논술 MBTI 질문"""
    __tablename__ = 'reading_mbti_questions'

    question_id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_tests.test_id'), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # 'absolute' or 'comparison'
    area = db.Column(db.String(20))  # 'read', 'speech', 'write'
    category = db.Column(db.String(20))  # 'vocab', 'reread', 'analyze', 'textual', 'expand', 'lead', 'summary', 'logic', 'rewrite'
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON)  # For comparison questions: [{value: 'vocab', text: '...'}]
    order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ReadingMBTIQuestion {self.question_id}>'


class ReadingMBTIType(db.Model):
    """독서 논술 MBTI 27가지 유형"""
    __tablename__ = 'reading_mbti_types'

    type_id = db.Column(db.Integer, primary_key=True)
    type_code = db.Column(db.String(20), unique=True, nullable=False)  # 'R1-S1-W1'
    type_key = db.Column(db.String(50), unique=True, nullable=False)  # 'vocab-textual-summary'
    type_name = db.Column(db.String(100), nullable=False)  # '정확성의 달인형'
    combo_description = db.Column(db.String(200))  # '어휘탐험가 × 교재토론러 × 핵심정리왕'
    full_description = db.Column(db.Text)

    # 각 영역별 설명
    reading_style = db.Column(db.Text)
    speaking_style = db.Column(db.Text)
    writing_style = db.Column(db.Text)

    # 강점/약점/팁 (JSON 배열)
    strengths = db.Column(db.JSON)  # ['강점1', '강점2', ...]
    weaknesses = db.Column(db.JSON)  # ['약점1', '약점2', ...]
    tips = db.Column(db.JSON)  # ['팁1', '팁2', ...]

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    results = db.relationship('ReadingMBTIResult', backref='mbti_type', lazy='dynamic')

    def __repr__(self):
        return f'<ReadingMBTIType {self.type_code}: {self.type_name}>'


class ReadingMBTIResponse(db.Model):
    """학생의 테스트 응답"""
    __tablename__ = 'reading_mbti_responses'

    response_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_tests.test_id'), nullable=False)

    # 응답 데이터 (JSON)
    responses = db.Column(db.JSON, nullable=False)  # {q1: 4, q2: 5, ..., comp1: 'vocab', ...}

    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='reading_mbti_responses')
    result = db.relationship('ReadingMBTIResult', backref='response', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ReadingMBTIResponse {self.response_id}: Student {self.student_id}>'


class ReadingMBTIResult(db.Model):
    """테스트 결과 및 분석"""
    __tablename__ = 'reading_mbti_results'

    result_id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_responses.response_id'), nullable=False, unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_tests.test_id'), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('reading_mbti_types.type_id'), nullable=False)

    # 점수 데이터 (JSON)
    scores = db.Column(db.JSON, nullable=False)  # {read: {vocab: 20, reread: 18, ...}, speech: {...}, write: {...}}

    # 결정된 유형
    read_type = db.Column(db.String(20), nullable=False)  # 'vocab', 'reread', 'analyze'
    speech_type = db.Column(db.String(20), nullable=False)  # 'textual', 'expand', 'lead'
    write_type = db.Column(db.String(20), nullable=False)  # 'summary', 'logic', 'rewrite'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='reading_mbti_results')

    @property
    def type_combination(self):
        """유형 조합 문자열"""
        return f"{self.read_type}-{self.speech_type}-{self.write_type}"

    @property
    def max_scores(self):
        """각 영역별 최고 점수"""
        return {
            'read': max(self.scores['read'].values()),
            'speech': max(self.scores['speech'].values()),
            'write': max(self.scores['write'].values())
        }

    @property
    def total_score(self):
        """전체 점수 합계"""
        total = 0
        for area in self.scores.values():
            total += sum(area.values())
        return total

    def __repr__(self):
        return f'<ReadingMBTIResult {self.result_id}: {self.type_combination}>'
