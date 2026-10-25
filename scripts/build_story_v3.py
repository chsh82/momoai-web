"""Inline protected assets using bounded memory; no network."""
from pathlib import Path
import base64, hashlib, json, re
ROOT=Path(__file__).resolve().parents[1]
def build():
    base=ROOT/'app/interest_quest/protected'
    target=base/'index.html'
    marker='/* Student launch presentation: canonical inputs, ties and report remain unchanged. */'
    prefix=[]
    with target.open(encoding='utf-8') as source:
        for line in source:
            if marker in line:
                prefix.append(line.split(marker)[0]);break
            prefix.append(line)
        else: raise ValueError('Missing presentation marker')
    html=''.join(prefix)
    a='<!-- STORY_V3_STYLE -->'
    if a in html:
        begin=html.index(a);end=html.index('<!-- /STORY_V3_STYLE -->',begin)+len('<!-- /STORY_V3_STYLE -->')
        html=html[:begin]+html[end:]
    html=html.replace('</head>',a+'<style>'+(base/'story-v3.css').read_text(encoding='utf-8')+'</style><!-- /STORY_V3_STYLE --></head>')
    html=re.sub(r'<footer class="footer">[\s\S]*?</footer>','<footer class="footer"><p>모모의 이야기 탐험단 · 관심을 발견하는 여행<br>입력은 이 페이지에만 있어요. 닫기 전에 기록 파일로 저장해 주세요.</p></footer>',html)
    manifest=json.loads((base/'story-assets/v4-image-slots.json').read_text(encoding='utf-8'))
    embedded=json.loads((base/'story-assets/embedded.json').read_text(encoding='utf-8'))
    temporary=target.with_suffix('.building')
    try:
        with temporary.open('wb') as output:
            output.write((html+marker+'\nconst STORY_ASSETS={').encode('utf-8'))
            first=True
            def emit(key,value):
                nonlocal first
                output.write((('' if first else ',')+json.dumps(key)+':'+json.dumps(value,ensure_ascii=False)).encode('utf-8'))
                first=False
            for key,value in embedded.items(): emit(key,value)
            for slot in manifest['slots']:
                if slot['status']!='INTEGRATED_FILE_VERIFIED':continue
                raw=(base/slot['display_source']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=slot['display_sha256']:raise ValueError('Artwork changed: '+slot['id'])
                emit(slot['id'],'data:image/webp;base64,'+base64.b64encode(raw).decode('ascii'))
            output.write(b'};\nconst VILLAGE_CONTENT=')
            output.write((base/'story-v4-content.json').read_bytes())
            output.write(b';\nconst V4_IMAGE_SLOTS=')
            output.write((base/'story-assets/v4-image-slots.json').read_bytes())
            output.write(b';\n')
            for name in ['story-v3-illustrations.js','story-v3.js']:
                output.write((base/name).read_bytes());output.write(b'\n')
            output.write(b'</script></body></html>')
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
if __name__=='__main__':build()
