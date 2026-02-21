# -*- coding: utf-8 -*-
"""Flask 애플리케이션 팩토리"""
from flask import Flask, send_file, redirect, url_for
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user
from flask_compress import Compress
from pathlib import Path
from datetime import datetime

from app.models import db
from app.extensions import limiter, mail
from config import config


migrate = Migrate()
login_manager = LoginManager()
compress = Compress()


def create_app(config_name='default'):
    """Flask 애플리케이션 생성"""
    # 프로젝트 루트를 template/static 폴더로 설정
    import os
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    app.config.from_object(config[config_name])

    # Flask-Compress 설정 (Gzip 압축)
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html', 'text/css', 'text/xml',
        'application/json', 'application/javascript',
        'text/javascript', 'application/xml'
    ]
    app.config['COMPRESS_LEVEL'] = 6  # 압축 레벨 (1-9, 6이 균형)
    app.config['COMPRESS_MIN_SIZE'] = 500  # 500바이트 이상만 압축

    # Extensions 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    compress.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    # Rate limit 초과 시 에러 핸들러
    from flask import flash, redirect, url_for
    @app.errorhandler(429)
    def ratelimit_handler(e):
        flash('너무 많은 요청이 감지되었습니다. 잠시 후 다시 시도해주세요.', 'error')
        return redirect(url_for('auth.login'))

    # Flask-Login 설정
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '로그인이 필요합니다.'

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    # Jinja2 custom filters
    @app.template_filter('basename')
    def basename_filter(path):
        """Extract basename from path"""
        return Path(path).name

    # Jinja2 global functions
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals.update(now=datetime.now, csrf_token=generate_csrf)

    # Lazy Loading 이미지 태그 헬퍼
    @app.template_global('lazy_img')
    def lazy_img_tag(src, alt='', css_class='', width=None, height=None):
        """Lazy loading이 적용된 img 태그 생성"""
        attrs = [f'src="{src}"', f'alt="{alt}"', 'loading="lazy"']
        if css_class:
            attrs.append(f'class="{css_class}"')
        if width:
            attrs.append(f'width="{width}"')
        if height:
            attrs.append(f'height="{height}"')
        return f'<img {" ".join(attrs)}>'

    # 정적 파일 캐싱 설정
    @app.after_request
    def add_header(response):
        """정적 파일에 캐시 헤더 추가"""
        if 'static' in response.headers.get('Content-Type', ''):
            # 정적 파일은 1년 캐싱 (CSS, JS, 이미지 등)
            response.headers['Cache-Control'] = 'public, max-age=31536000'
        elif response.mimetype and response.mimetype.startswith(('text/css', 'application/javascript', 'image/')):
            # CSS, JS, 이미지 파일 1년 캐싱
            response.headers['Cache-Control'] = 'public, max-age=31536000'
        elif response.mimetype and response.mimetype.startswith('text/html'):
            # HTML은 짧은 캐싱 (5분)
            response.headers['Cache-Control'] = 'public, max-age=300'
        return response

    # Jinja2 custom filters
    import json
    @app.template_filter('from_json')
    def from_json_filter(value):
        """JSON 문자열을 Python 객체로 변환"""
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    # Blueprints 등록
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.essays import essays_bp
    app.register_blueprint(essays_bp, url_prefix='/essays')

    from app.students import students_bp
    app.register_blueprint(students_bp, url_prefix='/students')

    # Dashboard removed - using role-specific portals only
    # from app.dashboard import dashboard_bp
    # app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from app.books import books_bp
    app.register_blueprint(books_bp, url_prefix='/books')

    from app.community import community_bp
    app.register_blueprint(community_bp, url_prefix='/community')

    # 검색
    from app.search import search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

    from app.notifications import notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    from app.profile import profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')

    from app.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.teacher import teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    from app.parent_portal import parent_bp
    app.register_blueprint(parent_bp, url_prefix='/parent')

    from app.student_portal import student_bp
    app.register_blueprint(student_bp, url_prefix='/student')

    from app.harkness import harkness_bp
    app.register_blueprint(harkness_bp, url_prefix='/harkness')

    from app.library import library_bp
    app.register_blueprint(library_bp, url_prefix='/library')

    from app.zoom import zoom_bp
    app.register_blueprint(zoom_bp, url_prefix='/zoom')

    # Context processor: 미읽은 알림 카운트 주입
    @app.context_processor
    def inject_unread_counts():
        default = {'homework': 0, 'announcement': 0, 'essay': 0,
                   'feedback': 0, 'total': 0, 'assignments': 0}
        try:
            from flask_login import current_user
            from app.models.notification import Notification

            if not current_user.is_authenticated:
                return {'unread_counts': default}

            def _count(ntype):
                if isinstance(ntype, list):
                    return Notification.query.filter(
                        Notification.user_id == current_user.user_id,
                        Notification.is_read == False,
                        Notification.notification_type.in_(ntype)
                    ).count()
                return Notification.query.filter_by(
                    user_id=current_user.user_id,
                    is_read=False,
                    notification_type=ntype
                ).count()

            hw = _count('homework_assignment')
            ann = _count('class_announcement')
            counts = {
                'homework': hw,
                'announcement': ann,
                'assignments': hw + ann,
                'essay': _count('essay_complete'),
                'feedback': _count(['teacher_feedback', 'consultation']),
                'total': Notification.query.filter_by(
                    user_id=current_user.user_id, is_read=False
                ).count(),
            }
        except Exception:
            counts = default

        return {'unread_counts': counts}

    # Context processor: 학부모 설문 완료 여부 주입
    @app.context_processor
    def inject_parent_survey_status():
        try:
            from flask_login import current_user
            if not current_user.is_authenticated or current_user.role != 'parent':
                return {'parent_survey_completed': False}
            from app.models import ParentStudent
            has_children = ParentStudent.query.filter_by(
                parent_id=current_user.user_id,
                is_active=True
            ).first() is not None
            return {'parent_survey_completed': has_children}
        except Exception:
            return {'parent_survey_completed': False}

    # 기본 라우트 - 역할별 포털로 리다이렉트
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            # 역할별 포털로 리다이렉트
            if current_user.role == 'admin' or current_user.role == 'manager':
                return redirect(url_for('admin.index'))
            elif current_user.role == 'teacher':
                return redirect(url_for('teacher.index'))
            elif current_user.role == 'student':
                return redirect(url_for('student.index'))
            elif current_user.role == 'parent':
                return redirect(url_for('parent.index'))
            else:
                return redirect(url_for('admin.index'))  # 기본값
        return redirect(url_for('auth.login'))

    # API: 팝업 공지사항 목록
    @app.route('/api/popup-announcements')
    @login_required
    def api_popup_announcements():
        """안 읽은 팝업 공지사항 목록 조회"""
        from flask import jsonify
        from app.models.announcement import Announcement

        # 팝업 공지사항 조회
        all_announcements = Announcement.query.filter_by(
            is_published=True,
            is_popup=True
        ).order_by(Announcement.created_at.desc()).all()

        # 현재 사용자가 볼 수 있고 안 읽은 공지만 필터링
        unread_popups = []
        for announcement in all_announcements:
            if announcement.is_active:
                target_roles = announcement.target_roles_list
                if 'all' in target_roles or current_user.role in target_roles:
                    # 안 읽은 것만
                    if not announcement.is_read_by(current_user.user_id):
                        unread_popups.append({
                            'announcement_id': announcement.announcement_id,
                            'title': announcement.title,
                            'content': announcement.content,
                            'announcement_type': announcement.announcement_type,
                            'author': announcement.author.name if announcement.author else '관리자',
                            'created_at': announcement.created_at.strftime('%Y년 %m월 %d일 %H:%M')
                        })

        return jsonify({
            'success': True,
            'announcements': unread_popups
        })

    # API: 공지사항 읽음 처리
    @app.route('/api/announcements/<announcement_id>/mark-read', methods=['POST'])
    @login_required
    def api_mark_announcement_read(announcement_id):
        """공지사항 읽음 처리"""
        from flask import jsonify
        from app.models.announcement import Announcement

        announcement = Announcement.query.get(announcement_id)

        if not announcement:
            return jsonify({
                'success': False,
                'message': '공지사항을 찾을 수 없습니다.'
            }), 404

        # 읽음 처리
        announcement.mark_as_read_by(current_user.user_id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '읽음 처리되었습니다.'
        })

    # API: 파일 다운로드
    @app.route('/api/download/<path:filename>')
    @login_required
    def api_download(filename):
        """파일 다운로드 API"""
        try:
            # HTML 또는 PDF 폴더에서 파일 찾기
            html_path = Path(app.config['HTML_FOLDER']) / filename
            pdf_path = Path(app.config['PDF_FOLDER']) / filename

            if html_path.exists():
                return send_file(html_path, as_attachment=True)
            elif pdf_path.exists():
                return send_file(pdf_path, as_attachment=True)
            else:
                return "파일을 찾을 수 없습니다.", 404

        except Exception as e:
            return str(e), 500

    return app
