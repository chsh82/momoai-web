"""Generate image handoff metadata, not illustrations. Local files only."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'app/interest_quest/protected'

def build():
    content=json.loads((BASE/'story-v4-content.json').read_text(encoding='utf-8'))
    import re
    names=dict(re.findall(r"(\w+):\{name:'([^']+)'",(BASE/'story-v3.js').read_text(encoding='utf-8')))
    slots=[]
    for domain,c in content.items():
        slots.append(dict(id='village-'+domain,filename='village-'+domain+'.webp',alt=names[domain]+' 마을의 생활 풍경',aspect='3:2',slot='village-landscape / atlas',fallback_asset=domain,status='PENDING_EXTERNAL_ART'))
        for i,job in enumerate(c['jobs'],1):
            slots.append(dict(id=f'career-{domain}-{i:02}',filename=f'career-{domain}-{i:02}.webp',alt=job[0]+'의 작업 장면',aspect='3:2',slot=f'career-scene {i}',fallback_asset=domain,status='PENDING_EXTERNAL_ART'))
        slots.append(dict(id='school-'+domain,filename='school-'+domain+'.webp',alt=names[domain]+'의 초등·중등·고등 배움 장면',aspect='9:2',panel_aspect='3:2',panels=['초등','중등','고등'],slot='school-stage: 3 equal crops',fallback_asset=domain,status='PENDING_EXTERNAL_ART'))
    for name,fallback,alt in [('questions','MOMO_AMPHITHEATRE','이야기 속 활동을 고르는 장면'),('careers','FACTORY','공부와 직업을 탐색하는 장면'),('report','FOREST','나의 여행 기록을 돌아보는 장면')]:
        slots.append(dict(id='roadmap-'+name,filename='roadmap-'+name+'.webp',alt=alt,aspect='3:2',slot='home roadmap',fallback_asset=fallback,status='PENDING_EXTERNAL_ART'))
    result={'schema':'momo-protected-art-slots-v1','art_ready':False,'gate':'All slots use reused existing protected embedded artwork until external GPT files are supplied, reviewed, decoded and embedded. No SVG substitutes. Do not publish as finished original art.','import_policy':'Local reviewed WebP only; inline data in protected artifact through maintained builder. Never a public-static route or remote URL. school strips have 3 equal panels. Existing village fallback is a temporary scene, NOT occupation or school-specific art.','slots':slots}
    # Technical integration is not final visual approval. Never carry a stale ready flag.
    import hashlib, io
    from PIL import Image
    for slot in slots:
        source=Path('story-assets/external-v4')/slot['filename']
        path=BASE/source
        if not path.exists():
            continue
        raw=path.read_bytes()
        image=Image.open(io.BytesIO(raw)); image.load()
        expected=(9,2) if slot['id'].startswith('school-') else (3,2)
        if image.format!='WEBP' or image.width*expected[1]!=image.height*expected[0]:
            raise ValueError('Invalid verified artwork: '+slot['id'])
        # Bounded display derivatives only: originals stay byte-identical to intake.
        display_source=Path('story-assets/display-v4')/slot['filename']
        display=BASE/display_source
        display.parent.mkdir(exist_ok=True)
        encoded=io.BytesIO()
        display_size=(2880,640) if slot['id'].startswith('school-') else (960,640)
        image.resize(display_size,Image.Resampling.LANCZOS).save(encoded,format='WEBP',quality=80,method=6,exact=True)
        display_raw=encoded.getvalue()
        if not display.exists() or display.read_bytes()!=display_raw: display.write_bytes(display_raw)
        decoded=Image.open(io.BytesIO(display_raw)); decoded.load()
        if decoded.size!=display_size: raise ValueError('Invalid display dimensions')
        slot.update(source=source.as_posix(),sha256=hashlib.sha256(raw).hexdigest(),dimensions=list(image.size),status='INTEGRATED_FILE_VERIFIED',
                    display_source=display_source.as_posix(),display_sha256=hashlib.sha256(display_raw).hexdigest(),display_dimensions=list(decoded.size),
                    display_encoding='WebP quality=80 method=6; LANCZOS 960x640 per panel, no crop; lossy display derivative')
    integrated=sum(s['status']=='INTEGRATED_FILE_VERIFIED' for s in slots)
    result.update(integration_status='integrated_file_verified' if integrated==len(slots) else 'partial_or_missing',
                  visual_approval='pending_visual_approval',
                  gate='Files decoded and integrated locally when present. Final user screen/print visual approval is pending; no deployment approval.',
                  integrated_slots=integrated)
    (BASE/'story-assets/v4-image-slots.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{integrated}/{len(slots)} file-verified local slots; pending_visual_approval')
if __name__=='__main__':build()
