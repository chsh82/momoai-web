"""Standalone essay-only SQL scope; no student-card routes or schema dependencies."""

def is_hub_admin(actor):
    """Require both a trusted admin role and its explicit level combination.

    Existing admin/2 and master_admin/1 are preserved. manager/2 is an
    explicit policy fixture, not a claim that this role exists in production.
    Numeric role comments are deliberately not used to remap legacy users.
    """
    return (type(getattr(actor, 'role_level', None)) is int
            and type(getattr(actor, 'role', None)) is str) and (actor.role, actor.role_level) in {
        ('master_admin', 1), ('admin', 1), ('admin', 2), ('manager', 2),
    }


def _db():
    from app.models import db
    return db


def _table(name):
    return _db().metadata.tables[name]


def _identity(actor):
    uid = getattr(actor, 'user_id', None)
    return type(uid) is str and bool(uid.strip())


def _admin(actor):
    return _identity(actor) and is_hub_admin(actor)


def _teacher(actor):
    return (_identity(actor) and getattr(actor, 'role', None) == 'teacher'
            and type(getattr(actor, 'role_level', None)) is int
            and actor.role_level in (3, 4))


def enrollment_scope(actor, student_id=None, *, history=False):
    """Safe scalar Select; history is admin-only, never a teacher bypass."""
    import sqlalchemy as sa
    e, c = _table('course_enrollments'), _table('courses')
    query = sa.select(e.c.enrollment_id, e.c.student_id, e.c.course_id,
                      e.c.status, e.c.enrolled_at, e.c.completed_at,
                      c.c.course_name, c.c.course_type, c.c.teacher_id,
                      c.c.status.label('course_status'), c.c.is_terminated).select_from(
                          e.join(c, e.c.course_id == c.c.course_id))
    if not (_admin(actor) or _teacher(actor)):
        query = query.where(sa.false())
    elif not _admin(actor):
        query = query.where(c.c.teacher_id == actor.user_id)
    if not (history and _admin(actor)):
        query = query.where(e.c.status == 'active', c.c.status == 'active', c.c.is_terminated.is_(False))
    if student_id is not None:
        query = query.where(e.c.student_id == student_id)
    return query.execution_options(autoflush=False)


def student_scope(actor):
    """One row per authorized student; use before search/count/page/export."""
    import sqlalchemy as sa
    s = _table('students')
    query = sa.select(s.c.student_id, s.c.name, s.c.grade, s.c.school, s.c.status)
    if not _admin(actor):
        scope = enrollment_scope(actor).subquery()
        query = query.where(s.c.student_id.in_(sa.select(scope.c.student_id)))
    return query.execution_options(autoflush=False)



def original_access_query(actor, kind, source_id=None):
    """Per-essay reads only; other record kinds intentionally unsupported."""
    import sqlalchemy as sa
    if kind != 'essay':
        raise ValueError('Only essay originals are supported')
    from app.services.essay_delivery import essay_acl
    table = _table('essays')
    fields = ('essay_id','student_id','user_id','course_id','session_id','title','status','created_at','completed_at')
    query = sa.select(*(table.c[f] for f in fields)).where(essay_acl(actor, table))
    if source_id is not None:
        query = query.where(table.c.essay_id == source_id)
    return query.execution_options(autoflush=False)
