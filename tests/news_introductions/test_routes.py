import unittest
from bs4 import BeautifulSoup
from support import build_app, client, db, SiteContent, ROOT

class IntroTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_app()
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        print('Synthetic evidence root:', ROOT)
    def setUp(self):
        self.app.config.pop('NEWS_INTRO_V02_ENABLED', None)
        # Release artwork is a fallback; saved editorial text wins.
        with self.app.app_context():
            for row in SiteContent.query.all():
                row.content = 'Stored <script>alert(1)</script>' if self._testMethodName in (
                    'test_flag_is_fail_closed_and_stored_html_is_escaped',
                    'test_admin_existing_edit_round_trip_and_csrf') else ''
            db.session.commit()
    def test_course_candidate_has_source_pages_and_accessible_text(self):
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        response = client(self.app).get('/news/courses')
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, 'html.parser')
        self.assertEqual(len(soup.select('[data-intro-v02] img')), 4)
        self.assertNotIn('로컬 검토 전용', soup.get_text())
        self.assertIn('베이직', soup.get_text())
        self.assertIn('정독 · 강독 + 짧은 글쓰기', soup.get_text())
        self.assertNotIn('Stored', soup.get_text())
        for i, image in enumerate(soup.select('[data-intro-v02] img'), 1):
            self.assertEqual(image['src'], f'/static/news/introductions-v02/course-{i:02}.webp')
            self.assertTrue(image['alt'])

    def test_about_candidate_has_source_story_and_renamed_title(self):
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        soup = BeautifulSoup(client(self.app).get('/news/about').data, 'html.parser')
        self.assertIn('모모의 책장 소개', soup.title.get_text())
        self.assertEqual(len(soup.select('[data-intro-v02] img')), 4)
        for text in ('미하엘 엔데의 『모모』', '모모', '카시오페이아', '베포', '기기', '호라박사', '소개를 위한 해석입니다.', '다음 책장에는, 어떤 생각이 기다릴까요?'):
            self.assertIn(text, soup.get_text())
        for i, image in enumerate(soup.select('[data-intro-v02] img'), 1):
            self.assertEqual(image['src'], f'/static/news/introductions-v02/story-{i:02}.webp')

    def test_hub_candidate_has_three_original_menu_images(self):
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        soup = BeautifulSoup(client(self.app).get('/news/').data, 'html.parser')
        images = soup.select('img[data-intro-menu]')
        self.assertEqual([i['src'] for i in images], [f'/static/news/introductions-v02/menu-{k}.png' for k in ('course', 'teacher', 'about')])
        self.assertIn('모모의 책장 소개', soup.get_text())
        self.assertNotIn('로컬 검토 전용', soup.get_text())
        self.assertTrue(all(i.get('alt') for i in images))

    def test_flag_is_fail_closed_and_stored_html_is_escaped(self):
        for value in (False, 'true', 'False', 1, [], {}):
            if value is None:
                self.app.config.pop('NEWS_INTRO_V02_ENABLED', None)
            else:
                self.app.config['NEWS_INTRO_V02_ENABLED'] = value
            for path in ('/news/courses', '/news/about'):
                html = client(self.app).get(path).get_data(as_text=True)
                self.assertIn('Stored &lt;script&gt;', html)
                self.assertNotIn('<script>alert(1)</script>', html)
                self.assertNotIn('data-intro-v02', html)
            hub = client(self.app).get('/news/').get_data(as_text=True)
            self.assertNotIn('data-intro-menu', hub)
            self.assertNotIn('모모의 책장 소개', hub)

    def test_anonymous_redirects_and_non_admin_edits_preserve_rows(self):
        for enabled in (False, True):
            self.app.config['NEWS_INTRO_V02_ENABLED'] = enabled
            for path in ('/news/', '/news/courses', '/news/about', '/news/courses/edit', '/news/about/edit'):
                response = client(self.app, None).get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/auth/login', response.location)
            with self.app.app_context():
                before = [(r.key, r.title, r.content) for r in SiteContent.query.order_by(SiteContent.key)]
            for role in ('parent', 'student', 'teacher', 'manager'):
                c = client(self.app, role)
                for path in ('/news/courses/edit', '/news/about/edit'):
                    self.assertEqual(c.get(path).status_code, 403)
                    with c.session_transaction() as session:
                        session['csrf_token'] = 'synthetic-token'
                    from itsdangerous import URLSafeTimedSerializer
                    token = URLSafeTimedSerializer(self.app.secret_key, salt='wtf-csrf-token').dumps('synthetic-token')
                    self.assertEqual(c.post(path, data={'title':'DENIED', 'content':'DENIED', 'csrf_token':token}).status_code, 403)
            with self.app.app_context():
                self.assertEqual(before, [(r.key,r.title,r.content) for r in SiteContent.query.order_by(SiteContent.key)])

    def test_admin_existing_edit_round_trip_and_csrf(self):
        for enabled in (False, True):
            self.app.config['NEWS_INTRO_V02_ENABLED'] = enabled
            c = client(self.app, 'admin')
            for path, key in (('/news/courses/edit','course_intro'),('/news/about/edit','about_momo')):
                soup = BeautifulSoup(c.get(path).data, 'html.parser')
                # Submit the token actually rendered for this synthetic client.
                field = soup.select_one('input[name=csrf_token]')
                self.assertIsNotNone(field, 'Editor must render a CSRF field')
                token = field['value']
                self.assertIn('Stored <script>', soup.select_one('textarea').get_text())
                for data in ({'title':'DENIED','content':'DENIED'}, {'title':'DENIED','content':'DENIED','csrf_token':'arbitrary'}):
                    self.assertEqual(c.post(path,data=data).status_code,400)
                response = c.post(path,data={'title':'Saved title','content':'Saved <b>text</b>','csrf_token':token})
                self.assertEqual(response.status_code,302)
                with self.app.app_context():
                    row = db.session.get(SiteContent,key)
                    self.assertEqual((row.title,row.content,row.updated_by_id),('Saved title','Saved <b>text</b>','fixture-admin'))
                    row.title, row.content = 'Stored <title>', 'Stored <script>alert(1)</script>'
                    db.session.commit()

    def test_gets_never_seed_missing_content(self):
        with self.app.app_context():
            rows = [(r.key,r.title,r.content) for r in SiteContent.query.all()]
            SiteContent.query.delete()
            db.session.commit()
        try:
            for enabled in (False, True):
                self.app.config['NEWS_INTRO_V02_ENABLED'] = enabled
                for path in ('/news/', '/news/courses','/news/about'):
                    self.assertEqual(client(self.app).get(path).status_code,200)
                with self.app.app_context():
                    self.assertEqual(SiteContent.query.count(),0)
        finally:
            with self.app.app_context():
                for key,title,content in rows:
                    db.session.add(SiteContent(key=key,title=title,content=content))
                db.session.commit()

    def test_every_editorial_string_has_accessible_text(self):
        import json
        from support import REPO
        source = json.loads((REPO/'app/news/introductions_v02.json').read_text(encoding='utf-8'))
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value: yield from strings(item)
            elif isinstance(value, dict):
                for key,item in value.items():
                    if key not in ('id','key'): yield from strings(item)
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        for kind,path in (('course','courses'),('story','about')):
            soup = BeautifulSoup(client(self.app).get('/news/'+path).data,'html.parser')
            text = soup.select_one('[data-intro-v02]').get_text()
            for phrase in strings(source[kind+'_pages']):
                self.assertIn(phrase,text)

    def test_source_assets_are_unchanged_and_fully_decodable(self):
        import hashlib
        from pathlib import Path
        from PIL import Image
        from support import REPO
        source = Path('C:/Users/aproa/Documents/Agent-Work/projects/momo-marketing/reports/momo-news-introductions-v02')
        assets = list((REPO/'static/news/introductions-v02').iterdir())
        self.assertEqual(len(assets),11)
        for asset in assets:
            original = source/('menus' if asset.suffix=='.png' else 'webp')/asset.name
            if asset.suffix == '.png':
                self.assertEqual(hashlib.sha256(original.read_bytes()).digest(),hashlib.sha256(asset.read_bytes()).digest())
            else:
                self.assertNotEqual(hashlib.sha256(original.read_bytes()).digest(),hashlib.sha256(asset.read_bytes()).digest())
            with Image.open(asset) as image:
                image.load()
                self.assertGreater(image.width,0)
                self.assertGreater(image.height,0)

    def test_candidate_editorial_values_are_autoescaped(self):
        from unittest.mock import patch
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        payload = '<script>candidate-injection</script>'
        page = {'id':'course-01','eyebrow':payload,'title':payload,'lead':payload,'steps':[[payload,payload]],'programs':[{'name':payload,'tag':payload,'body':payload,'point':payload}]}
        with patch('app.news.routes.candidate_pages', return_value=[page]):
            html = client(self.app).get('/news/courses').get_data(as_text=True)
            self.assertNotIn(payload,html)
            self.assertIn('&lt;script&gt;candidate-injection&lt;/script&gt;',html)

    def test_candidate_artwork_cannot_be_fetched_when_flag_off(self):
        for value in (None,False,'true',1):
            self.app.config['NEWS_INTRO_V02_ENABLED'] = value
            with client(self.app).get('/static/news/introductions-v02/course-01.webp') as response:
                self.assertEqual(response.status_code,404)
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        with client(self.app).get('/static/news/introductions-v02/course-01.webp') as response:
            self.assertEqual(response.status_code,200)
        self.app.config['NEWS_INTRO_V02_ENABLED'] = False
        with client(self.app).get('/static/css/style.min.css') as response:
            self.assertEqual(response.status_code,200)

    def test_candidate_static_gate_normalizes_path_aliases(self):
        self.app.config['NEWS_INTRO_V02_ENABLED'] = False
        for path in ('news/./introductions-v02/course-01.webp', 'news/other/../introductions-v02/course-01.webp'):
            with client(self.app).get('/static/'+path) as response:
                self.assertEqual(response.status_code,404)

if __name__ == '__main__':
    unittest.main(verbosity=2)
