"""Real learner publication, independent of private editorial/admin storage.
Explicit CLI init/release only. Original signed package/provenance stays unchanged.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,os,sqlite3,time
from .store import Conflict
from .real_source import unpack_real
from .staged_cohorts import initialize_staging,stage_cohort,staged_row,visible

MARKER='reading_quiz.enrolled-learners.v1'
AUDIENCE='authenticated-current-enrolled-student-and-linked-parent-preview'

def checked_root(value):
    if not value or not Path(value).is_absolute(): raise ValueError('Explicit absolute learner root required')
    root=Path(value)
    if root.resolve()!=root or not root.is_dir(): raise ValueError('Existing canonical private root required')
    if any(p.lower() in {'static','uploads','outputs','public','htdocs','www','instance'} for p in root.parts): raise ValueError('Private learner root required')
    marker=root/'.reading-quiz-learners'
    if marker.resolve()!=marker or marker.read_text()!=MARKER: raise ValueError('Dedicated learner marker required')
    return root

@contextmanager
def connect(root,write=False):
    from .publication_fence import lease
    root=checked_root(root)
    with lease(root):
        with _connect_unfenced(root,write) as db:yield db

@contextmanager
def _connect_unfenced(root,write=False):
    root=checked_root(root);path=root/'reading-quiz-learners.sqlite'
    if path.resolve()!=path: raise ValueError('Symlink forbidden')
    if not path.is_file(): raise LookupError('Learner store needs explicit initialization')
    db=sqlite3.connect(path.as_uri()+('?mode=rw' if write else '?mode=ro'),uri=True,timeout=10);db.row_factory=sqlite3.Row
    try:
        if write: db.execute('BEGIN IMMEDIATE')
        yield db
        if write: db.commit()
    except Exception:
        if write: db.rollback()
        raise
    finally: db.close()

def initialize(root):
    # Only called explicitly by CLI. Never from a route, GET or ordinary POST.
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root: raise ValueError('Canonical absolute path required')
    if any(p.lower() in {'static','uploads','outputs','public','htdocs','www','instance'} for p in root.parts): raise ValueError('Private root required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    marker=root/'.reading-quiz-learners'
    if marker.exists(): checked_root(root)
    else:
        fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as out: out.write(MARKER);out.flush();os.fsync(out.fileno())
    path=root/'reading-quiz-learners.sqlite'
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    with connect(root,True) as db:
        db.executescript("""CREATE TABLE revisions(revision_id TEXT PRIMARY KEY,quiz_id TEXT NOT NULL,revision_no INTEGER NOT NULL,title TEXT NOT NULL,bundle_hash TEXT NOT NULL,package BLOB NOT NULL,state TEXT NOT NULL CHECK(state IN ('owner_released','revoked')),UNIQUE(quiz_id,revision_no));
CREATE TABLE owner_releases(revision_id TEXT PRIMARY KEY,package_sha256 TEXT NOT NULL,bundle_hash TEXT NOT NULL,problem_sha256 TEXT NOT NULL,answer_sha256 TEXT NOT NULL,audience TEXT NOT NULL,actor TEXT NOT NULL,authorization TEXT NOT NULL,released_at_ms INTEGER NOT NULL,educational_approval INTEGER NOT NULL CHECK(educational_approval=0));
CREATE TABLE learner_attempts(attempt_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,revision_id TEXT NOT NULL,bundle_hash TEXT NOT NULL,started_at_ms INTEGER NOT NULL,completed_at_ms INTEGER,write_version INTEGER NOT NULL,public_json TEXT NOT NULL,private_json TEXT NOT NULL,answers_json TEXT NOT NULL,submit_key TEXT,result_json TEXT);
CREATE TRIGGER immutable_owner_release_update BEFORE UPDATE ON owner_releases BEGIN SELECT RAISE(ABORT,'Immutable owner authorization');END;
CREATE TRIGGER immutable_owner_release_delete BEFORE DELETE ON owner_releases BEGIN SELECT RAISE(ABORT,'Immutable owner authorization');END;""")


def owner_release(root,packages,authorization,actor):
    if not authorization or not actor: raise ValueError('Explicit owner authorization required')
    prepared=[]
    for raw in packages:
        b,assets,m,_=unpack_real(raw)
        prepared.append((raw,b,m,hashlib.sha256(raw).hexdigest(),hashlib.sha256(assets['problem.pdf']).hexdigest(),hashlib.sha256(assets['answer.pdf']).hexdigest()))
    intent_root=checked_root(root)/'release-intents'
    if intent_root.resolve()!=intent_root: raise ValueError('Intent symlink forbidden')
    intent_root.mkdir(mode=0o700,exist_ok=True)
    import uuid
    intent=dict(actor=actor,authorization=authorization,audience=AUDIENCE,educational_approval=False,created_at_ms=time.time_ns()//1_000_000,
                packages=[dict(revision_id=b['revision_id'],package_sha256=sha,bundle_hash=m['bundle_hash'],problem_sha256=problem,answer_sha256=answer) for _,b,m,sha,problem,answer in prepared])
    fd=os.open(intent_root/(str(uuid.uuid4())+'.json'),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as out:
        json.dump(intent,out,ensure_ascii=False,sort_keys=True);out.flush();os.fsync(out.fileno())
    with connect(root,True) as db:
        for raw,b,m,sha,problem,answer in prepared:
            previous=db.execute('SELECT package FROM revisions WHERE revision_id=?',(b['revision_id'],)).fetchone()
            if previous:
                if previous['package']!=raw: raise Conflict('Immutable real package conflict')
                continue
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?)',(b['revision_id'],b['quiz_id'],b['revision_no'],b['title'],m['bundle_hash'],raw,'owner_released'))
            db.execute('INSERT INTO owner_releases VALUES(?,?,?,?,?,?,?,?,?,0)',(b['revision_id'],sha,m['bundle_hash'],problem,answer,AUDIENCE,actor,authorization,time.time_ns()//1_000_000))
    with connect(root) as db:
        return [dict(db.execute('SELECT * FROM owner_releases WHERE revision_id=?',(b['revision_id'],)).fetchone()) for _,b,_,_,_,_ in prepared]


def verified_row(db,rid):
    row=db.execute('SELECT * FROM revisions WHERE revision_id=?',(rid,)).fetchone()
    if row is None:
        row=staged_row(db,rid)
        if row is None: raise LookupError('Revision not found')
        if not visible(row): raise PermissionError('Scheduled publication unavailable')
        return dict(row)
    audit=db.execute('SELECT * FROM owner_releases WHERE revision_id=?',(rid,)).fetchone()
    if row['state']!='owner_released' or audit is None: raise PermissionError('Publication unavailable')
    if audit['audience']!=AUDIENCE or audit['package_sha256']!=hashlib.sha256(row['package']).hexdigest() or audit['bundle_hash']!=row['bundle_hash']: raise PermissionError('Publication audit mismatch')
    return dict(row)

def get_revision(root,rid):
    with connect(root) as db:
        return verified_row(db,rid)

def revisions(root):
    with connect(root) as db:
        rows=[dict(r) for r in db.execute("SELECT revision_id,quiz_id,revision_no,title,bundle_hash,state,package FROM revisions WHERE state='owner_released' ORDER BY title,revision_no DESC")]
        from .staged_cohorts import has_staging
        if has_staging(db):
            rows += [dict(r) for r in db.execute('SELECT revision_id,quiz_id,revision_no,title,bundle_hash,state,package FROM staged_revisions') if visible(r)]
        from .listing_metadata import week_for_package
        for row in rows:
            row['week']=week_for_package(row.pop('package'))
        return rows
