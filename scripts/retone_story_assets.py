"""Recolour supplied landscape pixels with Pillow, not generated raster artwork.
Characters remain their unmodified separate supplied assets.
"""
import base64,io,json,hashlib
from pathlib import Path
from PIL import Image,ImageOps,ImageEnhance,ImageChops,ImageDraw,ImageFont
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/exploration-story-v3'
PRIVATE=ROOT/'app/interest_quest/protected/story-assets'
TONES={'FOREST':('#102d32','#e3e9cf',.25),'LAB':('#142c56','#c3e2fa',.38),'FACTORY':('#5e2817','#ffe1ae',.31),'PLAZA':('#683d4a','#f7d8cc',.30),'CLINIC':('#1b5658','#d2f0e8',.27),'PORT':('#0c3a64','#b8e3ed',.38),'FIELD':('#29502a','#e4efb1',.29),'HOUSE':('#5b391b','#fbe7ad',.30),'STAGE':('#45345e','#e9d7ef',.36),'LANDSCAPE':('#233c5b','#d1e3de',.38)}
def main():
    PRIVATE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b=p.chromium.launch();page=b.new_page();page.goto((ROOT/'app/interest_quest/protected/index.html').as_uri());world=page.evaluate('WORLD');b.close()
    assets={};audit=[]
    sheet=Image.new('RGB',(920,240*len(TONES)), '#fffdf5');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
    for index,(id,(dark,light,blend)) in enumerate(TONES.items()):
        key='revision9-'+id+'.webp' if id in ['LAB','PLAZA','PORT','FIELD','HOUSE','STAGE','LANDSCAPE'] else 'village-'+id+'.webp'
        raw=base64.b64decode(world[key].split(',')[1]);before=Image.open(io.BytesIO(raw)).convert('RGB')
        coloured=ImageOps.colorize(ImageOps.grayscale(before),dark,light)
        after=Image.blend(before,coloured,blend)
        after=ImageEnhance.Contrast(after).enhance(1.06)
        buf=io.BytesIO();after.save(buf,format='WEBP',quality=88,method=6);result=buf.getvalue()
        (PRIVATE/(id+'.webp')).write_bytes(result)
        assets[id]='data:image/webp;base64,'+base64.b64encode(result).decode()
        decoded=Image.open(io.BytesIO(result)).convert('RGB')
        diff=ImageChops.difference(before,decoded)
        changed=sum(1 for pixel in diff.get_flattened_data() if pixel!=(0,0,0))
        audit.append({'id':id,'source_key':key,'source_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(result).hexdigest(),'dimensions':before.size,'changed_pixels':changed,'total_pixels':before.width*before.height,'dark':dark,'light':light,'blend':blend,'process':'Pillow luminance duotone blend + 1.06 contrast; original supplied landscape retained; separate character pixels unchanged'})
        y=index*240
        draw.text((15,y+4),id+'  BEFORE / AFTER',font=font,fill='#233e37')
        sheet.paste(ImageOps.fit(before,(440,200)),(10,y+32));sheet.paste(ImageOps.fit(decoded,(440,200)),(470,y+32))
    (PRIVATE/'embedded.json').write_text(json.dumps(assets,separators=(',',':')),encoding='utf-8')
    (OUT/'asset-retone-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    sheet.save(OUT/'village-before-after-contact-sheet.jpg',quality=90)
    print(json.dumps([{k:a[k] for k in ['id','dimensions','changed_pixels','total_pixels']} for a in audit]))
if __name__=='__main__':main()
