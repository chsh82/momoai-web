#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, re, sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

PAGE_TITLES = {
    'templates/student/teaching_materials.html': ('📚 학습 교재', '열람 가능 교재'),
    'templates/student/teaching_material_detail.html': ('📚 교재 상세', None),
    'templates/student/teaching_videos.html': ('🎬 학습 동영상', '열람 가능 동영상'),
    'templates/student/teaching_video_player.html': ('🎬 동영상 재생', None),
}

def add_page_title(fp, title, subtitle=None):
    try:
        with open(fp, 'r', encoding='utf-8') as f: content = f.read()
        if '{% block page_title %}' in content: return False
        if not re.search(r'{% block title %}', content): return False
        new = f'\n\n{{% block page_title %}}{title}{{% endblock %}}'
        if subtitle: new += f'\n\n{{% block page_subtitle %}}\n<span class="text-sm text-white text-opacity-70 ml-3">{subtitle}</span>\n{{% endblock %}}'
        content = re.sub(r'({% block title %}.*?{% endblock %})', r'\1' + new + '\n', content, 1)
        with open(fp, 'w', encoding='utf-8') as f: f.write(content)
        print(f"  Updated: {fp}")
        return True
    except: return False

updated = sum(add_page_title(fp, *data) for fp, data in PAGE_TITLES.items() if os.path.exists(fp))
print(f"\nFinal update: {updated} files")
