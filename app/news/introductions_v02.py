"""Approved v02 fallback; stored SiteContent remains the editable priority.

Enabled by default. An explicit non-True configuration disables the artwork.
No environment lookup, database seeding or publishing side effects.
"""
import json
from pathlib import Path
from flask import current_app


def candidate_pages(kind):
    if current_app.config.get('NEWS_INTRO_V02_ENABLED', True) is not True:
        return None
    source = json.loads(Path(__file__).with_name('introductions_v02.json').read_text(encoding='utf-8'))
    return source[kind + '_pages']
