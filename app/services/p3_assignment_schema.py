"""Independent assignment rehearsal schema. No app imports or global registry."""
from sqlalchemy import (MetaData, Table, Column, Text, Integer, ForeignKey,
                        ForeignKeyConstraint, UniqueConstraint, CheckConstraint)


def build_schema(actual):
    """Bind foreign keys to actual Columns without mutating actual metadata."""
    m = MetaData()
    def text(name, nullable=False, primary_key=False):
        return Column(name, Text, nullable=nullable, primary_key=primary_key)
    def ref(name, table, target):
        return Column(name, Text, ForeignKey(actual.tables[table].c[target], ondelete='RESTRICT'), nullable=False)
    def digest(name):
        return CheckConstraint(f"length({name})=64 AND {name} NOT GLOB '*[^0-9a-f]*'")
    r = Table('br_assignment_revisions', m,
        text('revision_id', primary_key=True),
        ref('submission_id', 'assignment_submissions', 'submission_id'),
        Column('revision_no', Integer, nullable=False), text('parent_revision_id', nullable=True),
        ref('actor_user_id', 'users', 'user_id'), text('content'), text('file_manifest'),
        text('payload_digest'), text('legacy_snapshot'), text('legacy_digest'),
        ref('enrollment_id', 'course_enrollments', 'enrollment_id'),
        ref('course_id', 'courses', 'course_id'),
        Column('session_id', Text, ForeignKey(actual.tables['course_sessions'].c.session_id, ondelete='RESTRICT'), nullable=True),
        text('scope_state'), text('program_id', nullable=True), text('edition_id', nullable=True),
        text('rubric_id', nullable=True), text('captured_at'),
        CheckConstraint("typeof(revision_no)='integer' AND revision_no>=1"),
        CheckConstraint("scope_state IN ('explicit_scope_checked','unknown')"),
        CheckConstraint('program_id IS NULL AND edition_id IS NULL AND rubric_id IS NULL'),
        digest('payload_digest'), digest('legacy_digest'),
        UniqueConstraint('submission_id', 'revision_no', name='uq_br_revision_no'),
        UniqueConstraint('submission_id', 'revision_id', name='uq_br_revision_target'))
    r.append_constraint(ForeignKeyConstraint([r.c.submission_id, r.c.parent_revision_id],
        [r.c.submission_id, r.c.revision_id], name='fk_br_revision_parent', ondelete='RESTRICT'))
    h = Table('br_assignment_heads', m,
        ref('submission_id', 'assignment_submissions', 'submission_id'), text('revision_id'),
        Column('generation', Integer, nullable=False), text('legacy_digest'),
        CheckConstraint("typeof(generation)='integer' AND generation>=1"), digest('legacy_digest'))
    h.c.submission_id.primary_key = True
    from sqlalchemy import PrimaryKeyConstraint
    h.append_constraint(PrimaryKeyConstraint(h.c.submission_id))
    h.append_constraint(ForeignKeyConstraint([h.c.submission_id, h.c.revision_id],
        [r.c.submission_id, r.c.revision_id], name='fk_br_head_revision', ondelete='RESTRICT'))
    c = Table('br_assignment_receipts', m,
        text('command_id', primary_key=True), ref('actor_user_id', 'users', 'user_id'),
        text('idempotency_key'), ref('assignment_id', 'assignments', 'assignment_id'),
        ref('submission_id', 'assignment_submissions', 'submission_id'), text('revision_id'),
        text('request_digest'), Column('response_status', Integer, nullable=False),
        text('response_body'), text('committed_at'), digest('request_digest'),
        CheckConstraint('length(idempotency_key) BETWEEN 1 AND 128'),
        CheckConstraint('response_status IN (200,201)'),
        UniqueConstraint('actor_user_id', 'idempotency_key', name='uq_br_actor_key'),
        UniqueConstraint('revision_id', name='uq_br_receipt_revision'))
    c.append_constraint(ForeignKeyConstraint([c.c.submission_id, c.c.revision_id],
        [r.c.submission_id, r.c.revision_id], name='fk_br_receipt_revision', ondelete='RESTRICT'))
    Table('br_assignment_outbox', m, text('event_id', primary_key=True),
        Column('command_id', Text, ForeignKey(c.c.command_id, ondelete='RESTRICT'), nullable=False),
        ref('recipient_user_id', 'users', 'user_id'),
        Column('notification_id', Text, ForeignKey(actual.tables['notifications'].c.notification_id, ondelete='RESTRICT'), nullable=False, unique=True),
        text('event_type'), text('payload'), text('delivery_state'),
        Column('attempt_count', Integer, nullable=False), text('created_at'),
        CheckConstraint("event_type='assignment_submitted'"),
        CheckConstraint("delivery_state='pending'"), CheckConstraint("typeof(attempt_count)='integer' AND attempt_count=0"),
        UniqueConstraint('command_id', 'recipient_user_id', 'event_type', name='uq_br_outbox_event'))
    return m


