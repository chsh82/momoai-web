# -*- coding: utf-8 -*-
"""Flask 애플리케이션 팩토리"""
from flask import Flask, send_file, redirect, url_for, render_template
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

    # 승인 대기 중인 사용자 접근 제한
    @app.before_request
    def check_user_approval():
        """비활성(승인 대기) 사용자를 pending 페이지로 리다이렉트"""
        from flask_login import current_user
        from flask import request, redirect, url_for

        if current_user.is_authenticated and not current_user.is_active:
            allowed_endpoints = {
                'auth.pending_approval', 'auth.logout',
                'auth.login', 'static',
            }
            if request.endpoint not in allowed_endpoints:
                # JSON API 요청은 403 반환
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({'error': '계정 승인 대기 중입니다.', 'code': 'pending_approval'}), 403
                return redirect(url_for('auth.pending_approval'))

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

    @app.template_filter('kst')
    def to_kst_filter(dt, fmt='%m/%d %H:%M'):
        """UTC datetime → KST(+9) 변환 후 포맷. time 객체는 그대로 포맷."""
        import datetime as dt_module
        from datetime import timedelta
        if dt is None:
            return ''
        # time objects (e.g. course start_time) are stored as KST already
        if isinstance(dt, dt_module.time) and not isinstance(dt, dt_module.datetime):
            return dt.strftime(fmt)
        # date objects: adding hours has no effect (safe but no-op)
        return (dt + timedelta(hours=9)).strftime(fmt)

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

    # Service Worker를 루트(/) scope로 제공
    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory, make_response
        response = make_response(send_from_directory(static_dir, 'sw.js'))
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

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
            # 동적 HTML은 캐시 금지 (로그인 사용자별 다른 데이터 표시)
            if 'Cache-Control' not in response.headers:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
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

    from app.inquiry import inquiry_bp
    app.register_blueprint(inquiry_bp)

    from app.news import news_bp
    app.register_blueprint(news_bp)

    from app.messages import messages_bp
    app.register_blueprint(messages_bp)

    from app.payment import payment_bp
    app.register_blueprint(payment_bp, url_prefix='/payment')

    # Context processor: 미읽은 알림 카운트 주입
    @app.context_processor
    def inject_unread_counts():
        default = {'homework': 0, 'announcement': 0, 'essay': 0,
                   'feedback': 0, 'total': 0, 'assignments': 0, 'pending_users': 0}
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

            # 관리자용: 승인 대기 회원 수 (거절된 사용자 제외)
            pending_users = 0
            if current_user.is_active and current_user.has_permission_level(2):
                from app.models import User as _UserModel
                # 거절됐거나 이미 한 번 승인된(정지 포함) 사용자 제외
                exclude_ids = [
                    n.user_id for n in Notification.query.filter(
                        Notification.notification_type.in_(['account_rejected', 'account_approved'])
                    ).with_entities(Notification.user_id).all()
                ]
                q = _UserModel.query.filter_by(is_active=False).filter(
                    _UserModel.role.in_(['teacher', 'parent', 'student'])
                )
                if exclude_ids:
                    q = q.filter(~_UserModel.user_id.in_(exclude_ids))
                pending_users = q.count()

            # DM 미읽은 수 (강사/관리자만)
            dm_unread = 0
            if current_user.role in ('admin', 'teacher'):
                from app.models.conversation import Conversation, ConversationMessage
                dm_unread = ConversationMessage.query.join(
                    Conversation,
                    ConversationMessage.conversation_id == Conversation.conversation_id
                ).filter(
                    db.or_(
                        Conversation.user1_id == current_user.user_id,
                        Conversation.user2_id == current_user.user_id
                    ),
                    ConversationMessage.sender_id != current_user.user_id,
                    ConversationMessage.is_read == False
                ).count()

            counts = {
                'homework': hw,
                'announcement': ann,
                'assignments': hw + ann,
                'essay': _count('essay_complete'),
                'feedback': _count(['teacher_feedback', 'consultation']),
                'new_submission': _count('essay_submitted'),  # 강사용: 새 제출 건수
                'pending_users': pending_users,  # 관리자용: 승인 대기
                'dm': dm_unread,  # DM 미읽은 수
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
                return {'parent_survey_completed': True}
            from app.models import ParentStudent, Student
            from app.models.student_profile import StudentProfile

            # 연결된 모든 자녀 조회
            children = db.session.query(Student).join(
                ParentStudent, ParentStudent.student_id == Student.student_id
            ).filter(
                ParentStudent.parent_id == current_user.user_id,
                ParentStudent.is_active == True
            ).all()

            if not children:
                # 연결된 자녀 없음 → 설문 필요 (녹색)
                return {'parent_survey_completed': False}

            # 자녀 중 프로필(설문)이 없는 경우가 하나라도 있으면 녹색 유지
            all_completed = all(
                StudentProfile.query.filter_by(student_id=child.student_id).first() is not None
                for child in children
            )
            return {'parent_survey_completed': all_completed}
        except Exception:
            return {'parent_survey_completed': True}

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
        return render_template('landing.html')

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

    # API: 처리 대기 업무 팝업 확인
    @app.route('/api/action-items/pending')
    @login_required
    def api_action_items_pending():
        """오늘 팝업용 미완료 업무 목록 조회 (admin/teacher만)"""
        from flask import jsonify
        from app.models.action_item import ActionItem
        from sqlalchemy import case as sa_case

        if current_user.role not in ('admin', 'master_admin', 'teacher'):
            return jsonify({'success': True, 'items': []})

        priority_order = sa_case(
            {'high': 1, 'medium': 2, 'low': 3},
            value=ActionItem.priority,
            else_=4
        )

        from sqlalchemy import or_
        from app.models.user import User as UserModel
        if current_user.role in ('admin', 'master_admin'):
            # 관리자: 관리자가 생성한 항목만
            admin_ids = [u.user_id for u in db.session.query(UserModel).filter(
                UserModel.role.in_(['admin', 'master_admin']), UserModel.is_deleted == False
            ).all()]
            visibility = ActionItem.created_by.in_(admin_ids)
        else:
            # 강사: 본인 생성 + 관리자 부여 항목
            visibility = or_(
                ActionItem.created_by == current_user.user_id,
                ActionItem.assigned_to == current_user.user_id,
            )

        items = ActionItem.query.filter(
            ActionItem.status != 'completed',
            visibility
        ).order_by(priority_order, ActionItem.due_date.asc().nullslast()).limit(20).all()

        from datetime import date
        result = []
        for item in items:
            result.append({
                'item_id':        item.item_id,
                'title':          item.title,
                'category':       item.category,
                'priority':       item.priority,
                'priority_icon':  item.priority_icon,
                'priority_label': item.priority_label,
                'status':         item.status,
                'status_label':   item.status_label,
                'is_overdue':     item.is_overdue,
                'due_date':       item.due_date.strftime('%m/%d') if item.due_date else None,
                'student_name':   item.student.name if item.student else None,
            })

        return jsonify({'success': True, 'items': result, 'total': len(result)})

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

    # 앱 시작 시 누락된 테이블 자동 생성
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass

    # 수업 리마인더 스케줄러 시작
    try:
        from app.utils.scheduler import init_scheduler
        init_scheduler(app)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'[Scheduler] 시작 실패: {e}')

    return app
