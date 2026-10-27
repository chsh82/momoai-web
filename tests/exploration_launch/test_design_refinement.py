"""Student-readable welcome, village transitions, result map and spacing."""
from v02_helpers import open_report
import json
from pathlib import Path
from test_story_v3 import page, ROOT
OUT=ROOT/'reports/exploration-v4/design-refinement'
OUT.mkdir(exist_ok=True,parents=True)

def test_welcome_explains_nine_villages_and_three_discoveries(page):
    messages=[]
    for i in range(4):
        messages.append(page.locator('.speech p').inner_text())
        if i<3: page.get_by_role('button',name='다음 이야기',exact=True).click()
    expected=page.evaluate('MOMOTOWN_V02.opening')
    assert messages==[expected['admin_first']]+expected['student'][1:]
    combined=' '.join(messages)
    assert all(t in combined for t in ['아홉','하나의 모모타운','하고 싶은 일','세 마을','마음에 든 곳'])
    page.get_by_role('button',name='초대장 펼치기',exact=True).click()
    assert '9개' in page.locator('.invitation-layout .lead').inner_text()

def test_bridge_explains_companion_villages_before_second_and_third(page):
    page.evaluate("showSample('story')")
    score=page.evaluate('JSON.stringify(sampleSession.result)')
    page.locator('.launch-pager button').last.click()
    assert page.locator('#result-panel').get_attribute('data-step')=='connections'
    page.locator('.launch-pager button').last.click()
    assert page.locator('#result-panel').get_attribute('data-step')=='bridge'
    bridge=page.locator('.village-transition')
    assert all(t in bridge.inner_text() for t in ['두 번째','세 번째','다른 호기심','실력'])
    assert bridge.locator('[data-companion]').count()==2
    expected=page.evaluate('reportModel(sampleSession).paths.slice(1).map(p=>p.row.domain_id)')
    assert bridge.locator('[data-companion]').evaluate_all('(es)=>es.map(e=>e.dataset.companion)')==expected
    page.get_by_role('button',name='두 번째 마을 만나기',exact=True).click()
    assert page.locator('#result-panel').get_attribute('data-step')=='second'
    assert page.locator('#result-panel .village-discovery').get_attribute('data-village')==expected[0]
    page.locator('.launch-pager button').last.click()
    assert page.locator('#result-panel').get_attribute('data-step')=='third'
    assert '세 번째' in page.locator('.companion-arrival').inner_text()
    assert page.locator('#result-panel .village-discovery').get_attribute('data-village')==expected[1]
    page.locator('.launch-pager button').first.click()
    assert page.locator('#result-panel').get_attribute('data-step')=='second'
    assert page.evaluate('JSON.stringify(sampleSession.result)')==score
    assert page.locator('#result-progress').inner_text()=='4 / 6'

def test_report_map_follows_third_village_and_keeps_the_real_three_results(page):
    for key in ['story','lab','people','wide']:
        page.evaluate('(key)=>showSample(key)',key)
        open_report(page)
        expected=page.evaluate("Object.fromEntries(reportModel(sampleSession).paths.map(p=>[p.row.domain_id,String(p.slot)]))")
        section=page.locator('#main .report-map-summary')
        assert section.count()==1
        order=page.locator('#main .journey-report').evaluate('(e)=>[...e.children].map(x=>x.className)')
        assert order.index('report-page report-map-summary')==max(i for i,v in enumerate(order) if 'report-village-story' in v)+1
        assert order.index('report-page report-map-summary')<order.index('report-page report-comparison')
        assert section.locator('[data-map-village]').count()==9
        assert section.locator('.report-map-board > img').get_attribute('src')==page.evaluate('STORY_ASSETS.LANDSCAPE')
        actual=section.locator('[data-rank]').evaluate_all('(es)=>Object.fromEntries(es.map(e=>[e.dataset.mapVillage,e.dataset.rank]))')
        assert actual==expected
        assert section.locator('.map-rank').all_inner_texts() and sorted(section.locator('.map-rank').all_inner_texts())==['1','2','3']
        assert section.locator('.report-map-legend li').count()==3
        page.evaluate('()=>{window.print=()=>{}}')
        page.locator('.report-bottom-print button').click()
        printed=page.locator('#print-root .report-map-summary [data-rank]').evaluate_all('(es)=>Object.fromEntries(es.map(e=>[e.dataset.mapVillage,e.dataset.rank]))')
        assert printed==expected

