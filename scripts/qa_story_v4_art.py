"""v4 local-only artifact evidence. Never starts application or contacts network."""
from pathlib import Path
import base64, hashlib, io, json, subprocess
from PIL import Image
import fitz
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/exploration-v4/art-integration'
import sys

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    target=ROOT/'app/interest_quest/protected/index.html'
    before=hashlib.sha256(target.read_bytes()).hexdigest()
    subprocess.run([sys.executable,str(ROOT/'scripts/build_story_v3.py')],check=True,cwd=ROOT)
    assert before==hashlib.sha256(target.read_bytes()).hexdigest()
    from jinja2 import Environment
    Environment().parse(target.read_text(encoding='utf-8'))
    content=json.loads((ROOT/'app/interest_quest/protected/story-v4-content.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'app/interest_quest/protected/story-assets/v4-image-slots.json').read_text(encoding='utf-8'))
    static={'villages':len(content),'school_stages':sum(len(v['school']) for v in content.values()),'subject_explanations':sum(len(s) for v in content.values() for s in v['school']),'jobs':sum(len(v['jobs']) for v in content.values()),'image_slots':len(manifest['slots']),'unique_slot_ids':len({s['id'] for s in manifest['slots']}),'pending':sum(s['status']=='PENDING_EXTERNAL_ART' for s in manifest['slots']),'art_ready':manifest['art_ready'],'build_idempotent':True,'html_sha256':before,'jinja_parse':True}
    (OUT/'static-verification.json').write_text(json.dumps(static,indent=2),encoding='utf-8')
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        c=b.new_context(viewport={'width':1440,'height':950})
        c.route('http://**/*',lambda r:r.abort());c.route('https://**/*',lambda r:r.abort())
        page=c.new_page();page.set_default_timeout(120000);page.set_default_navigation_timeout(120000);errors=[];network=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
        audit={}
        for name,src in page.evaluate('({...WORLD,...STORY_ASSETS,...ASSETS})').items():
            im=Image.open(io.BytesIO(base64.b64decode(src.split(',')[1])));im.load()
            audit[name]={'format':im.format,'size':list(im.size)}
        (OUT/'decoded-image-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        (OUT/'village-character-topic-mapping.json').write_text(json.dumps(page.evaluate('Object.entries(VILLAGE_STORY).map(([id,v])=>({id,...v,group_codes:BRIDGE_BY_VILLAGE.get(id).group_codes,jobs:VILLAGE_CONTENT[id].jobs.map(j=>j[0])}))'),ensure_ascii=False,indent=2),encoding='utf-8')
        for width in [390,1440]:
            page.set_viewport_size({'width':width,'height':950})
            page.evaluate('goHome()');page.screenshot(path=str(OUT/f'home-{width}.png'),full_page=True)
            assert page.locator('.story-roadmap svg').count()==0
            page.evaluate('showAtlas()');page.screenshot(path=str(OUT/f'atlas-{width}.png'),full_page=True)
            for id in content:
                page.evaluate('(id)=>pickVillage(id)',id)
                page.locator('#dialog').screenshot(path=str(OUT/f'dialog-{id}-{width}.png'))
                page.locator('#dialog-content .school-progression').screenshot(path=str(OUT/f'school-{id}-{width}.png'))
                assert page.locator('#dialog-content .pending-art').count()==0
                for image in page.locator('#dialog-content img').all():
                    assert image.evaluate('(e)=>e.complete && e.naturalWidth>0')
                page.evaluate('closeDialog()')
            page.evaluate("showSample('story')")
            for tab in ['core','connections','second','third','compare']:
                page.locator('#tab-'+tab).click();page.screenshot(path=str(OUT/f'result-{tab}-{width}.png'),full_page=True)
            page.evaluate('printResult()')
            page.screenshot(path=str(OUT/f'report-{width}.png'),full_page=True)
            page.evaluate('()=>{window.print=()=>{}}')
            page.locator('.report-bottom-print button').click()
            page.emulate_media(media='print');page.pdf(path=str(OUT/f'report-{width}.pdf'),format='A4',print_background=True);page.emulate_media(media='screen')
        # Server-served artifact cannot enable local QA, even with opt-in query.
        html=(ROOT/'app/interest_quest/protected/index.html').read_text(encoding='utf-8')
        server=c.new_page();server.route('https://local.invalid/**',lambda r:r.fulfill(status=200,content_type='text/html',body=html))
        server.goto('https://local.invalid/?admin=1&qa=1')
        assert server.evaluate('enableLocalStoryQA()') is False
        server.evaluate('showSamples()');assert server.locator('.sample-choice').count()==0
        b.close()
    assert errors==[],errors
    assert network==[],network
    pdf=fitz.open(OUT/'report-1440.pdf')
    pdf_audit=[]
    for i,p in enumerate(pdf):
        text=p.get_text();assert text.strip(),f'blank page {i+1}'
        pdf_audit.append({'page':i+1,'characters':len(text),'images':len(p.get_images()),'last_text':text[-100:]})
    assert '<참고목록>' in pdf[-1].get_text()
    assert '인쇄 또는 PDF 저장' not in ''.join(p.get_text() for p in pdf)
    (OUT/'pdf-audit.json').write_text(json.dumps(pdf_audit,ensure_ascii=False,indent=2),encoding='utf-8')
    pdf[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(OUT/'pdf-first-page.png')
    for i in range(len(pdf)):
        pdf[i].get_pixmap(matrix=fitz.Matrix(1,1)).save(OUT/f'pdf-page-{i+1:02}.png')
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'app/interest_quest/protected/index.html',ROOT/'app/interest_quest/protected/story-v3.js',ROOT/'app/interest_quest/protected/story-v3.css',ROOT/'app/interest_quest/protected/story-v4-content.json',ROOT/'app/interest_quest/protected/story-assets/v4-image-slots.json']}
    (OUT/'source-hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    summary={'console_errors':errors,'external_requests_attempted':network,'decoded_images':len(audit),'pdf_pages':len(pdf),'art_ready':manifest['art_ready'],'pending_slots':static['pending'],'integration_status':manifest['integration_status'],'visual_approval':manifest['visual_approval'],'server_query_does_not_enable_qa':True}
    (OUT/'artifact-audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
