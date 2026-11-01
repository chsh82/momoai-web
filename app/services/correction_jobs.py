"""Durable correction generations and transaction-local write fencing.

No writer lock spans inference. Every flush/commit rechecks generation + SQL ACL
under the same essay mutex used by cancellation/transfer. Files are fenced before
publication and use generation-specific names, never an old result's path.
"""
from contextlib import contextmanager
from functools import wraps
import uuid
import sqlalchemy as sa
from app.models import db, Essay, User
from app.models.essay import EssayCorrectionJob


class StaleCorrection(RuntimeError):
    pass


def invalidate(essay_id):
    table = EssayCorrectionJob.__table__
    db.session.execute(sa.update(table).where(table.c.essay_id == essay_id)
        .values(state='cancelled', revision_note=None))


def claim(actor, essay, revision_note=None, session=None):
    from app.services.essay_delivery import lock_essay, essay_acl
    session = session if session is not None else db.session
    table = Essay.__table__
    with session.no_autoflush:
        status = lock_essay(essay.essay_id, session=session)
        if not session.execute(sa.select(table.c.essay_id).where(
                table.c.essay_id == essay.essay_id, essay_acl(actor, table, write=True))).first():
            raise PermissionError('첨삭 담당이 변경되었습니다.')
        if status == 'processing':
            raise ValueError('이미 첨삭 생성 중입니다.')
        job = session.get(EssayCorrectionJob, essay.essay_id)
        if job is None:
            job = EssayCorrectionJob(essay_id=essay.essay_id)
            session.add(job)
        job.job_id = str(uuid.uuid4())
        job.actor_id = actor.user_id
        job.state = 'prepared' if revision_note is not None else 'dispatched'
        job.revision_note = revision_note
        session.execute(sa.update(table).where(table.c.essay_id == essay.essay_id).values(status='processing'))
        session.expire(essay, ['status'])
        return job.job_id


def dispatch(actor, essay):
    from app.services.essay_delivery import lock_essay, can_correct
    status = lock_essay(essay.essay_id)
    job = db.session.get(EssayCorrectionJob, essay.essay_id, populate_existing=True)
    if not can_correct(actor, essay):
        raise PermissionError('첨삭 담당이 변경되었습니다.')
    if status != 'processing' or job is None or job.state != 'prepared' or job.actor_id != actor.user_id:
        raise ValueError('유효한 재생성 요청이 없습니다.')
    note = job.revision_note
    job.state = 'dispatched'
    job.revision_note = None
    return job.job_id, note


def checkpoint(session=None):
    """Lock + verify before each write; caller commits promptly, before inference."""
    from app.services.essay_delivery import lock_essay, essay_acl
    session = session if session is not None else db.session()
    identity = session.info.get('correction_generation')
    if identity is None:
        return
    essay_id, job_id, actor_id = identity
    table = EssayCorrectionJob.__table__
    with session.no_autoflush:
        lock_essay(essay_id, session=session)
        valid = session.execute(sa.select(table.c.job_id).where(table.c.essay_id == essay_id,
            table.c.job_id == job_id, table.c.actor_id == actor_id, table.c.state == 'running')).first()
        actor = session.get(User, actor_id, populate_existing=True)
        allowed = actor and session.execute(sa.select(Essay.__table__.c.essay_id).where(
            Essay.__table__.c.essay_id == essay_id, essay_acl(actor, Essay.__table__, write=True))).first()
        if not valid or not allowed:
            raise StaleCorrection('취소되었거나 담당이 변경된 첨삭 작업입니다.')


def file_name(filename):
    checkpoint()
    identity = db.session.info.get('correction_generation')
    if identity:
        from pathlib import Path
        path = Path(filename)
        return f'{path.stem}_{identity[1]}{path.suffix}'
    return filename


@contextmanager
def worker_generation(essay_id, job_id):
    from app.services.essay_delivery import lock_essay
    session = db.session()
    lock_essay(essay_id)
    job = session.get(EssayCorrectionJob, essay_id, populate_existing=True)
    if job is None or job.job_id != job_id or job.state != 'dispatched':
        session.rollback()
        raise StaleCorrection('유효한 대기 작업이 없습니다.')
    job.state = 'running'
    session.flush()
    session.info['correction_generation'] = (essay_id, job_id, job.actor_id)
    def before_flush(s, *args): checkpoint(s)
    def before_commit(s): checkpoint(s)
    sa.event.listen(session, 'before_flush', before_flush)
    sa.event.listen(session, 'before_commit', before_commit)
    try:
        checkpoint(session)
        session.commit()  # release writer before any network/service construction
        yield
        checkpoint(session)
        job = session.get(EssayCorrectionJob, essay_id, populate_existing=True)
        # Remove guards only after the last guarded write, while retaining mutex.
        session.flush()
        sa.event.remove(session, 'before_flush', before_flush)
        sa.event.remove(session, 'before_commit', before_commit)
        job.state = 'finished'
        session.commit()
    finally:
        for event, listener in [('before_flush', before_flush), ('before_commit', before_commit)]:
            if sa.event.contains(session, event, listener):
                sa.event.remove(session, event, listener)
        session.info.pop('correction_generation', None)
        session.rollback()


def fenced_worker(app, essay_id, job_id):
    """Wrap every route worker, including failure/notification commits."""
    def decorate(fn):
        @wraps(fn)
        def run():
            with app.app_context():
                try:
                    with worker_generation(essay_id, job_id):
                        # Existing workers must use this same app context/session.
                        fn()
                except StaleCorrection:
                    db.session.rollback()
        return run
    return decorate
