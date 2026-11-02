"""Opt-in atomic notification writes for a caller-owned DB transaction."""
from contextlib import contextmanager
from app.models import db


@contextmanager
def notification_transaction():
    """Commit records together; dispatch best-effort pushes only after commit.

    Existing callers of Notification.create_notification keep their commit behavior.
    No outbox/retry guarantee is introduced: persisted bell notifications remain
    authoritative if push delivery fails after the database commit.
    """
    key = 'pending_notification_pushes'
    if key in db.session.info:
        raise RuntimeError('Nested notification transactions are unsupported')
    pending = []
    db.session.info[key] = pending
    try:
        yield
        db.session.commit()
    except BaseException:
        db.session.rollback()
        raise
    finally:
        db.session.info.pop(key, None)
    for payload in pending:
        try:
            from app.utils.push_utils import send_push_to_user
            send_push_to_user(**payload)
        except Exception:
            pass  # Bell notification is already committed, as in the legacy helper.
