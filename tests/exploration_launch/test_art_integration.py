"""External art stays private and separately gated from visual approval."""
import base64, hashlib, io, json, subprocess, sys
from pathlib import Path
from PIL import Image
from test_story_v3 import page
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'app/interest_quest/protected'

def test_verified_sources_survive_manifest_rebuild():
    subprocess.run([sys.executable,str(ROOT/'scripts/build_story_v4_manifest.py')],check=True)
    m=json.loads((BASE/'story-assets/v4-image-slots.json').read_text(encoding='utf-8'))
    assert m['integration_status']=='integrated_file_verified'
    assert m['visual_approval']=='pending_visual_approval'
    assert m['art_ready'] is False
    assert len(m['slots'])==39
    provenance=json.loads((BASE/'story-assets/v4-source-provenance.json').read_text(encoding='utf-8'))
    assert provenance['archive_sha256']=='99ccc912ca6c1e1e3b6e4cce7ea834cbe2edee04bc12cba6cbf83c5e29fa753a'
    assert set(provenance['files'])=={s['id'] for s in m['slots']}
    for s in m['slots']:
        expected=provenance['files'][s['id']]
        raw=(BASE/s['source']).read_bytes()
        assert s['filename']==expected['filename']
        assert hashlib.sha256(raw).hexdigest()==s['sha256']==expected['sha256']
        im=Image.open(io.BytesIO(raw)); im.load()
        assert im.format=='WEBP'
        assert list(im.size)==s['dimensions']==expected['dimensions']
        assert s['status']=='INTEGRATED_FILE_VERIFIED'


def test_inline_artifact_has_bounded_size():
    assert (BASE/'index.html').stat().st_size < 25_000_000

def test_all_slots_render_exact_inline_bytes_and_honest_fallback(page):
    m=json.loads((BASE/'story-assets/v4-image-slots.json').read_text(encoding='utf-8'))
    actual=page.evaluate("Object.fromEntries(V4_IMAGE_SLOTS.slots.map(s=>[s.id,STORY_ASSETS[s.id]]))")
    assert set(actual)=={s['id'] for s in m['slots']}
    for s in m['slots']:
        assert actual[s['id']].startswith('data:image/webp;base64,')
        assert base64.b64decode(actual[s['id']].split(',')[1])==(BASE/s['display_source']).read_bytes()
        assert hashlib.sha256((BASE/s['display_source']).read_bytes()).hexdigest()==s['display_sha256']
    page.evaluate('goHome()')
    assert page.locator('.story-roadmap .pending-art').count()==0
    for domain in ['FOREST','LAB','FACTORY','PLAZA','CLINIC','PORT','FIELD','HOUSE','STAGE']:
        page.evaluate('(id)=>pickVillage(id)',domain)
        assert page.locator('#dialog-content .village-landscape > img').first.get_attribute('src')==actual['village-'+domain]
        assert page.locator('#dialog-content .pending-art').count()==0
        assert '새 장면 그림 준비 중' not in page.locator('#dialog-content').inner_text()
        for i in range(2):
            assert page.locator('.career-scene img').nth(i).get_attribute('src')==actual[f'career-{domain}-{i+1:02}']
        for i in range(3):
            image=page.locator('.school-stage img').nth(i)
            assert image.get_attribute('src')==actual['school-'+domain]
            assert image.evaluate('(e)=>getComputedStyle(e).objectPosition')==['0% 50%','50% 50%','100% 50%'][i]
            assert image.evaluate('(e)=>e.naturalWidth/e.naturalHeight')==4.5
        page.evaluate('closeDialog()')
    fallback=page.evaluate("()=>{const src=STORY_ASSETS['career-FOREST-01'];delete STORY_ASSETS['career-FOREST-01'];const result=slotImage('career-FOREST-01');STORY_ASSETS['career-FOREST-01']=src;return result}")
    assert '준비 중' in fallback and 'pending-art' in fallback


def test_equal_school_panel_geometry_in_screen_and_print(page):
    for width in [390,1440]:
        page.set_viewport_size({'width':width,'height':950})
        page.evaluate("showSample('story');printResult()")
        page.evaluate('()=>{window.print=()=>{}}')
        page.locator('.report-bottom-print button').click()
        for media,root in [('screen','#main .journey-report'),('print','#print-root')]:
            page.emulate_media(media=media)
            images=page.locator(root+' .school-stage img')
            assert images.count()==9
            for image in images.all():
                geometry=image.evaluate('(e)=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height,fit:getComputedStyle(e).objectFit})')
                assert abs(geometry['w']/geometry['h']-1.5)<0.01,geometry
                assert geometry['fit']=='cover'
        page.emulate_media(media='screen')
