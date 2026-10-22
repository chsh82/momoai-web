"""Isolated route tests: never import the application factory/config or a database."""
import sys
import types
from pathlib import Path
import pytest
from flask import Flask, session
from flask_login import LoginManager, UserMixin

ROOT = Path(__file__).resolve().parents[2]
# Load real blueprint packages without executing app/__init__.py.
package = types.ModuleType('app')
package.__path__ = [str(ROOT / 'app')]
sys.modules['app'] = package
from app.interest_quest import interest_quest_bp
from app.interest_mid import interest_mid_bp

class Identity(UserMixin):
    def __init__(self, role, active=True):
        self.id, self.role, self.active = role, role, active
        self.is_admin = role == 'admin'
    @property
    def is_active(self):
        return self.active

def make_web():
    from flask_wtf.csrf import generate_csrf
    app = Flask('launch-test', static_folder=str(ROOT/'static'), template_folder=str(ROOT/'templates'))
    app.config.update(TESTING=True, SECRET_KEY='local-test-only')
    app.jinja_env.globals['csrf_token']=generate_csrf
    app.add_url_rule('/test-only-csrf', 'test_only_csrf', generate_csrf)
    manager = LoginManager(app)
    @manager.user_loader
    def load(uid):
        return Identity(uid, session.get('active', True))
    app.add_url_rule('/login', 'auth.login', lambda: 'local login')
    app.register_blueprint(interest_quest_bp, url_prefix='/student/interest-quest')
    app.register_blueprint(interest_mid_bp, url_prefix='/student/interest-mid')
    return app, app.test_client()

@pytest.fixture
def web():
    return make_web()

def identify(client, role, active=True):
    with client.session_transaction() as s:
        s.clear()
        if role:
            s['_user_id'] = role
            s['active'] = active

def csrf(client):
    return client.get('/test-only-csrf').get_data(as_text=True)

@pytest.mark.parametrize('feature', ['quest', 'mid'])
def test_active_student_launch_flag(web, feature):
    app, client = web
    identify(client, 'student')
    # Root redirects/rendering are not needed to prove route access.
    path = '/student/interest-' + feature + '/'
    assert client.get(path).status_code == 403
    app.config['STUDENT_INTEREST_' + feature.upper() + '_ENABLED'] = True
    if feature == 'mid':
        from jinja2 import ChoiceLoader, DictLoader
        app.jinja_loader = ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}), app.jinja_loader])
    assert client.get(path).status_code == 200

def test_static_quest_bypass_removed(web):
    app, client = web
    assert client.get('/static/interest_quest/index.html').status_code == 404
    assert not (ROOT/'static/interest_quest/index.html').exists()
    identify(client, 'admin')
    assert b'InterestScoring' in client.get('/student/interest-quest/').data

@pytest.mark.parametrize('quest,mid', [(False,False),(True,False),(False,True),(True,True)])
def test_default_flags_and_student_sidebar(web, quest, mid):
    import ast
    from flask import render_template_string
    from flask_login import login_user
    config = ast.parse((ROOT/'config.py').read_text(encoding='utf-8'))
    cls = next(x for x in config.body if isinstance(x,ast.ClassDef) and x.name=='Config')
    defaults = {x.targets[0].id: ast.literal_eval(x.value) for x in cls.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id.startswith('STUDENT_INTEREST_')}
    assert defaults == {'STUDENT_INTEREST_QUEST_ENABLED':False, 'STUDENT_INTEREST_MID_ENABLED':False}
    app, client = web
    app.config.update(STUDENT_INTEREST_QUEST_ENABLED=quest, STUDENT_INTEREST_MID_ENABLED=mid)
    template=(ROOT/'templates/base.html').read_text(encoding='utf-8')
    # Render actual service section; avoid unrelated application/DB context processors.
    start=template.rfind('{% if',0,template.index('<a href="{{ url_for(\'interest_quest.index\') }}"'))
    end=template.index('<!-- 어휘퀴즈',start)
    fragment=template[start:end]
    app.add_url_rule('/study-mid', 'study_mid.index', lambda:'')
    app.add_url_rule('/study-elem', 'study_elem.index', lambda:'')
    for role in ('student','parent','teacher','manager','admin','master_admin'):
        identity=Identity(role)
        identity.is_admin=role=='admin'
        with app.test_request_context('/'):
            login_user(identity)
            html=render_template_string(fragment, sidebar_active=lambda x:'')
        admin=role in ('admin','master_admin')
        assert ('/student/interest-quest/' in html) == (admin or (role=='student' and quest))
        assert ('/student/interest-mid/' in html) == (admin or (role=='student' and mid))
        assert ('/study-mid' in html) == admin
        assert ('/study-elem' in html) == admin

