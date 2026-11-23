"""Permissions exercised on HTML, JSON and native print URLs, with real ORM state."""
import hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4
import pytest
from conftest import BASE,create,db,User,Student,ParentStudent,store

@pytest.mark.parametrize('uid',['u2','p2','teacher','admin'])
def test_foreign_and_trial_roles_cannot_read_or_mutate_child_results(web,uid):
    app,c=web;data=create(app);attempt=data['attempt_id'];path=Path(app.config['MOMOTOWN_FEEDBACK_DB']);before=path.read_bytes()
    c.get('/__fixture_login/'+uid)
    for suffix in ['/children/s1/reports','/children/s1/reports.json','/children/s1/reports/'+attempt,
                   '/children/s1/reports/'+attempt+'.json','/children/s1/reports/'+attempt+'/print',
                   '/reports/'+attempt,'/reports/'+attempt+'.json','/reports/'+attempt+'/print']:
        assert c.get(BASE+suffix).status_code in (403,404)
    assert path.read_bytes()==before

@pytest.mark.parametrize('model,key,field,value',[
    (ParentStudent,'r1','is_active',False),(ParentStudent,'r1','permission_level','unknown'),
    (User,'p1','is_deleted',True),(User,'u1','is_deleted',True),
    (User,'u1','role','teacher'),(Student,'s1','status','withdrawn'),(Student,'s1','user_id',None)])
def test_revocation_and_current_account_state_guard_all_child_surfaces(web,model,key,field,value):
    app,c=web;data=create(app);attempt=data['attempt_id']
    c.get('/__fixture_login/p1')
    with app.app_context():setattr(db.session.get(model,key),field,value);db.session.commit()
    for suffix in ['/children/s1/reports','/children/s1/reports.json','/children/s1/reports/'+attempt,
                   '/children/s1/reports/'+attempt+'.json','/children/s1/reports/'+attempt+'/print']:
        assert c.get(BASE+suffix).status_code in (403,404)


def test_absent_store_read_does_not_create_db_or_schema(web):
    app,c=web;path=Path(app.config['MOMOTOWN_FEEDBACK_DB'])
    assert c.get(BASE+'/reports.json').json==dict(rows=[],has_more=False,offset=0)
    assert not path.exists()
    assert c.get(BASE+'/reports/'+str(uuid4())+'.json').status_code==404
    assert not path.exists()


def test_native_print_route_checks_anonymous_and_feature_gate(web):
    app,c=web;saved=create(app);attempt=saved['attempt_id']
    targets=['/reports','/reports.json','/reports/'+attempt,'/reports/'+attempt+'.json','/reports/'+attempt+'/print',
             '/children','/children.json','/children/s1/reports','/children/s1/reports.json','/children/s1/reports/'+attempt+'/print']
    with c.session_transaction() as session:session.clear()
    for target in targets:assert c.get(BASE+target).status_code==302
    c.get('/__fixture_login/u1');app.config.update(MEMBER_INTEREST_QUEST_ENABLED=False,STUDENT_INTEREST_QUEST_ENABLED=False)
    for target in targets:assert c.get(BASE+target).status_code==403
    app.config['STUDENT_INTEREST_QUEST_ENABLED']=True
    assert c.get(BASE+'/reports').status_code==200
    c.get('/__fixture_login/p1')
    assert c.get(BASE+'/children').status_code==403


def test_readonly_does_not_call_mutation_or_scorer_and_preserves_unknown_version(web,monkeypatch):
    app,c=web;saved=create(app)
    with closing(sqlite3.connect(app.config['MOMOTOWN_FEEDBACK_DB'])) as sql:
        sql.execute('UPDATE attempts SET copy_version=?,content_version=? WHERE attempt_id=?',('unknown-historical','unknown-content',saved['attempt_id']));sql.commit()
    before=Path(app.config['MOMOTOWN_FEEDBACK_DB']).read_bytes()
    def forbidden(*a,**kw):raise AssertionError('No new score, acknowledgement, preference or write connection on reports')
    from app.interest_quest import backend
    monkeypatch.setattr(backend,'analyze',forbidden)
    for name in ['create','presentation','preference','restore','connection']:monkeypatch.setattr(store,name,forbidden)
    for uid,prefix in [('u1',''),('p1','/children/s1')]:
        c.get('/__fixture_login/'+uid)
        response=c.get(BASE+prefix+'/reports/'+saved['attempt_id']+'.json')
        assert response.json['snapshot']['analysis']==saved['analysis']
        html=c.get(BASE+prefix+'/reports/'+saved['attempt_id']+'/print').get_data(as_text=True)
        assert '이 버전의 고정 안내 자료가 없어' in html
        assert 'unknown-historical' in html
        assert '<태그>' not in html
    assert Path(app.config['MOMOTOWN_FEEDBACK_DB']).read_bytes()==before


def test_historical_presentation_preference_still_reject_superseded_attempt(web):
    app,c=web;old=create(app);create(app,1)
    token=c.get(BASE+'/context').json['csrf_token']
    for action,body in [('presentation',dict(analysis_revision=old['analysis_revision'],domain_id=old['presented_villages'][0],sections=['intro'])),('preference',dict(request_id=str(uuid4()),analysis_revision=old['analysis_revision'],selected_village_id=old['presented_villages'][0]))]:
        assert c.post(BASE+'/attempts/'+old['attempt_id']+'/'+action,json=body,headers={'X-CSRFToken':token}).status_code==409
    c.get('/__fixture_login/p1')
    for action in ['presentation','preference']:
        assert c.post(BASE+'/attempts/'+old['attempt_id']+'/'+action,json={}).status_code==403


def test_report_includes_persisted_response_evidence_without_rescoring(web):
    app,c=web;saved=create(app)
    payload=c.get(BASE+'/reports/'+saved['attempt_id']+'.json')
    assert payload.status_code==200
    with app.app_context():
        original=store.restore('s1',saved['attempt_id'])
    assert payload.json.get('answers')==original['answers']
    html=c.get(BASE+'/reports/'+saved['attempt_id']).get_data(as_text=True)
    assert '저장된 응답 · 당시 문항 안내' in html
    from app.interest_quest.reports import catalog_for
    catalog=catalog_for(payload.json)
    selected=catalog['scenes'][0]['options'][0]['proposed_text']
    from markupsafe import escape
    assert str(escape(selected)) in html


def test_history_pagination_is_stable_and_deduplicated(web):
    app,c=web
    ids=[create(app,i)['attempt_id'] for i in range(23)]
    first=c.get(BASE+'/reports.json').json;second=c.get(BASE+'/reports.json?offset=20').json
    actual=[r['attempt_id'] for r in first['rows']+second['rows']]
    assert actual==list(reversed(ids))
    assert len(actual)==len(set(actual))==23
    assert first['has_more'] is True and second['has_more'] is False
    for offset in ['-1','10001','nope']:
        assert c.get(BASE+'/reports.json?offset='+offset).status_code==400
