from test_story_v3 import page
from test_story_report import sample

def test_core_connections_keep_small_village_marker_and_readable_school_column(page):
    page.set_viewport_size({'width':1440,'height':950})
    sample(page);page.locator('#tab-connections').click()
    assert page.locator('.core-place-marker').count()==1
    assert page.locator('.core-place-marker img').count()>=1
    stages=page.locator('.school-stage').all()
    boxes=[s.bounding_box() for s in stages]
    assert len(boxes)==3
    assert len({round(b['y']) for b in boxes})==1
    assert all(b['width']>200 for b in boxes)
    assert boxes[0]['x']<boxes[1]['x']<boxes[2]['x']
