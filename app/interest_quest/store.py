"""Private lazy SQLite snapshots; never uses the application's current database."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from flask import abort, current_app
from .backend import FORM_VERSION, COPY_VERSION

SCHEMA = '''
CREATE TABLE IF NOT EXISTS attempts (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 attempt_id TEXT UNIQUE NOT NULL, student_id TEXT NOT NULL,
 request_id TEXT NOT NULL, payload TEXT NOT NULL,
 form_version TEXT NOT NULL, copy_version TEXT NOT NULL,
 scoring_version TEXT NOT NULL, representative_rule_version TEXT NOT NULL,
 content_version TEXT NOT NULL, origin TEXT NOT NULL,
 completed_at TEXT NOT NULL, snapshot TEXT NOT NULL,
 UNIQUE(student_id, request_id));
CREATE INDEX IF NOT EXISTS attempts_latest_cohort ON attempts(student_id, form_version, origin, sequence);
CREATE TABLE IF NOT EXISTS presentations (
 attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id), analysis_revision TEXT NOT NULL,
 domain_id TEXT NOT NULL, section TEXT NOT NULL, presented_at TEXT NOT NULL,
 PRIMARY KEY(attempt_id, analysis_revision, domain_id, section));
CREATE TABLE IF NOT EXISTS preferences (
 preference_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
 request_id TEXT NOT NULL, payload TEXT NOT NULL, analysis_revision TEXT NOT NULL,
 displayed_villages_in_order TEXT NOT NULL, selected_village_id TEXT NOT NULL,
 selected_display_position INTEGER NOT NULL, submitted_at_server TEXT NOT NULL,
 revision INTEGER NOT NULL, UNIQUE(attempt_id, request_id), UNIQUE(attempt_id, revision));
'''

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connection(*, write=True):
    """Keep reads on a consistent snapshot without claiming SQLite's writer slot.

    Writes still reserve that slot before checking ownership/latest state, so
    validation and mutation remain atomic. SQLite's busy wait stays bounded.
    """
    db = None
    try:
        path = Path(current_app.config.get('MOMOTOWN_FEEDBACK_DB') or Path(current_app.instance_path)/'momotown-feedback.sqlite3')
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(path), timeout=0.25)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(SCHEMA)
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield db
        db.commit()
    except (sqlite3.Error, OSError):
        if db: db.rollback()
        abort(503, description='Feedback storage temporarily unavailable. Please retry.')
    finally:
        if db: db.close()

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))

def owned(db, attempt_id, student_id):
    row = db.execute('SELECT * FROM attempts WHERE attempt_id=? AND student_id=? AND origin=?',
                     (attempt_id, str(student_id), 'STUDENT')).fetchone()
    if row is None: abort(404)
    require_latest(db, row)
    return row


def require_latest(db, row):
    if db.execute('SELECT 1 FROM attempts WHERE student_id=? AND form_version=? AND origin=? AND sequence>? LIMIT 1',
                  (row['student_id'], row['form_version'], 'STUDENT', row['sequence'])).fetchone():
        abort(409, description='This attempt has been superseded. Start from the current attempt.')

def response_snapshot(db, row):
    """Hydrate the API contract from immutable source data and current acknowledgements."""
    snapshot = json.loads(row['snapshot'])
    snapshot.update(answers=json.loads(row['payload'])['answers'],
                    form_version=row['form_version'], copy_version=row['copy_version'])
    seen = {(r['domain_id'], r['section']) for r in db.execute(
        'SELECT domain_id, section FROM presentations WHERE attempt_id=? AND analysis_revision=?',
        (row['attempt_id'], snapshot['analysis_revision']))}
    snapshot['presentations'] = [dict(domain_id=v, shown_sections=[s for s in ('intro', 'study') if (v, s) in seen])
                                 for v in snapshot['presented_villages'] if any((v, s) in seen for s in ('intro', 'study'))]
    return snapshot


def create(student_id, body, analysis):
    with connection() as db:
        row = db.execute('SELECT * FROM attempts WHERE student_id=? AND request_id=?',
                         (str(student_id), body['request_id'])).fetchone()
        payload = encode(body)
        if row:
            require_latest(db, row)
            if row['payload'] != payload: abort(409)
            return response_snapshot(db, row)
        snapshot = dict(attempt_id=str(uuid4()), analysis_revision=str(uuid4()),
                        analysis=analysis, presented_villages=analysis['representatives'], preference=None)
        db.execute('''INSERT INTO attempts
         (attempt_id, student_id, request_id, payload, form_version, copy_version,
          scoring_version, representative_rule_version, content_version, origin, completed_at, snapshot)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
         (snapshot['attempt_id'], str(student_id), body['request_id'], payload, FORM_VERSION,
          COPY_VERSION, '1.0.0-transparent-choice', 'top3-positive-ratio-domain-order-v1',
          COPY_VERSION, 'STUDENT', now(), encode(snapshot)))
        return response_snapshot(db, owned(db, snapshot['attempt_id'], student_id))

def restore(student_id, attempt_id):
    with connection(write=False) as db:
        return response_snapshot(db, owned(db, attempt_id, student_id))


def presentation(student_id, attempt_id, body):
    with connection() as db:
        snapshot = json.loads(owned(db, attempt_id, student_id)['snapshot'])
        if body['analysis_revision'] != snapshot['analysis_revision']: abort(409)
        if body['domain_id'] not in snapshot['presented_villages']: abort(400)
        sections = body['sections']
        if not isinstance(sections, list) or not sections or len(sections) > 2 or any(not isinstance(s,str) or s not in ('intro','study') for s in sections): abort(400)
        for section in sections:
            db.execute('INSERT OR IGNORE INTO presentations VALUES (?,?,?,?,?)',
                       (attempt_id, snapshot['analysis_revision'], body['domain_id'], section, now()))
        return response_snapshot(db, owned(db, snapshot['attempt_id'], student_id))


def preference(student_id, attempt_id, body):
    with connection() as db:
        snapshot = json.loads(owned(db, attempt_id, student_id)['snapshot'])
        if body['analysis_revision'] != snapshot['analysis_revision']: abort(409)
        villages = snapshot['presented_villages']
        if body['selected_village_id'] not in villages: abort(400)
        old = db.execute('SELECT payload FROM preferences WHERE attempt_id=? AND request_id=?',
                         (attempt_id, body['request_id'])).fetchone()
        if old:
            if old['payload'] != encode(body): abort(409)
            return response_snapshot(db, owned(db, snapshot['attempt_id'], student_id))
        seen = {(r['domain_id'], r['section']) for r in db.execute(
            'SELECT domain_id, section FROM presentations WHERE attempt_id=? AND analysis_revision=?',
            (attempt_id, snapshot['analysis_revision']))}
        if len(villages) != 3 or not all((v,s) in seen for v in villages for s in ('intro','study')): abort(409)
        revision = db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM preferences WHERE attempt_id=?', (attempt_id,)).fetchone()[0]
        saved = dict(preference_id=str(uuid4()), analysis_revision=snapshot['analysis_revision'],
                     displayed_villages_in_order=villages, selected_village_id=body['selected_village_id'],
                     selected_display_position=villages.index(body['selected_village_id'])+1,
                     submitted_at_server=now(), revision=revision)
        db.execute('INSERT INTO preferences VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (saved['preference_id'],attempt_id,body['request_id'],encode(body),saved['analysis_revision'],
                    encode(villages),saved['selected_village_id'],saved['selected_display_position'],
                    saved['submitted_at_server'],revision))
        snapshot['preference'] = saved
        db.execute('UPDATE attempts SET snapshot=? WHERE attempt_id=?', (encode(snapshot),attempt_id))
        return response_snapshot(db, owned(db, snapshot['attempt_id'], student_id))


def lookup(filters):
    """Bound both SQL result size and identity lookups; never include preview rows."""
    conditions = ["a.origin='STUDENT'"]
    values = []
    latest_condition = "a.sequence=(SELECT MAX(b.sequence) FROM attempts b WHERE b.student_id=a.student_id AND b.form_version=a.form_version AND b.origin='STUDENT')"
    if filters.get('history', '0') != '1':
        conditions.append(latest_condition)
    for key, column in (('student','student_id'),('form_version','form_version'),('copy_version','copy_version')):
        if filters.get(key):
            conditions.append('a.'+column+'=?')
            values.append(filters[key])
    for key, op in (('date_from','>='),('date_to','<=')):
        if filters.get(key):
            conditions.append('substr(a.completed_at,1,10)'+op+'?')
            values.append(filters[key])
    status = filters.get('status','')
    if status:
        conditions.append(('EXISTS' if status=='completed' else 'NOT EXISTS')+' (SELECT 1 FROM preferences p WHERE p.attempt_id=a.attempt_id)')
    limit = int(filters.get('limit','100'))
    offset = int(filters.get('offset','0'))
    with connection(write=False) as db:
        # Aggregates cover the filtered latest cohort, independently of row
        # pagination/history. Only scalar totals and bounded categorical groups
        # leave SQLite; no unbounded snapshots or identity lookups are loaded.
        cohort_conditions = list(conditions)
        if latest_condition not in cohort_conditions:
            cohort_conditions.append(latest_condition)
        cohort = ' FROM attempts a WHERE '+' AND '.join(cohort_conditions)
        totals = db.execute('SELECT COUNT(*) AS attempts, COUNT(DISTINCT a.student_id) AS students, '
                            "COALESCE(SUM(json_extract(a.snapshot,'$.preference.preference_id') IS NOT NULL),0) AS completed"+cohort, values).fetchone()
        summary = dict(totals)
        summary['pending'] = summary['attempts'] - summary['completed']
        for field, key in (('selected_village_id', 'selected_villages'), ('selected_display_position', 'selected_display_positions')):
            groups = db.execute("SELECT json_extract(a.snapshot,'$.preference."+field+"') AS category, COUNT(*) AS n"+cohort+
                                " AND json_extract(a.snapshot,'$.preference.preference_id') IS NOT NULL GROUP BY category", values).fetchall()
            summary[key] = {str(r['category']): r['n'] for r in groups}
        rows = db.execute('SELECT a.* FROM attempts a WHERE '+' AND '.join(conditions)+' ORDER BY a.sequence DESC LIMIT ? OFFSET ?', values+[limit+1,offset]).fetchall()
    results = []
    for row in rows[:limit]:
        snapshot = json.loads(row['snapshot'])
        from app.models import Student
        students = Student.query.filter_by(student_id=row['student_id']).all()
        name = students[0].name if len(students)==1 else None
        units = max(d['comparison_units'] for d in snapshot['analysis']['domains'])
        ties = [d['domain_id'] for d in snapshot['analysis']['domains'] if d['comparison_units']==units]
        results.append(dict(snapshot, student_id=row['student_id'], student_name=name,
                            form_version=row['form_version'],copy_version=row['copy_version'],
                            scoring_version=row['scoring_version'],content_version=row['content_version'],
                            representative_rule_version=row['representative_rule_version'],
                            completed_at=row['completed_at'],
                            status='completed' if snapshot['preference'] else 'pending',
                            top_tied_villages=ties,
                            presented_ties=[[d['domain_id'] for d in snapshot['analysis']['domains']
                                             if d['comparison_units']==next(x['comparison_units'] for x in snapshot['analysis']['domains'] if x['domain_id']==v)]
                                            for v in snapshot['presented_villages']]))
    return dict(rows=results, summary=summary, has_more=len(rows)>limit, limit=limit, offset=offset)
