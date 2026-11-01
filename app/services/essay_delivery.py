"""Explicit lesson submission. Never expands student-wide teacher access."""
from app.models import db, User
from app.models.course import Course, CourseEnrollment, CourseSession


def validate_submission_csrf():
    from flask import request, abort
    from flask_wtf.csrf import validate_csrf
    from wtforms.validators import ValidationError
    try:
        validate_csrf(request.form.get('csrf_token') or request.headers.get('X-CSRFToken'))
    except ValidationError:
        abort(400, description='유효한 CSRF 토큰이 필요합니다.')


def regular_teachers(student):
    return (User.query.join(Course, Course.teacher_id == User.user_id)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.course_id)
        .filter(CourseEnrollment.student_id == student.student_id, CourseEnrollment.status == 'active',
            Course.status == 'active', Course.is_terminated.is_(False), User.role == 'teacher',
            User.is_active.is_(True), db.or_(Course.course_type.is_(None), ~Course.course_type.like('보강%')))
        .order_by(CourseEnrollment.enrolled_at.asc(), User.user_id).distinct().all())


def makeup_choices(student):
    """Scheduled/completed lessons in valid active/completed makeup enrollment.

    Cancelled/terminated courses and dropped enrollments fail closed. Completed
    lessons remain submit-able; enrollment must cover the lesson date.
    """
    return (CourseSession.query.join(Course).join(CourseEnrollment,
        CourseEnrollment.course_id == Course.course_id).join(User, Course.teacher_id == User.user_id)
        .filter(CourseEnrollment.student_id == student.student_id,
            CourseEnrollment.status.in_(['active', 'completed']),
            Course.status.in_(['active', 'completed']), Course.is_terminated.is_(False),
            Course.course_type.like('보강%'), CourseSession.status.in_(['scheduled', 'completed']),
            db.func.date(CourseEnrollment.enrolled_at) <= CourseSession.session_date,
            db.or_(CourseEnrollment.completed_at.is_(None),
                db.func.date(CourseEnrollment.completed_at) >= CourseSession.session_date),
            User.role == 'teacher', User.is_active.is_(True))
        .order_by(CourseSession.session_date.desc(), CourseSession.session_id).all())


def essay_acl(actor, table, *, write=False):
    """Single SQL predicate for original/list/files and correction mutations."""
    import sqlalchemy as sa
    from app.services.essay_scope import _admin, _teacher, enrollment_scope
    users = db.metadata.tables['users']
    active = sa.select(users.c.user_id).where(users.c.user_id == getattr(actor, 'user_id', None),
        users.c.is_active.is_(True)).exists()
    if _admin(actor):
        return active
    if not _teacher(actor):
        return sa.false()
    scope = enrollment_scope(actor).subquery()
    linked = sa.select(scope.c.enrollment_id).where(scope.c.student_id == table.c.student_id,
        scope.c.course_id == table.c.course_id).correlate(table).exists()
    original = sa.or_(table.c.user_id == actor.user_id, linked)
    grants = db.metadata.tables['essay_teacher_grants']
    shared = sa.select(grants.c.grant_id).where(grants.c.essay_id == table.c.essay_id,
        grants.c.teacher_id == actor.user_id, grants.c.revoked_at.is_(None)).correlate(table).exists()
    if write:
        owner = sa.select(grants.c.teacher_id).where(grants.c.essay_id == table.c.essay_id,
            grants.c.mode == 'correction', grants.c.revoked_at.is_(None)).correlate(table).scalar_subquery()
        return sa.and_(active, sa.or_(owner == actor.user_id, sa.and_(owner.is_(None), original)))
    return sa.and_(active, sa.or_(original, shared))


def scoped_ocr_query(actor):
    """Preserve own standalone OCR; linked OCR always follows essay read ACL."""
    from app.models import OCRHistory
    from app.services.essay_scope import original_access_query, _admin
    safe = original_access_query(actor, 'essay').subquery()
    query = OCRHistory.query.filter(db.or_(OCRHistory.essay_id.is_(None),
        OCRHistory.essay_id.in_(db.select(safe.c.essay_id))))
    if not _admin(actor):
        query = query.filter(OCRHistory.user_id == actor.user_id)
    return query


def can_correct(actor, essay):
    import sqlalchemy as sa
    from app.models import Essay
    table = Essay.__table__
    with db.session.no_autoflush:
        return db.session.execute(sa.select(table.c.essay_id).where(
            table.c.essay_id == essay.essay_id, essay_acl(actor, table, write=True))).first() is not None


