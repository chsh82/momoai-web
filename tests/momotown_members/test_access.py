import pytest
from conftest import BASE,ROLES,identify
@pytest.mark.parametrize('role',ROLES)
def test_active_member_entry_context_without_student_flag(web,role):
    c=web['client'];identify(c,role)
    assert c.get(BASE+'/').status_code==200
    data=c.get(BASE+'/context');assert data.status_code==200
    assert data.json['mode']==('student' if role=='student' else 'admin_preview' if role in ('admin','master_admin') else 'member_preview')
    assert data.json['display_name']==('격리 학생' if role=='student' else None)
    assert web['queries']==([{'user_id':'student'}] if role=='student' else [])

@pytest.mark.parametrize('member_flag',[False,True,'true',1])
@pytest.mark.parametrize('role',[*ROLES,'observer',None])
@pytest.mark.parametrize('active',[False,True])
def test_entry_role_flag_active_matrix(web,member_flag,role,active):
    app,c=web['app'],web['client'];app.config['MEMBER_INTEREST_QUEST_ENABLED']=member_flag
    identify(c,role,active)
    allowed=bool(active and role in ROLES and (member_flag is True or role in ('admin','master_admin')))
    for suffix in ('/','/context'):
        response=c.get(BASE+suffix)
        assert (response.status_code==200)==allowed
        if response.status_code==200:
            assert response.headers['Cache-Control']=='private, no-store'

@pytest.mark.parametrize('role',ROLES)
def test_inactive_accounts_cannot_touch_any_student_or_feedback_route(web,role):
    c=web['client'];identify(c,role,False)
    for suffix in ('/attempts','/attempts/00000000-0000-4000-8000-000000000000/presentation','/attempts/00000000-0000-4000-8000-000000000000/preference'):
        assert c.post(BASE+suffix,json={}).status_code in (302,403)
    for suffix in ('/attempts/00000000-0000-4000-8000-000000000000','/feedback','/feedback.json'):
        assert c.get(BASE+suffix).status_code in (302,403)
    assert not web['db'].exists()

@pytest.mark.parametrize('role',[*ROLES,'observer',None])
def test_nonstudent_writes_reads_and_parent_impersonation_denied(web,role):
    if role=='student':return
    c=web['client'];identify(c,role)
    # Forged parent child identity never becomes a student identity.
    with c.session_transaction() as s:s['student_id']='s1';s['selected_child_id']='s1'
    for suffix in ('/attempts','/attempts/00000000-0000-4000-8000-000000000000/presentation','/attempts/00000000-0000-4000-8000-000000000000/preference'):
        assert c.post(BASE+suffix,json={'student_id':'s1','user_id':'student'}).status_code in (302,403)
    assert c.get(BASE+'/attempts/00000000-0000-4000-8000-000000000000').status_code in (302,403)
    if role not in ('admin','master_admin'):
        assert c.get(BASE+'/feedback.json').status_code==403
        assert c.get(BASE+'/feedback').status_code==403
    assert not web['db'].exists() and not web['queries']

def test_scoped_config_release_only_and_unchanged_mid(web):
    import ast
    from pathlib import Path
    tree=ast.parse((Path(__file__).resolve().parents[2]/'config.py').read_text(encoding='utf8'))
    def assignments(name):
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
        return {n.targets[0].id:ast.literal_eval(n.value) for n in cls.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and 'INTEREST_' in n.targets[0].id}
    assert assignments('Config')['MEMBER_INTEREST_QUEST_ENABLED'] is False
    assert assignments('ProductionConfig')=={'MEMBER_INTEREST_QUEST_ENABLED':True}
    assert assignments('Config')['STUDENT_INTEREST_MID_ENABLED'] is False
    for role in ('student','parent','teacher','manager','staff'):
        identify(web['client'],role)
        assert web['client'].get('/student/interest-mid/').status_code==403
