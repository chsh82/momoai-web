# -*- coding: utf-8 -*-
"""Flask 애플리케이션 팩토리"""
from flask import Flask, send_file, redirect, url_for
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user
from pathlib import Path
from datetime import datetime

from app.models import db
from config import config


migrate = Migrate()
login_manager = LoginManager()


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

    # Extensions 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

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
    app.jinja_env.globals.update(now=datetime.now)

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
