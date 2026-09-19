# -*- coding: utf-8 -*-
"""Student 모델"""
from datetime import datetime
from app.models import db


class Student(db.Model):
    """학생 모델"""
    __tablename__ = 'students'

    student_id = db.Column(db.String(36), primary_key=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                       nullable=True)  # Phase 4에서 사용 (학생 계정 연결)
    name = db.Column(db.String(100), nullable=False, index=True)
    nickname = db.Column(db.String(20), nullable=True)  # 마일리지 랭킹 등 공개 화면에 쓰는 별명 (실명 대체)
    grade = db.Column(db.String(20), nullable=False)  # 초1~고3 (구체적 학년)
    school = db.Column(db.String(200), nullable=True)  # 학교명
    birth_date = db.Column(db.Date, nullable=True)  # 생년월일
    tier = db.Column(db.String(20), nullable=True, index=True)  # A, B, C, VIP 등 등급
    tier_updated_at = db.Column(db.DateTime, nullable=True)  # 등급 변경 일시
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True)   # 거주 국가
    city = db.Column(db.String(100), nullable=True)      # 거주 도시
    notes = db.Column(db.Text, nullable=True)
    is_temp = db.Column(db.Boolean, default=False, nullable=False)  # 임시 학생 여부
    gender = db.Column(db.String(10), nullable=True)  # male, female, other
    status = db.Column(db.String(20), default='active', nullable=False, index=True)  # active, leave, withdrawn
    status_changed_at = db.Column(db.DateTime, nullable=True)  # 상태 변경 일시
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 명예의 전당 월요일 축하 팝업 - 이 학생 계정에게 마지막으로 팝업을 보여준 시각
    # (같은 주에 중복으로 뜨지 않게 막는 용도)
    hof_congrats_shown_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    teacher = db.relationship('User', back_populates='students',
                             foreign_keys=[teacher_id])
    essays = db.relationship('Essay', back_populates='student',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Student {self.name} ({self.grade})>'

    def __init__(self, **kwargs):
        super(Student, self).__init__(**kwargs)
        if not self.student_id:
            import uuid
            self.student_id = str(uuid.uuid4())

    @property
    def display_name(self):
        """학년·학교 포함 표시용 이름"""
        if self.grade and self.school:
            return f"{self.name} ({self.grade} · {self.school})"
        elif self.grade:
            return f"{self.name} ({self.grade})"
        return self.name

    @property
    def essay_count(self):
        """첨삭 수"""
        return len(self.essays)

    @property
    def completed_essay_count(self):
        """완료된 첨삭 수"""
        return len([e for e in self.essays if e.is_finalized])

    def update_tier(self, new_tier):
        """등급 업데이트"""
        self.tier = new_tier
        self.tier_updated_at = datetime.utcnow()

    @property
    def main_teacher(self):
        """지도교사로 표시할 강사(명예의 전당 등 공개 화면용).

        - teacher_id(실제 접근 권한 기준 - 여기서는 바꾸지 않음)가 일반 강사 계정이면
          그 강사를 그대로 "현재 담당 강사"로 보여준다.
        - teacher_id가 마스터/매니저 관리자 계정(role_level<=2)이면, 이 학생이 현재
          수강 중인 "정규" 수업(course_type='보강수업'인 보강 수업은 제외)의 담당 강사로
          대체해 보여준다 - 관리자 계정이 실제 지도교사인 것처럼 보이는 문제를 화면
          표시 단에서 바로잡는다(실제 teacher_id 자체는 접근 권한에 영향을 주므로 건드리지
          않음 - 별도 데이터 정리가 필요하면 scripts/backfill_hof_main_teacher.py 참고).
        - 정규 수업이 여러 개라 강사가 둘 이상이면 가장 최근에 시작한 수업의 강사를 쓴다.
        - 대체할 정규 수업을 못 찾으면(수강 중인 정규 수업이 없음) 원래 teacher_id를
          그대로 반환한다 - 화면에서 관리자 이름이 보이더라도 실제로 배정된 강사가 없다는
          사실을 숨기지 않는다.
        """
        if self.teacher and self.teacher.role_level > 2:
            return self.teacher

        from app.models.course import Course, CourseEnrollment

        enrollments = (CourseEnrollment.query
                       .join(Course, CourseEnrollment.course_id == Course.course_id)
                       .filter(CourseEnrollment.student_id == self.student_id)
                       .filter(CourseEnrollment.status == 'active')
                       .filter(Course.status == 'active')
                       .filter(Course.course_type != '보강수업')
                       .filter(Course.teacher_id.isnot(None))
                       .order_by(Course.start_date.desc())
                       .all())
        for e in enrollments:
            if e.course and e.course.teacher and e.course.teacher.role_level > 2:
                return e.course.teacher

        return self.teacher

    def has_tier_access(self, required_tiers):
        """특정 티어에 대한 접근 권한 확인

        Args:
            required_tiers: 문자열 또는 리스트 (예: 'A' 또는 ['A', 'B'])
        """
        if not required_tiers:
            return True

        if isinstance(required_tiers, str):
            required_tiers = [required_tiers]

        return self.tier in required_tiers
