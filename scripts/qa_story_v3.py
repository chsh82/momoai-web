"""Local QA evidence and PDF contact sheets; no application startup/network."""
import json,hashlib,subprocess,xml.etree.ElementTree as ET,ast,base64,io
from pathlib import Path
from typing import Any,cast
from PIL import Image,ImageDraw,ImageFont,ImageOps
import fitz
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/exploration-story-v3'

def contact(paths,target,cols=4,w=300,h=360):
    paths=list(paths)
    sheet=Image.new('RGB',(cols*w,((len(paths)+cols-1)//cols)*h),'#ebece6');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',13)
    for i,path in enumerate(paths):
        im=Image.open(path).convert('RGB');im.thumbnail((w-20,h-38))
        x=(i%cols)*w+10;y=(i//cols)*h
        draw.text((x,y+5),path.name,font=font,fill='#203d32');sheet.paste(im,(x,y+30))
    sheet.save(target,quality=91)

def main():
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True);c=b.new_context(viewport={'width':1440,'height':950})
        c.route('http://**/*',lambda r:r.abort());c.route('https://**/*',lambda r:r.abort())
        page=c.new_page();errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri())
        assets=page.evaluate('({...WORLD,...STORY_ASSETS,...ASSETS})');sizes={}
        for name,src in assets.items():
            im=Image.open(io.BytesIO(base64.b64decode(src.split(',')[1])));im.load();sizes[name]={'size':im.size,'format':im.format}
        (OUT/'decoded-image-audit.json').write_text(json.dumps(sizes,indent=2),encoding='utf-8')
        manifest=page.evaluate('Object.entries(VILLAGE_STORY).map(([id,v])=>({domain_id:id,scene_file:"story-assets/"+id+".webp",...v}))')
        (OUT/'village-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        for width in (390,1440):
            page.set_viewport_size({'width':width,'height':950});page.evaluate('replayGreeting()')
            page.screenshot(path=str(OUT/f'greeting-final-{width}.png'),full_page=True)
            page.get_by_role('button',name='안내 건너뛰기',exact=True).click()
            page.screenshot(path=str(OUT/f'invitation-final-{width}.png'),full_page=True)
            page.get_by_role('button',name='마을 지도 둘러보기',exact=True).click()
            page.screenshot(path=str(OUT/f'atlas-final-{width}.png'),full_page=True)
            page.get_by_role('button',name='결과 예시',exact=True).click();page.locator('.sample-choice').first.click()
            for i,tab in enumerate(['core','connections','second','third','compare']):
                page.locator('#tab-'+tab).click();page.screenshot(path=str(OUT/f'final-{width}-step-{i+1}.png'),full_page=True)
            page.get_by_role('button',name='전체 리포트 보기',exact=True).click()
            page.screenshot(path=str(OUT/f'report-screen-{width}.png'),full_page=True)
            page.evaluate('window.print=()=>{}');page.get_by_role('button',name='인쇄 또는 PDF 저장',exact=True).click()
            page.emulate_media(media='print');page.pdf(path=str(OUT/f'final-report-{width}.pdf'),format='A4',print_background=True);page.emulate_media(media='screen')
        assert not errors,errors
        assert not requests,requests
        (OUT/'browser-evidence.json').write_text(json.dumps({'console_errors':errors,'http_https_requests_attempted':requests,'network_policy':'HTTP and HTTPS aborted by context routes; file/data only','images_decoded':len(sizes)},indent=2),encoding='utf-8')
        page.set_viewport_size({'width':1440,'height':950})
        page.evaluate("document.querySelector('#main').innerHTML='<h1>직업 창작 일러스트 · 18분야</h1><div style=\"display:grid;grid-template-columns:repeat(3,1fr);gap:20px\">'+[...MAJORS.values()].map(g=>'<article>'+occupationArt(g.code,g.career_inquiry_drafts[0].role)+'<h2>'+esc(g.name_original)+'</h2><p>'+esc(g.career_inquiry_drafts[0].role)+'</p></article>').join('')+'</div>'")
        page.screenshot(path=str(OUT/'career-illustrations-contact-sheet.png'),full_page=True)
        b.close()
    pdfinfo=[];thumbs=[]
    doc=fitz.open(OUT/'final-report-1440.pdf')
    for i in range(len(doc)):
        page=doc[i]
        pix=page.get_pixmap(matrix=fitz.Matrix(.8,.8));target=OUT/f'pdf-page-{i+1:02}.png';pix.save(target);thumbs.append(target)
        text_dict=cast(dict[str,Any],page.get_text('dict'))
        spans=[s for block in text_dict['blocks'] if 'lines' in block for line in block['lines'] for s in line['spans'] if s['text'].strip()]
        pdfinfo.append({'page':i+1,'size_pt':[page.rect.width,page.rect.height],'text_characters':len(page.get_text()),'min_font_pt':round(min(s['size'] for s in spans),2) if spans else None,'last_text':page.get_text()[-110:],'raster_images':len(page.get_images())})
    assert '<참고목록>' in doc[-1].get_text(),doc[-1].get_text()
    assert all(x['text_characters']>25 for x in pdfinfo)
    (OUT/'pdf-audit.json').write_text(json.dumps(pdfinfo,ensure_ascii=False,indent=2),encoding='utf-8')
    contact(thumbs,OUT/'pdf-contact-sheet.jpg',cols=3,w=320,h=480)
    contact([OUT/f'final-{width}-step-{i}.png' for width in (390,1440) for i in range(1,6)],OUT/'results-contact-sheet.jpg',cols=5,w=300,h=600)
    contact([OUT/f'greeting-final-{w}.png' for w in (390,1440)]+[OUT/f'chapter-final-{i}.png' for i in range(1,5)],OUT/'story-scenes-contact-sheet.jpg',cols=3,w=400,h=500)
    root=ET.parse(OUT/'full-suite.xml').getroot();suite=list(root)[0]
    summary:dict[str,object]={k:suite.attrib[k] for k in ['tests','failures','errors','skipped','time']}
    summary.update(pdf_pages=len(pdfinfo),pdf_min_font=min(x['min_font_pt'] for x in pdfinfo),decoded_images=len(sizes))
    (OUT/'verification-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
