"""Real NEWS/community routes on the guarded synthetic-only factory."""
import unittest
from bs4 import BeautifulSoup
from support import build_app,client,db,SiteContent
from app.models import Post

class NoticeHubTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=build_app()
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():db.session.remove();db.engine.dispose()
    def setUp(self):
        with self.app.app_context():
            Post.query.delete();db.session.commit()
    def test_existing_notice_appears_in_hub_with_original_read_and_admin_links(self):
        with self.app.app_context():
            row=Post(user_id='fixture-admin',title='EXISTING NOTICE <escaped>',content='not copied',category='notice')
            other=Post(user_id='fixture-admin',title='NOT A NOTICE',content='existing',category='education_article')
            db.session.add_all([row,other]);db.session.commit();pid=row.post_id
            before=[(p.post_id,p.category,p.title,p.views) for p in Post.query.order_by(Post.post_id)]
        for role in ('parent','student','teacher','admin'):
            soup=BeautifulSoup(client(self.app,role).get('/news/').data,'html.parser')
            section=soup.select_one('#momo-notices')
            self.assertIsNotNone(section)
            self.assertIn('EXISTING NOTICE <escaped>',section.get_text())
            self.assertNotIn('NOT A NOTICE',section.get_text())
            self.assertTrue(section.select_one('a[href="/community/'+pid+'"]'))
            self.assertEqual(bool(section.select_one('a[href="/community/'+pid+'/edit"]')),role=='admin')
            self.assertEqual(bool(section.select_one('a[href="/community/new"]')),role=='admin')
        with self.app.app_context():
            self.assertEqual(before,[(p.post_id,p.category,p.title,p.views) for p in Post.query.order_by(Post.post_id)])

    def test_empty_notice_entry_is_independent_of_news_gate_and_anonymous_denied(self):
        for enabled in (False,True):
            self.app.config['NEWS_PUBLISHING_ENABLED']=enabled
            soup=BeautifulSoup(client(self.app,'parent').get('/news/').data,'html.parser')
            self.assertIn('등록된 모모공지가 없습니다.',soup.select_one('#momo-notices').get_text())
            self.assertIsNotNone(soup.select_one('#momo-notices').select_one('h3'))
        response=client(self.app,None).get('/news/')
        self.assertEqual(response.status_code,302)
        self.assertIn('/auth/login',response.location)

if __name__=='__main__':unittest.main(verbosity=2)
