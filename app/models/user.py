# -*- coding: utf-8 -*-
"""User 모델"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db


class User(UserMixin, db.Model):
    """사용자 모델"""
    __tablename__ = 'users'

    user_id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='teacher', index=True)
    role_level = db.Column(db.Integer, default=4, index=True)  # 1=master, 2=manager, 3=teacher, 4=parent, 5=student
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)  # 초기 비밀번호 변경 필요 여부

    # 프로필 이미지
    profile_image_filename = db.Column(db.String(255), nullable=True)
    profile_image_path = db.Column(db.String(500), nullable=True)

    # 온라인 강의실 (강사용)
    zoom_link = db.Column(db.Text, nullable=True)  # 암호화된 줌 링크
    zoom_token = db.Column(db.String(100), unique=True, nullable=True, index=True)  # 강사별 고정 토큰

    # 거주 정보 (학부모/학생 계정용)
    country = db.Column(db.String(100), nullable=True)   # 거주 국가
    city = db.Column(db.String(100), nullable=True)      # 거주 도시

    # 강사 소개 (teacher 역할용)
    teacher_intro = db.Column(db.Text, nullable=True)
    teacher_intro_public = db.Column(db.Boolean, default=False)

    # 보안 필드
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    email_verified = db.Column(db.Boolean, default=True, nullable=False)  # 기존 사용자는 True
    email_verification_token = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    students = db.relationship('Student', back_populates='teacher',
                              foreign_keys='Student.teacher_id',
                              cascade='all, delete-orphan')
    essays = db.relationship('Essay', back_populates='user',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'

    def get_id(self):
        """Flask-Login이 사용하는 ID"""
        return self.user_id

    def set_password(self, password):
        """비밀번호 설정 (해싱)"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """비밀번호 확인"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        """계정 잠금 여부"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    @property
    def lock_remaining_minutes(self):
        """잠금 해제까지 남은 분"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            delta = self.locked_until - datetime.utcnow()
            return max(1, int(delta.total_seconds() / 60))
        return 0

    def increment_failed_attempts(self, max_attempts=5, lockout_minutes=15):
        """로그인 실패 횟수 증가, 초과 시 계정 잠금"""
        from datetime import timedelta
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def reset_failed_attempts(self):
        """로그인 성공 시 실패 횟수 초기화"""
        self.failed_login_attempts = 0
        self.locked_until = None

    @property
    def is_authenticated(self):
        """Flask-Login: UserMixin 기본값은 is_active를 리턴하므로
        비활성 사용자가 인증되지 않은 것으로 처리됨.
        DB에 존재하는 사용자는 항상 인증된 것으로 간주."""
        return True

    @property
    def is_teacher(self):
        """강사 여부"""
        return self.role == 'teacher'

    @property
    def is_admin(self):
        """관리자 여부"""
        return self.role == 'admin'

    @property
    def is_student(self):
        """학생 여부"""
        return self.role == 'student'

    @property
    def is_parent(self):
        """학부모 여부"""
        return self.role == 'parent'

    @property
    def is_master_admin(self):
        """마스터 관리자 여부 (전체 권한)"""
        return self.role_level == 1

    @property
    def is_manager(self):
        """매니저 여부"""
        return self.role_level == 2

    @property
    def is_staff(self):
        """스태프 여부"""
        return self.role_level == 3

    @property
    def can_edit(self):
        """수정 권한 여부 (admin 또는 teacher만)"""
        return self.role in ['admin', 'teacher']

    def has_permission_level(self, required_level):
        """권한 레벨 확인 (낮은 숫자가 높은 권한)"""
        return self.role_level <= required_level

    def can_manage_user(self, target_user):
        """다른 사용자를 관리할 수 있는지 확인"""
        # 마스터 관리자는 모두 관리 가능
        if self.is_master_admin:
            return True
        # 매니저는 자신보다 낮은 레벨만 관리 가능
        if self.is_manager:
            return target_user.role_level > self.role_level
        return False

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.user_id:
            import uuid
            self.user_id = str(uuid.uuid4())
