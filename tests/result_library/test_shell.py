from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from flask import render_template_string,url_for
from flask_login import current_user
from werkzeug.routing import BuildError
import pytest
from conftest import ROOT,BASE,User

@pytest.mark.parametrize('uid,show_parent',[('u1',False),('p1',True),('teacher',False),('admin',False)])
def test_full_shell_wires_layer_and_parent_entry(web,uid,show_parent):
    app,c=web
    from jinja2 import ChoiceLoader,DictLoader
    app.jinja_loader=ChoiceLoader([app.jinja_loader,DictLoader({'news/publishing/unread_badge.html':'<!-- unrelated news badge omitted in factory-free shell -->'})])
    app.jinja_env.filters['kst']=lambda value,fmt:'2026-11-21'
    def links(endpoint,**kwargs):
        try:return url_for(endpoint,**kwargs)
        except BuildError:return '/__unrelated/'+endpoint
    User.role_level=property(lambda self:{'admin':2,'teacher':3,'parent':4,'student':5}[self.role])
    User.has_permission_level=lambda self,level:self.role_level<=level
    User.is_admin=property(lambda self:self.role=='admin')
    User.is_teacher=property(lambda self:self.role=='teacher')
    User.is_master_admin=False
    for template in [ROOT/'templates/base.html',ROOT/'reports/result-library-20261121/integration/base-live-candidate.html']:
        with app.test_request_context('/fixture-full-shell'):
            from flask_login import login_user
            from conftest import db
            login_user(db.session.get(User,uid))
            html=render_template_string(template.read_text(encoding='utf8'),url_for=links,
                 static_v=lambda name:'/static/'+name,news_learning_menu=False,parent_survey_completed=True,
                 p3_reports_navigation=None,unread_counts=defaultdict(int),now=lambda:SimpleNamespace(year=2026))
        assert 'id="interest-layer"' in html
        assert ('data-interest-layer href="'+BASE+'/children"') in html if show_parent else ('data-interest-layer href="'+BASE+'/children"') not in html
