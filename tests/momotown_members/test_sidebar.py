import pytest
from bs4 import BeautifulSoup
from conftest import BASE,ROLES,identify
@pytest.mark.parametrize('role',[*ROLES,'observer',None])
@pytest.mark.parametrize('active',[False,True])
@pytest.mark.parametrize('flag',[False,True])
def test_whole_real_sidebar_enclosing_roles_no_duplicate_or_other_gate_widening(web,role,active,flag):
    app,c=web['app'],web['client'];app.config['MEMBER_INTEREST_QUEST_ENABLED']=flag;identify(c,role,active)
    response=c.get('/__sidebar');assert response.status_code==200
    soup=BeautifulSoup(response.data,'html.parser')
    links=soup.select('a[href="'+BASE+'/"]')
    expected=bool(active and role in ROLES and (flag or role in ('admin','master_admin')))
    assert len(links)==int(expected)
    if expected:assert '전공마을 탐험' in links[0].get_text()
    mid=soup.select('a[href="/student/interest-mid/"]')
    # Existing outer student/admin branch remains unchanged (master_admin not present).
    assert len(mid)==int(role=='admin')  # Existing unrelated menu has no active check.