def trigger_sql():
    """Exact closed trigger inventory for immutable rows and legal HEAD lineage."""
    rules = {'revisions': ['insert_conflict','update','delete','lineage_insert'],
             'heads': ['insert_conflict','delete','transition_insert','transition_update'],
             'receipts': ['insert_conflict','update','delete'],
             'outbox': ['insert_conflict','update','delete']}
    result = {}
    for suffix, names in rules.items():
        table = 'br_assignment_' + suffix
        for rule in names:
            verb = 'UPDATE' if rule in ('update', 'transition_update') else 'DELETE' if rule == 'delete' else 'INSERT'
            name = table + '_' + rule + '_guard'
            result[name] = f"CREATE TRIGGER {name} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT, '{rule}'); END"
    def guard(suffix, rule, condition):
        table = 'br_assignment_' + suffix
        name = table + '_' + rule + '_guard'
        verb = 'UPDATE' if rule == 'transition_update' else 'INSERT'
        if rule == 'lineage_insert':
            condition = "NOT EXISTS(SELECT 1 FROM br_assignment_revisions WHERE revision_id=NEW.revision_id OR (submission_id=NEW.submission_id AND revision_no=NEW.revision_no)) AND (" + condition + ")"
        elif rule == 'transition_insert':
            condition = "NOT EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id) AND (" + condition + ")"
        result[name] = f"CREATE TRIGGER {name} BEFORE {verb} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, '{rule}'); END"
    guard('revisions', 'insert_conflict', "EXISTS(SELECT 1 FROM br_assignment_revisions WHERE revision_id=NEW.revision_id OR (submission_id=NEW.submission_id AND revision_no=NEW.revision_no))")
    guard('revisions', 'lineage_insert', "NOT ((NEW.revision_no=1 AND NEW.parent_revision_id IS NULL AND NOT EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id)) OR (NEW.revision_no>1 AND NEW.parent_revision_id IS NOT NULL AND NEW.parent_revision_id != NEW.revision_id AND EXISTS(SELECT 1 FROM br_assignment_heads h JOIN br_assignment_revisions p ON p.revision_id=h.revision_id AND p.submission_id=h.submission_id WHERE h.submission_id=NEW.submission_id AND h.generation=NEW.revision_no-1 AND h.revision_id=NEW.parent_revision_id AND p.revision_no=NEW.revision_no-1)))")
    guard('heads', 'insert_conflict', "EXISTS(SELECT 1 FROM br_assignment_heads WHERE submission_id=NEW.submission_id)")
    guard('heads', 'transition_insert', "NEW.generation != 1 OR NOT EXISTS(SELECT 1 FROM br_assignment_revisions r WHERE r.submission_id=NEW.submission_id AND r.revision_id=NEW.revision_id AND r.revision_no=1 AND r.parent_revision_id IS NULL AND r.legacy_digest=NEW.legacy_digest)")
    guard('heads', 'transition_update', "NEW.submission_id != OLD.submission_id OR NEW.generation != OLD.generation+1 OR NOT EXISTS(SELECT 1 FROM br_assignment_revisions r WHERE r.submission_id=NEW.submission_id AND r.revision_id=NEW.revision_id AND r.revision_no=NEW.generation AND r.parent_revision_id=OLD.revision_id AND r.legacy_digest=NEW.legacy_digest)")
    guard('receipts', 'insert_conflict', "EXISTS(SELECT 1 FROM br_assignment_receipts WHERE command_id=NEW.command_id OR (actor_user_id=NEW.actor_user_id AND idempotency_key=NEW.idempotency_key) OR revision_id=NEW.revision_id)")
    guard('outbox', 'insert_conflict', "EXISTS(SELECT 1 FROM br_assignment_outbox WHERE event_id=NEW.event_id OR notification_id=NEW.notification_id OR (command_id=NEW.command_id AND recipient_user_id=NEW.recipient_user_id AND event_type=NEW.event_type))")
    return result
