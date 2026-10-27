"""Real Chromium line-assignment regression; local files, no student/API data.

CHOICE_LAYOUT_FIX=0 exercises exact pre-fix HTML. Default overlays the owned
CSS on both the live d31fcaf baseline and the integrated generated document,
so this test also works before the parent regenerates index.html.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROTECTED = ROOT / 'app/interest_quest/protected'
OUT = ROOT / 'reports/momotown-v02-review/layout'
SCRATCH = Path('C:/Users/aproa/AppData/Local/hermes/profiles/momo/cache/scratch')
MEASURE = r"""() => Array.from(document.querySelectorAll('.option')).map(e => {
 const word=e.querySelector('.word'), cs=getComputedStyle(e), ws=getComputedStyle(word);
 const walker=document.createTreeWalker(word,NodeFilter.SHOW_TEXT), lines=[];
 let node, index=0;
 while(node=walker.nextNode()) for(let i=0;i<node.length;i++,index++) {
   const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+1);
   const box=r.getBoundingClientRect();
   if(!box.width || !box.height) continue;
   let line=lines.find(l=>Math.abs(l.top-box.top)<1);
   if(!line){line={top:box.top,chars:[]};lines.push(line)}
   line.chars.push(index);
 }
 const radio=e.querySelector('input'), check=e.querySelector('.selected-check');
 return {lines:lines.map(l=>l.chars), text:word.textContent,
   weight:ws.fontWeight,font:ws.fontFamily,fontSize:ws.fontSize,
   width:word.getBoundingClientRect().width,labelWidth:e.getBoundingClientRect().width,
   border:[cs.borderTopWidth,cs.borderRightWidth,cs.borderBottomWidth,cs.borderLeftWidth],
   padding:[cs.paddingTop,cs.paddingRight,cs.paddingBottom,cs.paddingLeft],gap:cs.gap,
   radio:{width:radio.getBoundingClientRect().width,flexShrink:getComputedStyle(radio).flexShrink},
   check:{display:getComputedStyle(check).display,visibility:getComputedStyle(check).visibility,width:check.getBoundingClientRect().width},
   scrollbar:innerWidth-document.documentElement.clientWidth,
   checked:radio.checked};
})"""

@pytest.fixture(scope='module')
def chromium():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture(scope='module')
def documents():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=subprocess.check_output(['git','show','d31fcaf:app/interest_quest/protected/index.html'],cwd=ROOT)
    path=SCRATCH/'choice-layout-d31fcaf.html'
    path.write_bytes(baseline)
    return {'live-d31fcaf':path,'integrated':PROTECTED/'index.html'}

@pytest.mark.parametrize('width',[320,360,390,768,1440])
@pytest.mark.parametrize('variant',['live-d31fcaf','integrated'])
def test_choice_click_preserves_actual_text_lines(chromium,documents,width,variant):
    page=chromium.new_page(viewport={'width':width,'height':900})
    # Do not touch a production origin or load remote fonts/assets.
    page.route('http://**/*',lambda r:r.abort())
    page.route('https://**/*',lambda r:r.abort())
    source=documents[variant]
    embedded=os.environ.get('CHOICE_LAYOUT_EMBEDDED')=='1'
    stage='embedded' if embedded else ('before' if os.environ.get('CHOICE_LAYOUT_FIX')=='0' else 'after')
    page.goto(source.as_uri())
    if stage=='after':
        page.add_style_tag(content=(PROTECTED/'momotown-v02.css').read_text(encoding='utf8'))
    page.evaluate('init();view="question";render(false)')
    page.evaluate('document.fonts.ready')
    counts=page.evaluate('({questions:FORM.items.length,options:FORM.items.reduce((n,q)=>n+q.options.length,0)})')
    assert counts=={'questions':32,'options':128}
    failures=[];observations=[];clicks=0;rerenders=0;resets=0
    for q in range(counts['questions']):
        page.evaluate('(q)=>{session.cursor=q;session.values[q]=null;view="question";render(false)}',q)
        initial=page.evaluate(MEASURE)
        assert len(initial)==4
        for option in range(4):
            prior=page.evaluate(MEASURE)
            if q==0 and option==0:
                page.locator('.question-card').screenshot(path=str(OUT/f'{stage}-{variant}-{width}-unselected.png'))
            # Observe identity: choose should not need to rebuild the question DOM.
            page.evaluate('window.__choiceNode=document.querySelector(".option .word")')
            page.locator('.option input').nth(option).check()
            clicks+=1
            after=page.evaluate(MEASURE)
            same_node=page.evaluate('window.__choiceNode===document.querySelector(".option .word")')
            assert page.evaluate('session.values[session.cursor]')==page.locator('.option input').nth(option).input_value()
            assert sum(o['checked'] for o in after)==1
            if q==0 and option==0:
                page.locator('.question-card').screenshot(path=str(OUT/f'{stage}-{variant}-{width}-selected.png'))
            for i,(a,b) in enumerate(zip(initial,after)):
                if a['lines']!=b['lines']:
                    failures.append({'question':q+1,'clicked':option,'affected':i,'before':a,'after':b})
            observations.append({'question':q+1,'clicked':option,'same_node':same_node,'before':prior,'after':after})
            page.evaluate('render(false)');rerenders+=1
            rerendered=page.evaluate(MEASURE)
            assert [o['lines'] for o in rerendered]==[o['lines'] for o in after]
        page.evaluate('session.values[session.cursor]=null;render(false)');resets+=1
        assert [o['lines'] for o in page.evaluate(MEASURE)]==[o['lines'] for o in initial]
    # Native radio keyboard operation and the existing focus-visible affordance.
    page.locator('.option input').first.focus()
    page.keyboard.press('ArrowRight')
    assert page.locator('.option input').nth(1).is_checked()
    focused=page.locator('.option').nth(1).evaluate('(e)=>({style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth})')
    assert focused['style']!='none' and float(focused['width'].replace('px',''))>0
    selected=page.locator('.option').nth(1).locator('.selected-check')
    assert selected.is_visible()
    assert selected.get_attribute('aria-hidden')=='true'
    report={'variant':variant,'width':width,'stage':stage,'chromium':chromium.version,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'css_sha256':hashlib.sha256((PROTECTED/'momotown-v02.css').read_bytes()).hexdigest(),
            'counts':counts,'clicks':clicks,'rerenders':rerenders,'resets':resets,
            'failures':failures,'observations':observations,'focus':focused}
    (OUT/f'{stage}-{variant}-{width}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    page.close()
    assert not failures, f'{variant} {width}px: {len(failures)} line-assignment changes; see layout JSON'
