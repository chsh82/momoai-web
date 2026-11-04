# Approved v02 introduction release

- Source: the selected `momo-news-introductions-v02` artwork, not v03.
- `artwork.html` retains the source CSS, page content, characters and all educational notes. Only the eight centered review-only footer labels were removed. Outer review guides and the unrelated teacher questionnaire are not part of the renderer.
- `build.py` renders eight WebP pages using Playwright/Chromium, Pillow and the approved Windows Malgun Gothic typography. Run `python tools/news_introductions_v02/build.py` from the repository root. Three existing menu PNGs remain byte-identical to the selected v02 menu assets.
- The original source hash is recorded in `provenance.json`. Character sources are the same existing supplied assets; this release does not establish broader external-use licensing.
- Intro fallback is enabled when `NEWS_INTRO_V02_ENABLED` is absent. Explicit `False` (or another non-literal-True value) disables it in Flask. Existing nonempty SiteContent stays editable and is rendered instead of the fallback. GET does not insert records.
- A reverse proxy serving `/static/` directly does not execute Flask's explicit-disable guard. Proxy/cache behavior must be separately reconciled at deployment; these assets contain no private data.
- Existing community `Post.category == 'notice'` is presented as 모모공지 in the news hub. Original IDs, read/edit URLs, comments, files, admin write policy and the notice form option remain. Community index hides only that exact category; old `?category=notice` redirects after login to `/news/#momo-notices`. No database relocation or article seeding.
- The remote-master basis has no 모모뉴스 section. On the current dirty live hub, insert the notice partial immediately before the existing `member_news` assignment and preserve that entire publishing block exactly. Never replace the live hub or app factory with this remote-base file. A separate local reconciliation artifact verifies that seam.
- This source publication is NOT production deployment. Worker-fence evidence is required before a scoped installation/restart; master push/reset or the broad migration workflow is not appropriate for the dirty live runtime.

## Isolated verification

Set `COMMUNITY_TEST_SCRATCH` to an existing directory under the approved Davinci scratch root (the harness is intentionally Windows/workstation scoped). Run each in a fresh process:

```
python tests/news_introductions/test_routes.py
python tests/news_introductions/test_release.py
python tests/news_introductions/test_notices.py
python tests/community/test_education_articles.py
python tests/news_introductions/browser_qa.py news --output <evidence-dir>
python tests/news_introductions/browser_qa.py community --output <evidence-dir>
```

These use synthetic SQLite, a package shim and a minimal shell, not the production application factory or production authentication. They do not establish logged-in live acceptance. Existing SQLAlchemy, datetime and WTForms deprecation warnings remain.
