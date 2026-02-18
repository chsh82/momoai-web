"""
상담 기록 모델
"""
from datetime import datetime
from app.models import db

class ConsultationRecord(db.Model):
    """학생 상담 기록"""
    __tablename__ = 'consultation_records'

    consultation_id = db.Column(db.Integer, primary_key=True)

    # 기본 정보
    consultation_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)  # 상담일
    counselor_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)  # 상담자 (강사/관리자)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)  # 학생

    # 분류
    major_category = db.Column(db.String(50), nullable=False)  # 대분류: 신규상담, 퇴원상담, 분기별상담, 진로진학상담, 기타
    sub_category = db.Column(db.String(50))  # 소분류 (선택사항)

    # 상담 내용
    title = db.Column(db.String(200), nullable=False)  # 제목
    content = db.Column(db.Text, nullable=False)  # 상담 내용

    # 참고인 (관리자가 설정, 여러 명 가능)
    reference_teachers = db.Column(db.Text)  # JSON 형태로 저장: [user_id1, user_id2, ...]

    # MBTI 기반 추천
    student_mbti_type = db.Column(db.String(50))  # 학생의 MBTI 유형 (예: vocab-textual-summary)
    recommended_teaching_style = db.Column(db.Text)  # AI가 추천한 수업 스타일
    teaching_recommendations = db.Column(db.Text)  # 구체적인 교수법 추천사항

    # 공유 설정
    share_with_parents = db.Column(db.Boolean, default=False)  # 학부모 공유 여부
    parent_shared_at = db.Column(db.DateTime)  # 학부모 공유 일시

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    counselor = db.relationship('User', foreign_keys=[counselor_id], backref='consultations_given')
    student = db.relationship('Student', foreign_keys=[student_id], backref='consultations')

    def __repr__(self):
        return f'<ConsultationRecord {self.consultation_id}: {self.title}>'

    @property
    def reference_teacher_ids(self):
        """참고인 ID 리스트 반환"""
        import json
        if self.reference_teachers:
            try:
                return json.loads(self.reference_teachers)
            except:
                return []
        return []

    def add_reference_teacher(self, teacher_id):
        """참고인 추가"""
        import json
        ids = self.reference_teacher_ids
        if teacher_id not in ids:
            ids.append(teacher_id)
            self.reference_teachers = json.dumps(ids)

    def remove_reference_teacher(self, teacher_id):
        """참고인 제거"""
        import json
        ids = self.reference_teacher_ids
        if teacher_id in ids:
            ids.remove(teacher_id)
            self.reference_teachers = json.dumps(ids)

    def can_view(self, user_id, user_role):
        """사용자가 이 상담 기록을 볼 수 있는지 확인"""
        # 관리자는 모든 기록 열람 가능
        if user_role in ['admin', 'master_admin']:
            return True

        # 상담자 본인
        if self.counselor_id == user_id:
            return True

        # 참고인으로 설정된 강사
        if user_id in self.reference_teacher_ids:
            return True

        return False

    def can_view_by_parent(self, parent_id):
        """학부모가 이 상담 기록을 볼 수 있는지 확인"""
        from app.models import ParentStudent

        # 공유 설정이 되어있지 않으면 볼 수 없음
        if not self.share_with_parents:
            return False

        # 해당 학생의 학부모인지 확인
        relation = ParentStudent.query.filter_by(
            parent_id=parent_id,
            student_id=self.student_id,
            is_active=True
        ).first()

        return relation is not None

    def share_to_parents(self):
        """학부모에게 공유"""
        if not self.share_with_parents:
            self.share_with_parents = True
            self.parent_shared_at = datetime.utcnow()
