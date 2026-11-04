"""Render the approved v02 artwork. Requires Pillow, Playwright and Chromium.

No app import, credentials, database or external HTTP. Malgun Gothic must be
installed for matching the approved Windows typography.
"""
from pathlib import Path
import io
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DEST = ROOT.parents[1] / 'static/news/introductions-v02'

if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            tab = browser.new_page(viewport={'width':1160, 'height':1800}, device_scale_factor=1)
            tab.route('http://**/*', lambda route: route.abort())
            tab.route('https://**/*', lambda route: route.abort())
            tab.goto((ROOT/'artwork.html').as_uri())
            tab.evaluate('document.fonts.ready')
            assert tab.evaluate("[...document.images].every(i => i.complete && i.naturalWidth > 0)")
            for kind in ('course', 'story'):
                for number in range(1,5):
                    name = f'{kind}-{number:02d}'
                    node = tab.locator('#'+name)
                    assert '미게시' not in node.inner_text()
                    image = Image.open(io.BytesIO(node.screenshot())).convert('RGB')
                    assert image.size == (1080, 2040 if name=='course-04' else 1800)
                    image.save(DEST/(name+'.webp'), quality=88, method=6)
            # The three original menu PNGs contain no text and remain unchanged.
        finally:
            browser.close()
    print('rendered 8 v02 release WebP pages; original menu PNGs preserved')
