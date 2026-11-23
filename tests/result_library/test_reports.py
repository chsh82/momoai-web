from pathlib import Path
import hashlib
from conftest import BASE,create,db,User,Student,ParentStudent


def test_linked_parent_list_detail_rechecks_account_and_relation(web):
    app,c=web
    old=create(app);create(app,1)
    c.get('/__fixture_login/p1')
    children=c.get(BASE+'/children.json')
    assert children.status_code==200
    assert [s['student_id'] for s in children.json['children']]==['s1']
    path=BASE+'/children/s1/reports/'+old['attempt_id']+'.json'
    assert c.get(path).status_code==200
    assert c.get(path).json['snapshot']['analysis']==old['analysis']
    assert c.get(BASE+'/children/s1/reports.json').status_code==200
    assert c.get(BASE+'/children/s2/reports.json').status_code==404
    c.get('/__fixture_login/p2')
    assert c.get(path).status_code==404
    c.get('/__fixture_login/p1')
    for model,key,field in [(ParentStudent,'r1','is_active'),(User,'u1','is_active'),(User,'p1','is_active')]:
        with app.app_context():
            row=db.session.get(model,key);setattr(row,field,False);db.session.commit()
        assert c.get(path).status_code in (403,404)
        assert c.get(BASE+'/children/s1/reports.json').status_code in (403,404)
        with app.app_context():
            row=db.session.get(model,key);setattr(row,field,True);db.session.commit()
    with app.app_context():
        db.session.get(ParentStudent,'r1').is_active=False;db.session.commit()
    assert c.get(BASE+'/children.json').json['children']==[]


def test_student_history_is_read_only_and_retains_latest_mutation_gate(web):
    app,c=web
    old=create(app);new=create(app,1)
    path=Path(app.config['MOMOTOWN_FEEDBACK_DB'])
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    response=c.get(BASE+'/reports.json')
    assert response.status_code==200
    rows=response.json['rows']
    assert [r['attempt_id'] for r in rows]==[new['attempt_id'],old['attempt_id']]
    assert [r['latest'] for r in rows]==[True,False]
    detail=c.get(BASE+'/reports/'+old['attempt_id']+'.json')
    assert detail.status_code==200
    assert detail.json['snapshot']['analysis']==old['analysis']
    assert detail.json['response_complete'] is True
    assert detail.json['preference_finalized'] is False
    assert c.get(BASE+'/attempts/'+old['attempt_id']).status_code==409
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
