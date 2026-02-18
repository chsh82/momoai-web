# -*- coding: utf-8 -*-
"""ACE 평가 시스템 모델"""
from datetime import datetime
from app.models import db
import json


class WeeklyEvaluation(db.Model):
    """주차 평가 모델 (주간 첨삭 피드백)"""
    __tablename__ = 'weekly_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 평가 정보
    eval_date = db.Column(db.Date, nullable=False, index=True)
    week_number = db.Column(db.Integer, nullable=False)  # 주차 (1, 2, 3...)
    book_title = db.Column(db.String(200), nullable=True)  # 수업 도서
    class_type = db.Column(db.String(50), nullable=True)  # 1:1, 일반 그룹, 하크니스

    # 점수 및 등급
    score = db.Column(db.Integer, nullable=False)  # 0-100점
    grade = db.Column(db.String(5), nullable=False)  # A+, A0, A-, B+, B0, B-, C+, C0, C-, D+, D0, D-, E, F

    # 별점 평가 (1-5점)
    participation_score = db.Column(db.Integer, default=3, nullable=False)  # 참여도 (기본 3점)
    understanding_score = db.Column(db.Integer, default=3, nullable=False)  # 이해도 (기본 3점)

    # 코멘트
    comment = db.Column(db.Text, nullable=True)

    # 타임스탬프
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='weekly_evaluations')
    teacher = db.relationship('User', backref='weekly_evaluations')

    def __repr__(self):
        return f'<WeeklyEvaluation {self.student_id} Week{self.week_number} {self.grade}>'

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'teacher_id': self.teacher_id,
            'eval_date': self.eval_date.strftime('%Y-%m-%d') if self.eval_date else None,
            'week_number': self.week_number,
            'book_title': self.book_title,
            'class_type': self.class_type,
            'score': self.score,
            'grade': self.grade,
            'participation_score': self.participation_score,
            'understanding_score': self.understanding_score,
            'comment': self.comment,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class AceEvaluation(db.Model):
    """ACE 분기 평가 모델 (3개월 단위 종합 역량 평가)"""
    __tablename__ = 'ace_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 분기 정보
    year = db.Column(db.Integer, nullable=False, index=True)  # 2025, 2026...
    quarter = db.Column(db.String(20), nullable=False, index=True)  # "1분기 (1~3월)", "2분기 (4~6월)", etc.

    # ACE 평가 점수 (JSON 저장)
    # 5개 축 (독해력, 사고력, 서술능력, 창의력, 소통능력) × 각 3개 항목 = 15개 항목
    # 각 항목은 "특", "상", "중", "하", "저" 중 하나
    scores_json = db.Column(db.Text, nullable=False)  # JSON: {"사실, 분석적 독해": "중", ...}

    # 종합 코멘트
    comment = db.Column(db.Text, nullable=True)

    # 타임스탬프
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='ace_evaluations')
    teacher = db.relationship('User', backref='ace_evaluations')

    def __repr__(self):
        return f'<AceEvaluation {self.student_id} {self.year} {self.quarter}>'

    @property
    def scores(self):
        """점수 딕셔너리 반환"""
        if self.scores_json:
            return json.loads(self.scores_json)
        return {}

    @scores.setter
    def scores(self, value):
        """점수 딕셔너리 저장"""
        if isinstance(value, dict):
            self.scores_json = json.dumps(value, ensure_ascii=False)
        else:
            raise ValueError("scores must be a dictionary")

    def get_total_score(self):
        """총점 계산 (15개 항목의 점수 합계, 최대 75점)"""
        grade_scores = {"특": 5, "상": 4, "중": 3, "하": 2, "저": 1}
        scores_dict = self.scores
        return sum(grade_scores.get(grade, 0) for grade in scores_dict.values())

    def get_axis_average(self, axis_items):
        """특정 축의 평균 점수 계산 (5점 만점)

        Args:
            axis_items: 축에 속한 항목명 리스트 (예: ["사실, 분석적 독해", "추론적 독해", "비판적 독해"])

        Returns:
            float: 평균 점수 (0~5)
        """
        grade_scores = {"특": 5, "상": 4, "중": 3, "하": 2, "저": 1}
        scores_dict = self.scores

        item_scores = [grade_scores.get(scores_dict.get(item, "중"), 3) for item in axis_items]

        if not item_scores:
            return 0.0

        return sum(item_scores) / len(item_scores)

    def to_dict(self):
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'teacher_id': self.teacher_id,
            'year': self.year,
            'quarter': self.quarter,
            'scores': self.scores,
            'total_score': self.get_total_score(),
            'comment': self.comment,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