def test_text_spacing_and_card_gutters_at_mobile_desktop_and_print(page):
    observations=[]
    for width in [390,1440]:
        page.set_viewport_size({'width':width,'height':950})
        page.evaluate("showSample('story');setTab('connections')")
        observations.append(page.locator('#result-panel .school-stage').first.evaluate('(e)=>({width:innerWidth,schoolPadding:parseFloat(getComputedStyle(e).paddingLeft)})'))
        page.locator('#result-panel .school-progression').screenshot(path=str(OUT/f'spacing-school-{width}.png'))
        open_report(page)
        observations[-1]['headingPadding']=page.locator('#main .report-heading').evaluate('(e)=>parseFloat(getComputedStyle(e).paddingLeft)')
        page.evaluate('()=>{window.print=()=>{}}')
        page.locator('.report-bottom-print button').click()
        page.emulate_media(media='print')
        observations[-1]['printLineRatio']=page.locator('#print-root .host-intro p').first.evaluate('(e)=>{const s=getComputedStyle(e);return parseFloat(s.lineHeight)/parseFloat(s.fontSize)}')
        page.emulate_media(media='screen')
    (OUT/'spacing-after.json').write_text(json.dumps(observations,indent=2),encoding='utf-8')
    for row in observations:
        assert row['schoolPadding']>=18,row
        assert row['headingPadding']>=18,row
        assert row['printLineRatio']>=1.69,row

def test_mobile_menu_is_collapsed_until_requested_and_closes_after_navigation(page):
    page.set_viewport_size({'width':390,'height':844})
    assert not page.locator('.nav').is_visible()
    toggle=page.get_by_role('button',name='메뉴',exact=True)
    assert toggle.is_visible() and toggle.get_attribute('aria-expanded')=='false'
    assert page.locator('.top').bounding_box()['height']<130
    toggle.click()
    assert page.locator('.nav').is_visible() and toggle.get_attribute('aria-expanded')=='true'
    page.keyboard.press('Escape')
    assert not page.locator('.nav').is_visible()
    assert toggle.evaluate('(e)=>e===document.activeElement')
    toggle.click()
    page.get_by_role('button',name='마을 전체 지도',exact=True).click()
    assert page.locator('.story-atlas').is_visible()
    assert not page.locator('.nav').is_visible() and toggle.get_attribute('aria-expanded')=='false'
    page.set_viewport_size({'width':1440,'height':950})
    # v02 deliberately uses the same explicit collapsed menu at every width.
    # Preserve actual desktop reachability rather than require auto-expansion.
    assert not page.locator('.nav').is_visible() and toggle.is_visible()
    toggle.click()
    assert page.locator('.nav').is_visible() and toggle.get_attribute('aria-expanded')=='true'
    assert page.get_by_role('button',name='마을 전체 지도',exact=True).is_visible()
    page.keyboard.press('Escape')
    assert not page.locator('.nav').is_visible()
    assert toggle.evaluate('(e)=>e===document.activeElement')

def test_map_labels_stay_inside_the_board_without_overlap(page):
    audit=[]
    for width in [320,390,768,1440]:
        page.set_viewport_size({'width':width,'height':950})
        page.evaluate("showSample('story')")
        open_report(page)
        row=page.locator('#main .report-map-board').evaluate("""board=>{const b=board.getBoundingClientRect();return {width:innerWidth,board:{x:b.x,y:b.y,right:b.right,bottom:b.bottom},places:[...board.querySelectorAll('[data-map-village]')].map(e=>{const r=e.getBoundingClientRect();return {id:e.dataset.mapVillage,x:r.x,y:r.y,right:r.right,bottom:r.bottom}})}}""")
        audit.append(row)
    (OUT/'map-layout-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    for row in audit:
        b=row['board']
        for r in row['places']:
            assert r['x']>=b['x']-1 and r['right']<=b['right']+1 and r['y']>=b['y']-1 and r['bottom']<=b['bottom']+1,(row['width'],r,b)
        for i,a in enumerate(row['places']):
            for other in row['places'][i+1:]:
                overlap=min(a['right'],other['right'])-max(a['x'],other['x'])>1 and min(a['bottom'],other['bottom'])-max(a['y'],other['y'])>1
                assert not overlap,(row['width'],a,other)

def test_mobile_result_navigation_is_one_row_and_keeps_current_step_visible(page):
    page.set_viewport_size({'width':390,'height':844})
    page.evaluate("showSample('story')")
    for tab in ['connections','bridge','second','third','compare']:
        page.evaluate('(tab)=>setTab(tab)',tab)
        box=page.locator('.launch-tabs').bounding_box()
        current=page.locator('#tab-'+tab).bounding_box()
        assert box['height']<=74,box
        assert current['x']>=box['x']-1 and current['x']+current['width']<=box['x']+box['width']+1,(tab,box,current)