@pytest.mark.parametrize('bad', ['not-a-number','1.2','-1','999','',None])
def test_compass_invalid_answer_no_500(web, bad):
    app,client=web
    identify(client,'admin')
    answers={f'q{i}':'0' for i in range(40)}
    if bad is None: answers.pop('q12')
    else: answers['q12']=bad
    answers['csrf_token']=csrf(client)
    response=client.post('/student/interest-mid/submit',data=answers)
    assert response.status_code==302
    assert response.location.endswith('/quiz')
    with client.session_transaction() as s:
        assert 'interest_mid_result' not in s

def test_compass_student_notices(web):
    from jinja2 import ChoiceLoader,DictLoader
    app,client=web
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}),app.jinja_loader])
    app.config['STUDENT_INTEREST_MID_ENABLED']=True
    identify(client,'student')
    html=client.get('/student/interest-mid/').get_data(as_text=True)
    assert '5문항' in html
    assert '능력이나 진로를 확정' in html
    assert '관리자 검토용' not in html

@pytest.mark.parametrize('quest,mid',[(False,False),(True,False),(False,True),(True,True)])
@pytest.mark.parametrize('role,active',[('admin',True),('master_admin',True),('student',True),('student',False),('parent',True),('teacher',True),('manager',True),('staff',True),(None,True)])
def test_all_route_role_flag_matrix(web,quest,mid,role,active):
    from jinja2 import ChoiceLoader,DictLoader
    app,client=web
    app.config.update(STUDENT_INTEREST_QUEST_ENABLED=quest, STUDENT_INTEREST_MID_ENABLED=mid)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}),app.jinja_loader])
    app.jinja_env.globals['csrf_token']=lambda:'local-token'
    identify(client,role,active)
    for feature,enabled,suffixes in [('quest',quest,['/']),('mid',mid,['/','/quiz','/submit','/result','/print'])]:
        allowed=role in ('admin','master_admin') or (role=='student' and active and enabled)
        for suffix in suffixes:
            path='/student/interest-'+feature+suffix
            response=client.post(path,data={'csrf_token':csrf(client)}) if suffix=='/submit' else client.get(path)
            if role is None or not active:
                assert response.status_code==302 and response.location.endswith('/login')
            elif allowed:
                assert response.status_code in (200,302)
                assert not response.location or not response.location.endswith('/login')
            else: assert response.status_code==403

def test_compass_csrf_and_score_equivalence(web):
    from flask_wtf.csrf import generate_csrf
    from app.interest_mid.routes import engine,FORM
    from jinja2 import ChoiceLoader,DictLoader
    from bs4 import BeautifulSoup
    app,client=web
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}),app.jinja_loader])
    # Production does not install global CSRFProtect: the real route must validate.
    app.jinja_env.globals['csrf_token']=generate_csrf
    identify(client,'admin')
    answers={f'q{i}':'0' for i in range(40)}
    assert client.post('/student/interest-mid/submit',data=answers).status_code==400
    assert client.post('/student/interest-mid/submit',data=dict(answers,csrf_token='invalid-token')).status_code==400
    soup=BeautifulSoup(client.get('/student/interest-mid/quiz').data,'html.parser')
    answers['csrf_token']=soup.select_one('[name=csrf_token]')['value']
    response=client.post('/student/interest-mid/submit',data=answers)
    assert response.status_code==302 and response.location.endswith('/result')
    items,content=engine.load(FORM)
    expected=engine.render_payload(engine.score([0]*40,FORM,items),content)
    with client.session_transaction() as s:
        assert s['interest_mid_result']['payload']==expected
        assert s['interest_mid_result']['answers']==[0]*40
    assert client.get('/student/interest-mid/result').status_code==200
    assert client.get('/student/interest-mid/print').status_code==200

def test_student_print_not_labeled_admin_preview(web):
    from jinja2 import ChoiceLoader,DictLoader
    app,client=web
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}),app.jinja_loader])
    app.config['STUDENT_INTEREST_MID_ENABLED']=True
    identify(client,'student')
    answers={f'q{i}':'0' for i in range(40)}
    answers['csrf_token']=csrf(client)
    client.post('/student/interest-mid/submit',data=answers)
    html=client.get('/student/interest-mid/print').get_data(as_text=True)
    assert '관리자 검토용' not in html

def test_syntax_and_no_factory_database_imports():
    import py_compile
    from jinja2 import Environment
    for relative in ('app/utils/student_launch.py','app/interest_quest/routes.py','app/interest_mid/routes.py','config.py'):
        py_compile.compile(str(ROOT/relative), doraise=True)
    env=Environment()
    for relative in ('templates/base.html','templates/interest_mid/index.html','templates/interest_mid/quiz.html','templates/interest_mid/print.html'):
        env.parse((ROOT/relative).read_text(encoding='utf-8'))
    assert 'app.models' not in sys.modules
    assert 'config' not in sys.modules
    assert 'app.scheduler' not in sys.modules