def lock_essay(essay_id, *, session=None):
    """Shared transaction mutex until caller commit/rollback.

    A real UPDATE acquires SQLite's writer lock (SELECT FOR UPDATE does not).
    Other databases take the same essay row lock. Never flush a stale identity
    map before the lock; read authoritative scalar state after acquiring it.
    Sorted multi-essay acquisition avoids inconsistent lock order. No retries.
    """
    import sqlalchemy as sa
    from app.models import Essay
    session = session if session is not None else db.session
    table = Essay.__table__
    with session.no_autoflush:
        changed = session.execute(sa.update(table).where(table.c.essay_id == essay_id)
            .values(status=table.c.status)).rowcount
        if changed != 1:
            raise ValueError('글을 찾을 수 없습니다.')
        return session.execute(sa.select(table.c.status).where(table.c.essay_id == essay_id)).scalar_one()


def begin_correction(actor, essay, *, session=None, revision_note=None):
    """Durable generation claim serialized with forwarding and cancellation."""
    from app.services.correction_jobs import claim
    return claim(actor, essay, revision_note=revision_note, session=session)


def forward_essays(actor, essays, teacher, *, mode, reason):
    """Stage grants/notifications atomically; caller commits. No push on preview."""
    from datetime import datetime, timezone
    from app.services.essay_scope import is_hub_admin
    from app.models.essay import EssayTeacherGrant
    from app.models import Notification
    if not actor.is_active or not is_hub_admin(actor):
        raise PermissionError('관리자만 전달할 수 있습니다.')
    if not teacher or not teacher.is_active or teacher.role != 'teacher' or teacher.role_level not in (3, 4):
        raise ValueError('활성 강사를 선택해주세요.')
    reason = (reason or '').strip()
    if mode not in ('reference', 'correction') or not reason or len(reason) > 2000:
        raise ValueError('전달 유형과 사유(1~2000자)를 확인해주세요.')
    essays = sorted(essays, key=lambda essay: essay.essay_id)
    states = {essay.essay_id: lock_essay(essay.essay_id) for essay in essays}
    if mode == 'correction' and any(status == 'processing' for status in states.values()):
        raise ValueError('첨삭 생성 중에는 담당을 이전할 수 없습니다.')
    created = []
    for essay in essays:
        existing = EssayTeacherGrant.query.filter_by(essay_id=essay.essay_id,
            teacher_id=teacher.user_id, mode=mode, revoked_at=None).first()
        if existing:
            continue
        if mode == 'correction':
            from app.services.correction_jobs import invalidate
            invalidate(essay.essay_id)
            for previous in EssayTeacherGrant.query.filter_by(essay_id=essay.essay_id,
                    mode='correction', revoked_at=None).all():
                revoke_grant(actor, previous, '새 첨삭 담당 이전: ' + reason)
            # Release partial-unique owner before inserting its replacement.
            db.session.flush()
        grant = EssayTeacherGrant(essay_id=essay.essay_id, teacher_id=teacher.user_id,
            actor_id=actor.user_id, mode=mode, reason=reason,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.add(grant)
        db.session.add(Notification(user_id=teacher.user_id, notification_type='essay_forwarded',
            title='글 강사 전달', message=f'{essay.title or "과제"}: {reason}',
            link_url='/essays/'+essay.essay_id+'/view_submission'))
        created.append(grant)
    return created


def revoke_grant(actor, grant, reason):
    from datetime import datetime, timezone
    from app.services.essay_scope import is_hub_admin
    if not actor.is_active or not is_hub_admin(actor):
        raise PermissionError('관리자만 회수할 수 있습니다.')
    reason = (reason or '').strip()
    if not reason or len(reason) > 2000:
        raise ValueError('회수 사유(1~2000자)를 입력해주세요.')
    from app.models.essay import EssayTeacherGrant
    from app.models import Essay
    import sqlalchemy as sa
    table = EssayTeacherGrant.__table__
    with db.session.no_autoflush:
        lock_essay(grant.essay_id)
        active = db.session.execute(sa.select(table.c.mode, table.c.essay_id).where(
            table.c.grant_id == grant.grant_id, table.c.revoked_at.is_(None))).first()
        if active is None:
            return False
        status = db.session.execute(sa.select(Essay.__table__.c.status).where(
            Essay.__table__.c.essay_id == active.essay_id)).scalar_one()
        if active.mode == 'correction' and status == 'processing':
            raise ValueError('첨삭 생성 중에는 담당을 회수할 수 없습니다.')
        if active.mode == 'correction':
            from app.services.correction_jobs import invalidate
            invalidate(active.essay_id)
        changed = db.session.execute(sa.update(table).where(table.c.grant_id == grant.grant_id,
            table.c.revoked_at.is_(None)).values(
                revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
                revoked_by=actor.user_id, revoke_reason=reason)).rowcount
        db.session.expire(grant)
        return changed == 1


def can_view_result(actor, essay):
    """One policy for every private result output; preserve portal statuses."""
    from app.models import ParentStudent, Student
    from app.services.essay_scope import original_access_query
    if not actor.is_active:
        return False
    if db.session.execute(original_access_query(actor, 'essay', essay.essay_id)).first():
        return True
    if not essay.is_finalized:
        return False
    if actor.role == 'parent':
        return ParentStudent.query.filter_by(parent_id=actor.user_id,
            student_id=essay.student_id, is_active=True).first() is not None
    if actor.role == 'student' and essay.status in ('reviewing', 'completed'):
        student = Student.query.filter_by(user_id=actor.user_id).first() or Student.query.filter_by(email=actor.email).first()
        return student is not None and student.student_id == essay.student_id
    return False


def download_output(filename):
    """Legacy filename download must resolve to exactly one authorized essay.

    Unknown/orphan files fail closed instead of bypassing the per-essay ACL.
    Never trust filenames as authorization, and never allow directory traversal.
    """
    from pathlib import Path, PureWindowsPath
    from flask import abort, current_app, send_file
    from flask_login import current_user
    from app.models import Essay, EssayVersion, EssayResult, ParentStudent, Student
    if not filename or '/' in filename or '\\' in filename or ':' in filename or filename in ('.', '..'):
        abort(404)
    targets = []
    for folder in ('HTML_FOLDER', 'PDF_FOLDER'):
        root = Path(current_app.config[folder]).resolve()
        target = (root / filename).resolve()
        if target.parent == root and target.is_file():
            targets.append(target)
    if len(targets) != 1:
        abort(404)
    target = targets[0]
    ids = set()
    for model, field in ((EssayVersion, EssayVersion.html_path),
            (EssayResult, EssayResult.html_path), (EssayResult, EssayResult.pdf_path)):
        for row in model.query.filter(field.endswith(filename, autoescape=True)).all():
            path = getattr(row, field.key)
            if path and PureWindowsPath(path).name == filename and Path(path).resolve() == target:
                ids.add(row.essay_id)
    if len(ids) != 1:
        abort(404)
    essay = db.session.get(Essay, ids.pop())
    if not can_view_result(current_user, essay):
        abort(403)
    return send_file(target, as_attachment=True)


def assign_submission(essay, student, *, mode='regular', session_id=None, teacher_id=None):
    if mode == 'makeup':
        lesson = next((s for s in makeup_choices(student) if s.session_id == session_id), None)
        if lesson is None or (teacher_id and teacher_id != lesson.course.teacher_id):
            raise ValueError('유효한 보강 수업/날짜/강사를 선택해주세요.')
        essay.user_id = lesson.course.teacher_id
        essay.course_id = lesson.course_id
        essay.session_id = lesson.session_id
        essay.session_assigned_auto = False
    elif mode == 'regular':
        teacher_id = teacher_id or student.teacher_id
        teacher = db.session.get(User, teacher_id) if teacher_id else None
        enrolled = CourseEnrollment.query.join(Course).filter(
            CourseEnrollment.student_id == student.student_id, CourseEnrollment.status == 'active',
            Course.teacher_id == teacher_id, Course.status == 'active', Course.is_terminated.is_(False),
            db.or_(Course.course_type.is_(None), ~Course.course_type.like('보강%'))).first()
        if not teacher or teacher.role != 'teacher' or not teacher.is_active or not (
                enrolled or student.teacher_id == teacher_id):
            raise ValueError('유효한 담당 강사를 선택해주세요.')
        essay.user_id = teacher_id
        from app.utils.essay_utils import auto_assign_essay_session
        auto_assign_essay_session(essay)
    else:
        raise ValueError('유효하지 않은 제출 방식입니다.')
