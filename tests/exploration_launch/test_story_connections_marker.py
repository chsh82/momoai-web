from test_story_v3 import page
from test_story_report import sample

def test_core_connections_keep_small_village_marker_and_readable_school_column(page):
    page.set_viewport_size({'width':1440,'height':950})
    sample(page);page.locator('#tab-connections').click()
    assert page.locator('.core-place-marker').count()==1
    assert page.locator('.core-place-marker img').count()>=1
    first=page.locator('.school-table thead th').first.bounding_box()['width']
    second=page.locator('.school-table thead th').nth(1).bounding_box()['width']
    assert first<second/2
