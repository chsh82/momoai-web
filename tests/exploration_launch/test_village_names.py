"""Approved concrete village names must agree across user-facing surfaces."""
from test_story_v3 import page

NAMES={'FOREST':'도서관 마을','LAB':'과학연구소 마을','FACTORY':'발명공방 마을','PLAZA':'시청광장 마을','CLINIC':'병원 마을','PORT':'항구시장 마을','FIELD':'생태농장 마을','HOUSE':'학교 마을','STAGE':'예술극장 마을'}
OLD=['속삭임 책숲','별빛 물음탑','톱니 구름공방','다정한 약속광장','햇살 쉼정원','바람 교역항','새싹 숨들판','한걸음 배움집','무지개 달무대']

def test_concrete_names_across_map_results_and_report(page):
    assert page.evaluate('Object.fromEntries(Object.entries(VILLAGE_STORY).map(([id,v])=>[id,v.name]))')==NAMES
    page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
    page.get_by_role('button',name='마을 전체 지도',exact=True).click()
    for id,name in NAMES.items():
        assert page.locator(f'.map-pin[data-village="{id}"]').inner_text()==name
        page.locator(f'.map-pin[data-village="{id}"]').click()
        assert page.locator('#dialog-title').inner_text()==name
        assert not any(old in page.locator('#dialog-content').inner_text() for old in OLD)
        page.evaluate('closeDialog()')
    for sample in ['lab','story','people','wide']:
        page.evaluate('(key)=>showSample(key)',sample)
        for step in ['core','connections','bridge','second','third','compare']:
            page.evaluate('(step)=>setTab(step)',step)
            assert not any(old in page.locator('#main').inner_text() for old in OLD)
        page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
        body=page.locator('.journey-report').inner_text()
        assert all(name in body for name in NAMES.values())
        assert not any(old in body for old in OLD)
        page.get_by_role('button',name='결과로 돌아가기',exact=True).click()
