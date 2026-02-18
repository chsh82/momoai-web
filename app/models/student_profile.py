"""
Student Profile Model - Initial Survey Data
학생 기초 조사 정보를 저장하는 모델
"""
from datetime import datetime
import json
from app.models import db


class StudentProfile(db.Model):
    """학생 기초 조사 프로필 정보"""
    __tablename__ = 'student_profiles'

    profile_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False, unique=True)

    # 기본 정보
    survey_date = db.Column(db.DateTime, default=datetime.utcnow)  # 설문 작성일
    address = db.Column(db.Text)  # 주소
    parent_contact = db.Column(db.String(50))  # 학부모 연락처
    current_school = db.Column(db.String(100))  # 재학 중인 학교

    # 독서 경험 및 역량
    reading_experience = db.Column(db.String(50))  # 독서논술 수업 경험 (6개월 미만, 6개월~1년 등)
    reading_competency = db.Column(db.Integer)  # 독서역량 (1-5)
    weekly_reading_amount = db.Column(db.String(50))  # 주 평균 독서량 (주 1권 미만, 주 1-2권 등)
    preferred_genres = db.Column(db.Text)  # 선호 독서 분야 (JSON array)

    # 학생 성향
    personality_traits = db.Column(db.Text)  # 학생 성향 (JSON array)

    # 수업 목표 및 요청사항
    main_improvement_goal = db.Column(db.String(200))  # 가장 향상시키고 싶은 부분
    preferred_class_style = db.Column(db.String(200))  # 선호하는 수업 스타일
    teacher_request = db.Column(db.Text)  # 강사에게 요청사항

    # 유입 경로
    referral_source = db.Column(db.String(100))  # 모모의 책장을 알게 된 경로

    # 진로/진학 정보
    education_info_needs = db.Column(db.Text)  # 필요한 교육&입시 정보 (JSON array)
    academic_goals = db.Column(db.Text)  # 진학 목표 (JSON array)
    career_interests = db.Column(db.Text)  # 관심 진로 분야 (JSON array)
    other_interests = db.Column(db.Text)  # 기타 관심사항

    # 형제자매 정보
    sibling_info = db.Column(db.Text)  # 형제/자매 정보

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))  # 입력한 관리자

    # Relationships
    student = db.relationship('Student', backref=db.backref('profile', uselist=False))
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<StudentProfile {self.student_id}>'

    @property
    def preferred_genres_list(self):
        """선호 장르를 리스트로 반환"""
        if self.preferred_genres:
            try:
                return json.loads(self.preferred_genres)
            except:
                return []
        return []

    @property
    def personality_traits_list(self):
        """성향을 리스트로 반환"""
        if self.personality_traits:
            try:
                return json.loads(self.personality_traits)
            except:
                return []
        return []

    @property
    def education_info_needs_list(self):
        """교육정보 필요사항을 리스트로 반환"""
        if self.education_info_needs:
            try:
                return json.loads(self.education_info_needs)
            except:
                return []
        return []

    @property
    def academic_goals_list(self):
        """진학 목표를 리스트로 반환"""
        if self.academic_goals:
            try:
                return json.loads(self.academic_goals)
            except:
                return []
        return []

    @property
    def career_interests_list(self):
        """진로 관심사를 리스트로 반환"""
        if self.career_interests:
            try:
                return json.loads(self.career_interests)
            except:
                return []
        return []

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'profile_id': self.profile_id,
            'student_id': self.student_id,
            'survey_date': self.survey_date.isoformat() if self.survey_date else None,
            'address': self.address,
            'parent_contact': self.parent_contact,
            'current_school': self.current_school,
            'reading_experience': self.reading_experience,
            'reading_competency': self.reading_competency,
            'weekly_reading_amount': self.weekly_reading_amount,
            'preferred_genres': self.preferred_genres_list,
            'personality_traits': self.personality_traits_list,
            'main_improvement_goal': self.main_improvement_goal,
            'preferred_class_style': self.preferred_class_style,
            'teacher_request': self.teacher_request,
            'referral_source': self.referral_source,
            'education_info_needs': self.education_info_needs_list,
            'academic_goals': self.academic_goals_list,
            'career_interests': self.career_interests_list,
            'other_interests': self.other_interests,
            'sibling_info': self.sibling_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
