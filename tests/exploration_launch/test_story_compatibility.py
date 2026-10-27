from v02_helpers import open_report, navigation
from test_story_v3 import page,ROOT,OUT
from test_story_report import sample
import json

def test_old_v1_import_and_reset_confirmation(page):
    sample(page)
    page.locator('#tab-compare').click()
    with page.expect_download() as d:page.get_by_role('button',name='기록 파일 저장',exact=True).click()
    target=OUT/'compat-current.json';d.value.save_as(target)
    record=json.loads(target.read_text(encoding='utf-8'))
    record['form_version']=page.evaluate('FORM.form_version')
    record.pop('response_frame_version',None);record.pop('canonical_form_version',None)
    record['data_origin']='LOCAL_USER_INPUT'
    # An authentic old record cannot retain a v02 snapshot or copy identifier.
    record.pop('preference_snapshot',None);record.pop('copy_version',None)
    record['result']={'tampered':True}
    legacy=OUT/'compat-old-v1.json';legacy.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
    page.locator('#record-file').set_input_files(str(legacy))
    page.wait_for_function('session?.result!==null && view==="result"')
    assert page.evaluate('session.response_frame_version===FORM.form_version')
    assert page.evaluate('JSON.stringify(session.result)===JSON.stringify(InterestScoring.score(responseRows(session),FORM))')
    answers=page.evaluate('session.values.slice()')
    # Legacy results remain legacy; opening a v02 report must not relabel them.
    page.locator('#tab-compare').click()
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    assert page.locator('#dialog-title').inner_text()=='이전 안내 버전의 기록'
    assert page.get_by_role('button',name='새 방문 시작하기',exact=True).is_visible()
    assert page.evaluate('session.response_frame_version===FORM.form_version')
    assert page.locator('.journey-report').count()==0
    page.evaluate('closeDialog()')
    navigation(page, '첫 화면으로')
    assert page.evaluate('session.values')==answers
    page.get_by_role('button',name='새 탐험 시작하기',exact=True).click()
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    assert page.locator('#dialog-title').inner_text()=='새 탐험을 시작할까요?'
    page.get_by_role('button',name='취소',exact=True).click()
    assert page.evaluate('session.values')==answers
    page.get_by_role('button',name='첫 장면으로 가기 →',exact=True).click()
    page.get_by_role('button',name='새로 시작하기',exact=True).click()
    assert page.evaluate('session.values.every(v=>v===null)')
    assert page.evaluate('session.response_frame_version===FESTIVAL_FRAME')
    # The explicitly offered migration is a fresh visit, not relabeled history.
    page.locator('#record-file').set_input_files(str(legacy))
    page.wait_for_function('session?.result!==null && view==="result"')
    page.locator('#tab-compare').click()
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    assert page.locator('#dialog-title').inner_text()=='이전 안내 버전의 기록'
    page.get_by_role('button',name='새 방문 시작하기',exact=True).click()
    assert page.evaluate('session.response_frame_version===FESTIVAL_FRAME')
    assert page.evaluate('session.values.every(v=>v===null)')
    assert page.locator('.chapter-screen').is_visible()


def test_tied_representatives_and_all_ui_remove_method(page):
    found=page.evaluate('''(()=>{for(let seed=0;seed<128;seed++){let x=seed+1;const values=FORM.items.map(q=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return q.options[(x>>>16)%4].id});const s={values,origin:'SYNTHETIC_EXAMPLE',response_frame_version:FESTIVAL_FRAME};s.result=InterestScoring.score(responseRows(s),FORM);const m=reportModel(s);if(m.reps.some(r=>r.tied_ids.length)){sampleSession=s;view='sample';resultTab='core';render();return {seed,rows:m.reps,domains:s.result.domains}}}return null})()''')
    assert found
    assert page.evaluate('MOMOTOWN_V02.tie_copy') in page.locator('#main').inner_text()
    expected=sorted([r for r in found['domains'] if r['selected_count']>0],key=lambda r:(-r['comparison_units'],r['display_order']))[:3]
    assert [r['domain_id'] for r in found['rows']]==[r['domain_id'] for r in expected]
    for tab in ['core','connections','bridge','second','third','compare']:
        page.locator('#tab-'+tab).click()
        text=page.locator('body').inner_text()
        for forbidden in ['결과를 읽는 방법','자료 출처와 결과 계산 방법','다음 여행에서 직접 해볼 일','이렇게 시작해 보세요','확인 필요']:
            assert forbidden not in text
    open_report(page)
    assert page.locator('.journey-report > :last-child').get_attribute('id')=='references'
