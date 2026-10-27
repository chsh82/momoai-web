from v02_helpers import open_report
from test_story_v3 import page
from test_story_report import sample

def test_one_school_table_per_village_no_repeated_long_catalog(page):
    sample(page)
    for tab in ['connections','second','third']:
        page.locator('#tab-'+tab).click()
        assert page.locator('.school-progression').count()==1
        assert page.locator('.career-scene').count()==2
        assert page.locator('.study-major').count()==1
        assert page.locator('.department-list').count()>=1
    page.locator('#tab-compare').click()
    open_report(page)
    assert page.locator('.journey-report .school-progression').count()==3
    assert page.locator('.journey-report .career-scene').count()==6
