from test_story_v3 import page, ROOT, OUT
import json

def sample(page):
    page.get_by_role('button',name='결과 예시',exact=True).click()
    page.locator('.sample-choice').first.click()

def test_report_graph_reference_last_and_export(page):
    sample(page)
    page.locator('#tab-compare').click()
    with page.expect_download() as d: page.get_by_role('button',name='기록 파일 저장',exact=True).click()
    target=OUT/'synthetic-example-v3.json'; d.value.save_as(target)
    data=json.loads(target.read_text(encoding='utf-8'))
    assert data['schema']=='momo-interest-record-v1'
    assert data['data_origin']=='SYNTHETIC_EXAMPLE'
    page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
    assert page.locator('.journey-report .village-discovery').count()==3
    assert page.locator('.interest-bar').count()==9
    for bar in page.locator('.interest-bar').all():
        id=bar.get_attribute('data-domain')
        row=next(r for r in data['result']['domains'] if r['domain_id']==id)
        assert float(bar.get_attribute('data-value'))==row['selected_count']/row['offered_count']
        assert f"{row['selected_count']} / {row['offered_count']}" in bar.inner_text()
    assert page.locator('.journey-report > :last-child').get_attribute('id')=='references'
    text=page.locator('.journey-report').inner_text()
    for banned in ['교육용 탐구 연결 제안','이렇게 시작해 보세요','다음 여행에서 직접 해볼 일','리포트를 읽는 방법과 자료 출처','계산 방법','확인 필요','자료 추적','비교값','÷']:
        assert banned not in text
    assert page.locator('.journey-report a[href^="http"]').count()>=6
    page.locator('#include-appendix').check()
    page.evaluate('window.print=()=>{window.printCalled=true}')
    page.get_by_role('button',name='인쇄 또는 PDF 저장',exact=True).click()
    assert page.evaluate('window.printCalled')
    assert page.locator('#print-root .response-appendix').count()==1
    assert page.locator('#print-root .journey-report > :last-child').get_attribute('id')=='references'
    page.emulate_media(media='print')
    page.pdf(path=str(OUT/'story-v3-with-appendix.pdf'),format='A4',print_background=True)
    page.emulate_media(media='screen')
    page.locator('#include-appendix').uncheck()
    page.get_by_role('button',name='인쇄 또는 PDF 저장',exact=True).click()
    assert page.locator('#print-root .response-appendix').count()==0
    page.emulate_media(media='print')
    page.pdf(path=str(OUT/'story-v3-report.pdf'),format='A4',print_background=True)
