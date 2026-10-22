from test_story_v3 import page,ROOT,OUT
from test_story_report import sample
import base64,io,json
from PIL import Image,ImageChops

def test_manifest_actual_assets_chapters_and_occupations(page):
    manifest=page.evaluate('VILLAGE_STORY')
    assert len(manifest)==9
    assert len({x['name'] for x in manifest.values()})==9
    assert len({x['character'] for x in manifest.values()})>=8
    changed=0
    for id,v in manifest.items():
        src=page.evaluate('(id)=>placeImage(id)',id)
        before=page.evaluate('(id)=>NEW_VILLAGES.has(id)?worldAsset("revision9-"+id+".webp"):worldAsset("village-"+id+".webp")',id)
        a=Image.open(io.BytesIO(base64.b64decode(src.split(',')[1]))).convert('RGB')
        b=Image.open(io.BytesIO(base64.b64decode(before.split(',')[1]))).convert('RGB')
        assert a.size==b.size
        if ImageChops.difference(a,b).getbbox(): changed+=1
    assert changed>=5
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    page.get_by_role('button',name='마을 전체 지도',exact=True).click()
    for id,v in manifest.items():
        pin=page.locator(f'.map-pin[data-village="{id}"]')
        assert pin.inner_text()==v['name']
        pin.click()
        assert page.locator('#dialog-title').inner_text()==v['name']
        assert v['name'] in page.locator('#dialog-content').inner_text()
        page.evaluate('closeDialog()')
    sample(page)
    page.locator('#tab-connections').click()
    assert page.locator('.career-scene svg[role=img]').count()>=2
    assert page.locator('.school-table svg').count()>=3
    assert page.locator('.department-illustration').count()>=1
    for svg in page.locator('.career-scene svg[role=img]').all():
        assert svg.get_attribute('aria-label')
        assert svg.locator('path,rect,circle').count()>5
    assert '예를 들어' in page.locator('.school-table').first.inner_text()
    page.get_by_role('button',name='첫 화면으로',exact=True).click()
    page.get_by_role('button',name='탐험 시작하기',exact=True).first.click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    for chapter,scene in [(1,'MOMO_AMPHITHEATRE'),(2,'PLAZA'),(3,'TIME_HOUSE'),(4,'MOMO_AMPHITHEATRE')]:
        page.evaluate('(n)=>{session.cursor=(n-1)*8;view="pause";render()}',chapter)
        css=page.locator('.chapter-art').get_attribute('style')
        assert page.evaluate('(id)=>placeImage(id)',scene) in css
        page.screenshot(path=str(OUT/f'chapter-final-{chapter}.png'),full_page=True)
