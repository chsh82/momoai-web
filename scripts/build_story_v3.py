"""Inline maintained v3 UI into the protected self-contained artifact. No network."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def build():
    target=ROOT/'app/interest_quest/protected/index.html'
    html=target.read_text(encoding='utf-8')
    marker='/* Student launch presentation: canonical inputs, ties and report remain unchanged. */'
    start=html.index(marker)
    assets=(ROOT/'app/interest_quest/protected/story-assets/embedded.json').read_text(encoding='utf-8')
    illustrations=(ROOT/'app/interest_quest/protected/story-v3-illustrations.js').read_text(encoding='utf-8')
    html=html[:start]+marker+'\nconst STORY_ASSETS='+assets+';\n'+illustrations+'\n'+(ROOT/'app/interest_quest/protected/story-v3.js').read_text(encoding='utf-8')+'\n</script></body></html>'
    css=(ROOT/'app/interest_quest/protected/story-v3.css').read_text(encoding='utf-8')
    a='<!-- STORY_V3_STYLE -->'
    if a in html:
        begin=html.index(a); end=html.index('<!-- /STORY_V3_STYLE -->',begin)+len('<!-- /STORY_V3_STYLE -->')
        html=html[:begin]+html[end:]
    html=html.replace('</head>',a+'<style>'+css+'</style><!-- /STORY_V3_STYLE --></head>')
    import re
    html=re.sub(r'<footer class="footer">[\s\S]*?</footer>', '<footer class="footer"><p>모모의 이야기 탐험단 · 관심을 발견하는 여행<br>입력은 이 페이지에만 있어요. 닫기 전에 기록 파일로 저장해 주세요.</p></footer>', html)
    target.write_text(html,encoding='utf-8')
if __name__=='__main__': build()