# ACE 평가 항목 상수 정의
ACE_AXES = [
    {
        "name": "독해력",
        "color": "#3B82F6",
        "items": [
            {"name": "사실, 분석적 독해", "desc": "내용에 대한 정확한 이해, 분석"},
            {"name": "추론적 독해", "desc": "독해 내용을 바탕으로 다른 정보 이끌어내기"},
            {"name": "비판적 독해", "desc": "합리적, 논리적으로 평가, 분류하는 독해"}
        ]
    },
    {
        "name": "사고력",
        "color": "#8B5CF6",
        "items": [
            {"name": "논리력", "desc": "주장에 대한 적절한 근거 제시"},
            {"name": "비교, 대조", "desc": "대상과 대상 사이의 공통점, 차이점 찾아내기"},
            {"name": "문제해결", "desc": "특정 상황, 현상에 대해 해결책 제시"}
        ]
    },
    {
        "name": "서술능력",
        "color": "#10B981",
        "items": [
            {"name": "맞춤법, 어휘력", "desc": "정확한 맞춤법, 적절한 어휘 활용"},
            {"name": "문장력", "desc": "간결하고 정확한 문장 서술"},
            {"name": "구성력", "desc": "문단 혹은 문장의 체계적 배치와 연결"}
        ]
    },
    {
        "name": "창의력",
        "color": "#F59E0B",
        "items": [
            {"name": "독창성", "desc": "새로운 관점 제시, 다각적 사고"},
            {"name": "관찰력", "desc": "사건이나 현상에 대한 심층적 사고"},
            {"name": "종합력", "desc": "여러 가지 사건, 정보를 모아 사고하는 능력"}
        ]
    },
    {
        "name": "소통능력",
        "color": "#F43F5E",
        "items": [
            {"name": "경청능력", "desc": "상대방의 말에 집중하고 핵심 파악하기"},
            {"name": "전달력", "desc": "주장과 근거를 논리적으로 전달하기"},
            {"name": "정확성", "desc": "사고 내용과 주장하는 내용 간의 일치성"}
        ]
    }
]

# 각 축에 item_names 추가 (템플릿에서 사용)
for axis in ACE_AXES:
    axis['item_names'] = [item['name'] for item in axis['items']]

# 모든 평가 항목 리스트 (15개)
ACE_ALL_ITEMS = []
for axis in ACE_AXES:
    for item in axis['items']:
        ACE_ALL_ITEMS.append(item['name'])

# 등급 라벨
GRADE_LABELS = ["특", "상", "중", "하", "저"]
GRADE_SCORES = {"특": 5, "상": 4, "중": 3, "하": 2, "저": 1}

# 주차 평가 등급
WEEKLY_GRADES = ["A+", "A0", "A-", "B+", "B0", "B-", "C+", "C0", "C-", "D+", "D0", "D-", "E", "F"]

# 수업 유형
CLASS_TYPES = ["1:1", "일반 그룹", "하크니스"]

# 분기 리스트
QUARTERS = ["1분기 (12~2월)", "2분기 (3~5월)", "3분기 (6~8월)", "4분기 (9~11월)"]

# 강사 코멘트 선택 옵션
TEACHER_COMMENTS = [
    "수업 태도가 매우 적극적이며 집중력이 뛰어납니다.",
    "글쓰기 실력이 꾸준히 향상되고 있습니다.",
    "논리적 사고력이 돋보이는 학생입니다.",
    "창의적인 아이디어 표현이 우수합니다.",
    "맞춤법과 문장력이 안정적입니다.",
    "토론 참여도가 높고 의견 전달이 명확합니다.",
    "독해력이 우수하며 깊이 있는 이해를 보입니다.",
    "수업 집중도를 높이면 더욱 발전할 수 있습니다.",
    "기초 문법 학습이 필요합니다.",
    "글의 구조와 구성력을 보완하면 좋겠습니다.",
    "어휘력 향상이 필요합니다.",
    "좀 더 적극적인 수업 참여를 권장합니다.",
    "꾸준한 독서와 글쓰기 연습이 필요합니다.",
    "논리적 근거 제시 능력을 키워야 합니다.",
    "경청 능력과 발표 능력이 모두 우수합니다.",
]
