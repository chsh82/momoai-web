"""Real Flask blueprint/private SQLite tests; no application factory."""
import sys
import types
import json
from pathlib import Path
from uuid import uuid4
import pytest
from flask import Flask, session
from flask_login import LoginManager, UserMixin
ROOT = Path(__file__).resolve().parents[2]
if 'app' not in sys.modules:
    package = types.ModuleType('app')
    package.__path__ = [str(ROOT/'app')]
    sys.modules['app'] = package
from app.interest_quest import interest_quest_bp
BASE = '/student/interest-quest'
VERSION = '1.0.0-draft1+interest-only-momotown-v02'
class Identity(UserMixin):
    def __init__(self, uid):
        self.id = uid
        self.role = session.get('role', 'student')
        self.is_admin = self.role == 'admin'
    @property
    def is_active(self):
        return session.get('active', True)
@pytest.fixture
def web(tmp_path):
    app = Flask('momotown-test', template_folder=str(ROOT/'templates'))
    app.config.update(TESTING=True, SECRET_KEY='test-only', STUDENT_INTEREST_QUEST_ENABLED=True,
                      MOMOTOWN_FEEDBACK_DB=str(tmp_path/'feedback.sqlite3'))
    manager = LoginManager(app)
    manager.user_loader(lambda uid: Identity(uid))
    app.add_url_rule('/login', 'auth.login', lambda:'login')
    app.register_blueprint(interest_quest_bp, url_prefix=BASE)
    client = app.test_client()
    identify(client)
    # Only model lookup is stubbed; identity authorization remains real.
    models = types.ModuleType('app.models')
    class Query:
        def filter_by(self, **kwargs):
            assert set(kwargs) <= {'user_id', 'student_id'}, 'Student PK is student_id, not id'
            self.kwargs = kwargs
            return self
        def all(self):
            return [types.SimpleNamespace(student_id='s1', name='<script>학생</script>')]
    models.Student = type('Student', (), {'query': Query()})
    old = sys.modules.get('app.models')
    sys.modules['app.models'] = models
    yield app, client, models
    if old is None: sys.modules.pop('app.models', None)
    else: sys.modules['app.models'] = old

def identify(client, role='student', uid='u1', active=True):
    with client.session_transaction() as s:
        s.clear()
        if role: s.update(_user_id=uid, role=role, active=active)

def canonical():
    text = (ROOT/'app/interest_quest/protected/index.html').read_text(encoding='utf-8')
    return json.JSONDecoder().raw_decode(text.split('const FORM=',1)[1])[0]

def payload():
    return dict(request_id=str(uuid4()), form_version=VERSION,
                answers=[item['options'][0]['id'] for item in canonical()['items']])

def post(c, path, data):
    token = c.get(BASE+'/context').get_json()['csrf_token']
    return c.post(BASE+path, json=data, headers={'X-CSRFToken':token})

