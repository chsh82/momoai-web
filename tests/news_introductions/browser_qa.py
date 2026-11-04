"""Loopback-only browser evidence. Uses synthetic cookies, NOT real authentication.
Run separately for news/community so package shims cannot contaminate each other.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

parser = argparse.ArgumentParser()
parser.add_argument('target', choices=['news','community'])
parser.add_argument('--output', required=True)
args = parser.parse_args()
OUT = Path(args.output).resolve()
OUT.mkdir(parents=True, exist_ok=True)
if args.target == 'news':
    from support import build_app, db, ROOT, SiteContent
    app = build_app()
    # Exercise the actual default and approved fallback, not an injected flag.
    with app.app_context():
        for row in SiteContent.query.all(): row.content = ''
        from app.models import Post
        db.session.add(Post(user_id='fixture-admin',category='notice',
            title='합성 모모공지 · 기존 공지 위치 이동 확인 · '+('긴제목표시확인'*12),content='합성 공지, 실제 운영 데이터 아님'))
        db.session.commit()
    pages = [('hub','/news/','parent'), ('hub-admin','/news/','admin'), ('courses','/news/courses','parent'), ('about','/news/about','parent'),
             ('courses-edit','/news/courses/edit','admin'), ('about-edit','/news/about/edit','admin')]
else:
    spec = importlib.util.spec_from_file_location('education_fixture', Path(__file__).resolve().parents[1]/'community/test_education_articles.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    app, db, ROOT = fixture.build_app(), fixture.db, fixture.ROOT
    from app.models import Post, Tag, PostTag, Bookmark
    with app.app_context():
        post = Post(user_id='fixture-admin',category='education_article',title='합성 교육기사 · 로컬 QA',content='<p>합성 교육기사 본문. 실제 게시물이 아닙니다.</p>')
        tag = Tag(name='합성태그')
        db.session.add_all([post,tag]); db.session.flush()
        pid = post.post_id
        db.session.add_all([PostTag(post_id=pid,tag_id=tag.tag_id), Bookmark(user_id='fixture-parent',post_id=pid)])
        db.session.commit()
    # Preserve the existing minimal shell, adding an explicit synthetic label.
    original_shell = app.jinja_loader.load(app.jinja_env, 'base.html').filename
    LABELED_SHELL = '''<!doctype html><html lang="ko"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/tailwind.min.css"><link rel="stylesheet" href="/static/css/style.min.css"></head><body><header style="background:#fff3cd;padding:10px">LOCAL SYNTHETIC QA · 최소 대체 shell · 운영 인증 아님</header><main>{% block content %}{% endblock %}</main>{% block extra_js %}{% endblock %}</body></html>'''
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html':LABELED_SHELL}),app.jinja_loader])
    pages = [('education-tab','/community/?category=education_article','parent'),
             ('education-detail','/community/'+pid,'parent'), ('education-new','/community/new','admin'),
             ('education-edit','/community/'+pid+'/edit','admin'), ('education-bookmarks','/community/bookmarks','parent'),
             ('education-tag','/community/tags/합성태그','parent')]

server = make_server('127.0.0.1',0,app,threaded=True)
thread = threading.Thread(target=server.serve_forever)
thread.start()
base = f'http://127.0.0.1:{server.server_port}'
results = []
blocked = []
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for viewport in ({'width':1440,'height':1000},{'width':390,'height':844}):
                name = 'desktop' if viewport['width'] == 1440 else 'phone'
                for label,path,role in pages:
                    context = browser.new_context(viewport=viewport,device_scale_factor=1)
                    def route_handler(route):
                        url = urlsplit(route.request.url)
                        if url.hostname == '127.0.0.1': route.continue_()
                        else:
                            blocked.append(route.request.url)
                            route.abort()
                    context.route('**/*',route_handler)
                    serializer = app.session_interface.get_signing_serializer(app)
                    cookie = serializer.dumps({'_user_id':'fixture-'+role,'_fresh':True})
                    context.add_cookies([{'name':app.config['SESSION_COOKIE_NAME'],'value':cookie,'url':base}])
                    page = context.new_page()
                    response = page.goto(base+path,wait_until='networkidle')
                    assert response.status == 200, (path,response.status)
                    if args.target == 'community' and label == 'education-new':
                        page.select_option('select[name=category]', 'education_article')
                        assert page.input_value('select[name=category]') == 'education_article'
                    page.locator('img').evaluate_all('(imgs)=>imgs.forEach(i=>i.loading="eager")')
                    page.evaluate('''async()=>{await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})));await document.fonts.ready}''')
                    metrics = page.evaluate('''()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:[...document.images].map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,height:i.naturalHeight,alt:i.alt}))})''')
                    assert metrics['scrollWidth'] <= metrics['width'], (path,metrics)
                    assert all(i['width']>0 for i in metrics['images']), (path,metrics)
                    screenshot = OUT/f'{args.target}-{label}-{name}.png'
                    page.screenshot(path=str(screenshot), full_page=True)
                    # Native text alternatives must expand with keyboard, no scripts needed.
                    details = page.locator('[data-intro-v02] details')
                    if details.count():
                        summary = details.first.locator('summary')
                        summary.focus(); page.keyboard.press('Enter')
                        assert details.first.get_attribute('open') is not None
                    results.append({'route':path,'role':role,'viewport':viewport,'screenshot':str(screenshot),'metrics':metrics})
                    context.close()
        finally:
            browser.close()
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=10)
    with app.app_context(): db.session.remove(); db.engine.dispose()
    (OUT/f'{args.target}-browser.json').write_text(json.dumps({'target':args.target,'synthetic_root':str(ROOT),'server_stopped':not thread.is_alive(),'results':results,'blocked_external_requests':sorted(set(blocked))},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target':args.target,'screenshots':len(results),'server_stopped':not thread.is_alive(),'synthetic_root':str(ROOT)}))
