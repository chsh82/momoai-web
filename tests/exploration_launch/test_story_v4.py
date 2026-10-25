"""Approved v4 behavior: local protected artifact, real Chromium, no HTTP."""
from test_story_v3 import page, ROOT
import pytest

@pytest.mark.parametrize('domain',['FOREST','LAB','FACTORY','PLAZA','CLINIC','PORT','FIELD','HOUSE','STAGE'])
def test_complete_village_story_and_learning(page,domain):
    page.evaluate('(id)=>pickVillage(id)',domain)
    v=page.evaluate('(id)=>VILLAGE_STORY[id]',domain)
    assert page.locator('#dialog-content .discovery-copy h2').first.inner_text()==v['name']+'을 소개할게'
    assert page.locator('.host-intro p').count() in (2,3)
    assert '마을 속 창작 이야기' in page.locator('#dialog-content').inner_text()
    assert page.locator('.village-news p').inner_text()
    assert page.locator('.village-books').inner_text()
    assert page.locator('.career-scene').count()==2
    assert page.locator('.career-scene p').first.inner_text().count('.')>=2
    assert page.locator('.school-stage').count()==3
    for stage in page.locator('.school-stage').all():
        assert stage.locator('img').count()==1
        assert stage.locator('li').count()==3
        assert all(len(t)>20 for t in stage.locator('li').all_inner_texts())
    assert page.locator('#dialog-content svg').count()==0
    assert '학교에서는 이렇게 연결돼요' not in page.locator('#dialog-content').inner_text()


@pytest.mark.parametrize('key',['lab','story','people','wide'])
def test_report_core_first_print_and_computed_qa_labels(page,key):
    page.evaluate('enableLocalStoryQA();showSamples()')
    expected=page.evaluate("['lab','story','people','wide'].map(k=>villageName(reportModel(qaSampleSession(k)).paths[0].row.domain_id))")
    assert page.locator('.sample-choice b').all_inner_texts()==expected
    page.evaluate('(key)=>showSample(key)',key)
    core=page.evaluate('villageName(reportModel(sampleSession).paths[0].row.domain_id)')
    page.evaluate('printResult()')
    assert page.locator('.journey-report h1').inner_text()==f'나에게 잘 어울리는 {core}을 소개합니다!'
    assert '가상 예시' in page.locator('.journey-report > :first-child').inner_text()
    order=page.locator('.journey-report').evaluate('(e)=>[...e.children].map(x=>x.className)')
    assert order.index('report-page report-comparison')>max(i for i,v in enumerate(order) if 'report-village-story' in v)
    assert page.locator('.journey-report > :last-child').get_attribute('id')=='references'
    assert page.locator('.report-bottom-print button').get_attribute('onclick')=='printUnified()'
    page.evaluate('()=>{window.printCalls=0;window.print=()=>{window.printCalls++}}')
    page.locator('.report-bottom-print button').click()
    assert page.evaluate('window.printCalls')==1
    assert page.locator('#print-root .no-print').count()==0
    assert page.evaluate('()=>{const ids=[...document.querySelectorAll("[id]")].map(e=>e.id);return ids.length===new Set(ids).size}')
    assert page.locator('.story-report svg').count()==0

def test_pdf_first_page_contains_core_scene(page):
    import fitz
    page.evaluate("showSample('story');printResult()")
    page.evaluate('()=>{window.print=()=>{}}')
    page.locator('.report-bottom-print button').click()
    page.emulate_media(media='print')
    document=fitz.open(stream=page.pdf(format='A4',print_background=True),filetype='pdf')
    assert len(document[0].get_images())>0
    assert '소개할게' in document[0].get_text()

def test_compact_story_is_complete_but_shorter(page):
    result=page.evaluate('''()=>{const p={slot:2,row:{domain_id:'FACTORY',evidence:[]},codes:[],catalogCodes:BRIDGE_BY_VILLAGE.get('FACTORY').group_codes};const el=document.createElement('div');el.innerHTML=discovery(p,false);const full=el.querySelector('.village-news p').textContent;el.innerHTML=discovery(p,true);return {full,compact:el.querySelector('.village-news p').textContent,intros:el.querySelectorAll('.host-intro p').length,books:!!el.querySelector('.village-books')}}''')
    assert len(result['compact'])<len(result['full'])
    assert result['intros']==2 and result['books']

@pytest.mark.parametrize('width',[390,1440])
def test_public_navigation_and_atlas_targets(page,width):
    page.set_viewport_size({'width':width,'height':950})
    assert page.locator('.brand strong').inner_text()=='모모아이 전공마을 탐색'
    assert page.locator('.brand small').inner_text()=='나의 호기심으로 시작하는 나만의 이야기'
    assert page.locator('.brand-mark').count()==0
    assert page.locator('.nav button[onclick="showSamples()"] ').count()==0
    page.evaluate('showSamples()')
    assert page.locator('.sample-choice').count()==0
    page.evaluate('showAtlas()')
    assert page.locator('.nav [aria-current="page"]').inner_text()=='마을 전체 지도'
    assert page.locator('.nav button[onclick*="storyStart"]').get_attribute('aria-current') is None
    target=page.locator('.map-pin[data-village="FOREST"]')
    assert target.locator('img').count()==1
    target.locator('img').click()
    assert page.locator('#dialog').evaluate('(e)=>e.open')
    page.evaluate('closeDialog()')
    target.focus();page.keyboard.press('Enter')
    assert page.locator('#dialog').evaluate('(e)=>e.open')
    page.evaluate('closeDialog();showGallery()')
    assert page.locator('.gallery-button[onclick*="cassiopeia"]').evaluate('(e)=>{const a=e.querySelector("img").getBoundingClientRect();const b=e.getBoundingClientRect();return a.width/b.width}') < .71