def test_attempt_snapshot_idempotency_restore(web):
    app,c,_ = web
    body = payload()
    response = post(c, '/attempts', body)
    assert response.status_code == 200
    data = response.get_json()
    assert data['preference'] is None
    form = canonical()
    expected = []
    for i,d in enumerate(form['domains']):
        offered = sum(o['weight'] for item in form['items'] for o in item['options'] if o['domain_id']==d['id'])
        count = sum(item['options'][0]['weight'] for item in form['items'] if item['options'][0]['domain_id']==d['id'])
        expected.append(dict(domain_id=d['id'], selected_count=count, offered_count=offered,
                             comparison_units=count*210//offered, display_order=i))
    assert data['analysis']['domains'] == expected
    reps = [r['domain_id'] for r in sorted(expected, key=lambda r:(-r['comparison_units'],r['display_order'])) if r['selected_count']>0][:3]
    assert data['analysis']['representatives'] == data['presented_villages'] == reps
    assert post(c,'/attempts',body).get_json() == data
    assert c.get(BASE+'/attempts/'+data['attempt_id']).get_json() == data
    body['answers'][0] = form['items'][0]['options'][1]['id']
    assert post(c,'/attempts',body).status_code == 409
    import sqlite3
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        assert db.execute('select count(*) from attempts').fetchone()[0] == 1
        assert '<script>' not in str(db.execute('select * from attempts').fetchall())

def test_preference_seen_gate_history_unchanged_analysis(web):
    app,c,_ = web
    data = post(c,'/attempts',payload()).get_json()
    path = '/attempts/'+data['attempt_id']
    pref = dict(request_id=str(uuid4()), analysis_revision=data['analysis_revision'],
                selected_village_id=data['presented_villages'][0])
    assert post(c,path+'/preference',pref).status_code == 409
    for domain in data['presented_villages']:
        for sections in (['intro'], ['study']):
            response = post(c,path+'/presentation',dict(analysis_revision=data['analysis_revision'],domain_id=domain,sections=sections))
            assert response.status_code == 200
    response = post(c,path+'/preference',pref)
    assert response.status_code == 200
    saved = response.get_json()
    assert saved['analysis'] == data['analysis']
    assert saved['presented_villages'] == data['presented_villages']
    assert saved['preference']['selected_village_id'] == pref['selected_village_id']
    assert saved['preference']['selected_display_position'] == 1
    assert post(c,path+'/preference',pref).get_json() == saved
    changed = dict(pref, request_id=str(uuid4()),selected_village_id=data['presented_villages'][1])
    latest = post(c,path+'/preference',changed).get_json()
    assert latest['preference']['revision'] == 2
    assert c.get(BASE+path).get_json() == latest
    # Retrying the older request must not undo the latest choice.
    assert post(c,path+'/preference',pref).get_json() == latest
    assert post(c,path+'/preference',dict(pref,selected_village_id=changed['selected_village_id'])).status_code == 409
    assert post(c,path+'/preference',dict(changed,analysis_revision=str(uuid4()))).status_code == 409
    other = post(c,'/attempts',payload()).get_json()
    assert other['analysis_revision'] != data['analysis_revision'] and other['preference'] is None
    newpref = dict(pref,request_id=str(uuid4()),analysis_revision=other['analysis_revision'])
    assert post(c,'/attempts/'+other['attempt_id']+'/preference',newpref).status_code == 409
    import sqlite3
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        assert db.execute('select count(*) from preferences').fetchone()[0] == 2

def test_admin_lookup_filters_preview_exclusion_xss(web):
    app,c,_ = web
    identify(c,'admin')
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    assert c.get(BASE+'/feedback.json').status_code == 200
    assert c.get(BASE+'/feedback.json').get_json()['rows'] == []
    identify(c)
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = True
    old = post(c,'/attempts',payload()).get_json()
    latest = post(c,'/attempts',payload()).get_json()
    identify(c,'admin')
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    data = c.get(BASE+'/feedback.json').get_json()
    assert len(data['rows']) == 1 and data['rows'][0]['attempt_id'] == latest['attempt_id']
    row = data['rows'][0]
    assert row['student_id'] == 's1' and row['student_name'] == '<script>학생</script>'
    assert row['status'] == 'pending' and row['preference'] is None
    assert row['presented_villages'] == latest['presented_villages']
    assert isinstance(row['top_tied_villages'],list)
    assert len(c.get(BASE+'/feedback.json?history=1').get_json()['rows']) == 2
    for query in ('student=other','form_version=old','copy_version=old','status=completed','date_from=2099-01-01','date_to=2000-01-01'):
        assert c.get(BASE+'/feedback.json?'+query).get_json()['rows'] == []
    for query in ('limit=10000','date_from=not-date','status=bad','student='+('x'*129),'unknown=1'):
        assert c.get(BASE+'/feedback.json?'+query).status_code == 400
    html = c.get(BASE+'/feedback').get_data(as_text=True)
    assert '<script>학생</script>' not in html and '&lt;script&gt;' in html
    assert '<label' in html and '<caption' in html
    import sqlite3
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        db.execute('UPDATE attempts SET origin=? WHERE attempt_id=?', ('ADMIN_PREVIEW',latest['attempt_id']))
    data = c.get(BASE+'/feedback.json').get_json()
    assert len(data['rows']) == 1 and data['rows'][0]['attempt_id'] == old['attempt_id']

@pytest.mark.parametrize('flag',[False,True])
@pytest.mark.parametrize('role,active',[(None,True),('student',True),('student',False),('admin',True),('admin',False),('master_admin',True),('parent',True),('teacher',True),('manager',True)])
def test_permissions_matrix(web,flag,role,active):
    app,c,_ = web
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = flag
    identify(c,role,active=active)
    admin = role in ('admin','master_admin') and active
    student = role=='student' and active and flag
    assert (c.get(BASE+'/context').status_code==200) == (admin or student)
    assert (c.get(BASE+'/feedback.json').status_code==200) == admin
    response = c.post(BASE+'/attempts',json=payload(),headers={'X-CSRFToken':'forged'})
    assert response.status_code != 200
    if not student: assert response.status_code in (302,403)

@pytest.mark.parametrize('links',[[],[types.SimpleNamespace(student_id='a',name='A'),types.SimpleNamespace(student_id='b',name='B')],[types.SimpleNamespace(student_id='a',name='')]])
def test_missing_duplicate_blank_student_link(web,monkeypatch,links):
    _,c,models = web
    monkeypatch.setattr(models.Student.query,'all',lambda:links)
    assert c.get(BASE+'/context').status_code == 409
    assert c.post(BASE+'/attempts',json=payload()).status_code == 409

def test_csrf_strict_fields_payload_limits(web):
    app,c,_ = web
    body = payload()
    assert c.post(BASE+'/attempts',json=body).status_code == 400
    assert c.post(BASE+'/attempts',json=body,headers={'X-CSRFToken':'forged'}).status_code == 400
    for field in ('reason','reason_text','reason_code','student_id','name','role','analysis','scores'):
        assert post(c,'/attempts',dict(body,**{field:'bad'})).status_code == 400
    for malformed in (dict(body,request_id='../../bad'),dict(body,request_id='x'*1000),dict(body,request_id=[]),dict(body,form_version='old'),dict(body,answers=body['answers'][:-1]),dict(body,answers=[body['answers'][0]]*32),dict(body,answers=[{}]*32),dict(body,answers=[None]*32)):
        assert post(c,'/attempts',malformed).status_code == 400
    token = c.get(BASE+'/context').get_json()['csrf_token']
    assert c.post(BASE+'/attempts',data='x'*17000,headers={'X-CSRFToken':token,'Content-Type':'application/json'}).status_code == 413
    assert not Path(app.config['MOMOTOWN_FEEDBACK_DB']).exists()

def test_ownership_no_reason_and_invalid_candidates(web,monkeypatch):
    _,c,models = web
    data = post(c,'/attempts',payload()).get_json()
    path = '/attempts/'+data['attempt_id']
    pref = dict(request_id=str(uuid4()),analysis_revision=data['analysis_revision'],selected_village_id=data['presented_villages'][0])
    shown = dict(analysis_revision=data['analysis_revision'],domain_id=data['presented_villages'][0],sections=['intro','study'])
    for suffix,body in (('/preference',pref),('/presentation',shown)):
        assert c.post(BASE+path+suffix,json=body).status_code == 400
        assert c.post(BASE+path+suffix,json=body,headers={'X-CSRFToken':'bad'}).status_code == 400
        assert post(c,path+suffix,dict(body,reason_text='forbidden')).status_code == 400
    assert post(c,path+'/preference',dict(pref,selected_village_id='not-a-village')).status_code == 400
    assert post(c,path+'/presentation',dict(shown,domain_id='not-a-village')).status_code == 400
    for sections in ([],['intro','evil'],[{}],'intro'):
        assert post(c,path+'/presentation',dict(shown,sections=sections)).status_code == 400
    assert post(c,path+'/presentation',dict(shown,analysis_revision=str(uuid4()))).status_code == 409
    for bad in ('bad','x'*1000,'%27%20OR%201=1'):
        assert c.get(BASE+'/attempts/'+bad).status_code == 400
    monkeypatch.setattr(models.Student.query,'all',lambda:[types.SimpleNamespace(student_id='s2',name='other')])
    assert c.get(BASE+path).status_code == 404
    assert post(c,path+'/presentation',shown).status_code == 404
    assert post(c,path+'/preference',pref).status_code == 404

def test_private_cache_headers(web):
    _,c,_ = web
    data = post(c,'/attempts',payload()).get_json()
    assert c.get(BASE+'/attempts/'+data['attempt_id']).headers['Cache-Control'] == 'private, no-store'
    identify(c,'admin')
    for suffix in ('/feedback','/feedback.json'):
        assert c.get(BASE+suffix).headers['Cache-Control'] == 'private, no-store'

def test_storage_busy_io_errors_are_retryable(web):
    app,c,_ = web
    data = post(c,'/attempts',payload()).get_json()
    import sqlite3
    db = sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB'])
    try:
        db.execute('BEGIN EXCLUSIVE')
        response = post(c,'/attempts',payload())
        assert response.status_code == 503 and b'sqlite' not in response.data
    finally:
        db.rollback();db.close()
    app.config['MOMOTOWN_FEEDBACK_DB'] = str(Path(app.config['MOMOTOWN_FEEDBACK_DB']).parent)
    response = c.get(BASE+'/attempts/'+data['attempt_id'])
    assert response.status_code == 503 and b'Traceback' not in response.data

def test_scoring_parity_against_actual_javascript_with_ties(web):
    import random, subprocess, shutil
    assert shutil.which('node'), 'Node is required for parity against the actual immutable scorer'
    _,c,_ = web
    form = canonical()
    rng = random.Random(20261027)
    cases = [[item['options'][rng.randrange(4)]['id'] for item in form['items']] for _ in range(32)]
    text = (ROOT/'app/interest_quest/protected/index.html').read_text(encoding='utf-8')
    start = text.index("(function(root){'use strict';")
    end = text.index("})(typeof globalThis!=='undefined'?globalThis:this);",start)+len("})(typeof globalThis!=='undefined'?globalThis:this);")
    # Run only the literal scorer, never the page or application factory.
    script = text[start:end]+"\nconst fs=require('fs');const {form,cases}=JSON.parse(fs.readFileSync(0,'utf8')); console.log(JSON.stringify(cases.map(answers=>InterestScoring.score(answers.map((id,i)=>({item_id:form.items[i].id,option_id:id})),form).domains)));"
    output = subprocess.run(['node','-e',script],input=json.dumps(dict(form=form,cases=cases)),text=True,capture_output=True,check=True,encoding='utf-8')
    expected = json.loads(output.stdout)
    tied = False
    for answers, rows in zip(cases,expected):
        data = post(c,'/attempts',dict(payload(),answers=answers)).get_json()
        fields = ('domain_id','selected_count','offered_count','comparison_units','display_order')
        assert data['analysis']['domains'] == [{k:r[k] for k in fields} for r in rows]
        ranking = sorted([r for r in rows if r['selected_count']>0],key=lambda r:(-r['comparison_units'],r['display_order']))
        assert data['presented_villages'] == [r['domain_id'] for r in ranking[:3]]
        tied |= any(a['comparison_units']==b['comparison_units'] for a,b in zip(ranking,ranking[1:]))
    assert tied, 'Fixture must exercise exact ratio ties'

def test_scope_flags_on_every_attempt_api(web):
    app,c,_ = web
    data = post(c,'/attempts',payload()).get_json()
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    path = BASE+'/attempts/'+data['attempt_id']
    assert c.get(path).status_code == 403
    for suffix in ('/presentation','/preference'):
        assert c.post(path+suffix,json={}).status_code == 403
    identify(c,'admin')
    assert c.get(path).status_code == 403
    for suffix in ('/presentation','/preference'):
        assert c.post(path+suffix,json={}).status_code == 403

def test_admin_completed_lookup_pagination_schema_no_reasons(web):
    app,c,_ = web
    data = post(c,'/attempts',payload()).get_json()
    path = '/attempts/'+data['attempt_id']
    for village in data['presented_villages']:
        assert post(c,path+'/presentation',dict(analysis_revision=data['analysis_revision'],domain_id=village,sections=['intro','study'])).status_code == 200
    saved = post(c,path+'/preference',dict(analysis_revision=data['analysis_revision'],request_id=str(uuid4()),selected_village_id=data['presented_villages'][2])).get_json()
    identify(c,'admin')
    rows = c.get(BASE+'/feedback.json?status=completed').get_json()['rows']
    assert len(rows)==1 and rows[0]['preference']==saved['preference']
    assert rows[0]['preference']['selected_display_position']==3
    assert not c.get(BASE+'/feedback.json?status=pending').get_json()['rows']
    identify(c)
    post(c,'/attempts',payload())
    identify(c,'master_admin')
    page = c.get(BASE+'/feedback.json?history=1&limit=1').get_json()
    assert page['has_more'] and len(page['rows'])==1
    page2 = c.get(BASE+'/feedback.json?history=1&limit=1&offset=1').get_json()
    assert not page2['has_more'] and len(page2['rows'])==1
    assert page2['rows'][0]['attempt_id']==data['attempt_id']
    import sqlite3
    with sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB']) as db:
        sql = ' '.join(r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name IN ('attempts','preferences','presentations')"))
        assert 'reason' not in sql and 'name' not in sql

def test_admin_context_does_not_resolve_students(web,monkeypatch):
    app,c,models = web
    identify(c,'master_admin')
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    def forbidden_lookup():
        raise AssertionError('Admin preview must not resolve a student')
    monkeypatch.setattr(models.Student.query,'all',forbidden_lookup)
    assert c.get(BASE+'/context').get_json()['display_name'] is None
    assert c.post(BASE+'/attempts',json=payload()).status_code == 403
    assert not Path(app.config['MOMOTOWN_FEEDBACK_DB']).exists()

def test_default_instance_store_is_separate_and_lazy(web,tmp_path):
    app,c,_ = web
    app.config.pop('MOMOTOWN_FEEDBACK_DB')
    app.instance_path = str(tmp_path/'private-instance')
    path = Path(app.instance_path)/'momotown-feedback.sqlite3'
    assert c.get(BASE+'/context').status_code == 200
    assert not path.exists()
    data = post(c,'/attempts',payload()).get_json()
    assert path.is_file()
    assert c.get(BASE+'/attempts/'+data['attempt_id']).get_json()==data

def test_context_identity(web):
    app,c,models = web
    response = c.get(BASE+'/context')
    assert response.status_code == 200
    data = response.get_json()
    assert data['mode'] == 'student'
    assert data['display_name'] == '<script>학생</script>'
    assert data['form_version'] == VERSION
    assert data['copy_version'] == 'momotown-festival-v02'
    assert data['csrf_token']
    assert models.Student.query.kwargs == {'user_id':'u1'}
    identify(c,'admin')
    app.config['STUDENT_INTEREST_QUEST_ENABLED'] = False
    data = c.get(BASE+'/context').get_json()
    assert data['mode'] == 'admin_preview' and data['display_name'] is None
    assert not Path(app.config['MOMOTOWN_FEEDBACK_DB']).exists()
