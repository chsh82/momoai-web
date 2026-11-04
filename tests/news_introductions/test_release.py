"""Release behavior, isolated synthetic SQLite only."""
import unittest
from bs4 import BeautifulSoup
from support import build_app, client, db, SiteContent

class ReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = build_app()
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context(): db.session.remove(); db.engine.dispose()
    def setUp(self): self.app.config.pop('NEWS_INTRO_V02_ENABLED', None)
    def test_default_renders_approved_fallback_without_configuration(self):
        with self.app.app_context():
            for row in SiteContent.query.all(): row.content = ''
            db.session.commit()
        for path in ('courses', 'about'):
            soup = BeautifulSoup(client(self.app).get('/news/'+path).data, 'html.parser')
            self.assertEqual(len(soup.select('[data-intro-v02] img')), 4)
        self.assertEqual(len(BeautifulSoup(client(self.app).get('/news/').data,'html.parser').select('[data-intro-menu]')),3)
        self.assertEqual(client(self.app).get('/static/news/introductions-v02/course-01.webp').status_code,200)

    def test_release_render_has_no_internal_review_notices(self):
        with self.app.app_context():
            for row in SiteContent.query.all(): row.content = ''
            db.session.commit()
        self.app.config['NEWS_INTRO_V02_ENABLED'] = True
        for path in ('courses', 'about', ''):
            html = client(self.app).get('/news/'+path).get_data(as_text=True)
            for marker in ('로컬 검토', '검수 시안', '미게시', '대표 검수용'):
                self.assertNotIn(marker, html)

    def test_stored_editor_content_retains_rendering_priority(self):
        with self.app.app_context():
            for row in SiteContent.query.all(): row.content = 'Saved public introduction <b>escaped</b>'
            db.session.commit()
        for path in ('courses', 'about'):
            soup = BeautifulSoup(client(self.app).get('/news/'+path).data, 'html.parser')
            self.assertIn('Saved public introduction <b>escaped</b>', soup.get_text())
            self.assertFalse(soup.select('[data-intro-v02]'))

    def test_artwork_source_removes_review_footer_preserving_educational_notes(self):
        from support import REPO
        source = BeautifulSoup((REPO/'tools/news_introductions_v02/artwork.html').read_text(encoding='utf-8'), 'html.parser')
        self.assertEqual(len(source.select('.page')), 8)
        self.assertEqual(len(source.select('.menu')), 3)
        self.assertNotIn('대표 검수용', source.get_text())
        self.assertNotIn('미게시', source.get_text())
        self.assertIn('소개를 위한 해석입니다.', source.get_text())
        self.assertIn('개설', source.get_text())

    def test_release_metadata_is_not_a_review_candidate(self):
        import json
        from support import REPO
        data=json.loads((REPO/'app/news/introductions_v02.json').read_text(encoding='utf-8'))
        self.assertEqual(data['revision'],'v02-release')
        self.assertEqual(data['status'],'승인 게시본')

if __name__ == '__main__': unittest.main(verbosity=2)
