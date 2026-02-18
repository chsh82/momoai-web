#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, re, sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

PAGE_TITLES = {
    # Admin attendance
    'templates/admin/attendance_status.html': ('✅ 전체 출결 현황', '수업별 출석 통계'),
    
    # Teacher attendance
    'templates/teacher/attendance_list.html': ('✅ 출결 관리', '수업별 출석 현황'),
    'templates/teacher/check_attendance.html': ('✅ 출석 체크', '수업 출석 입력'),
    
    # Parent attendance (이미 업데이트된 것 제외)
    'templates/parent/attendance.html': ('✅ 출결 현황', '자녀 출석 상세'),
    
    # Student attendance (이미 업데이트됨)
}

def add_page_title(fp, title, subtitle=None):
    try:
        with open(fp, 'r', encoding='utf-8') as f: 
            content = f.read()
        
        if '{% block page_title %}' in content: 
            print(f"  Skip (already has title): {fp}")
            return False
        
        if not re.search(r'{% block title %}', content): 
            print(f"  Warning (no title block): {fp}")
            return False
        
        new = f'\n\n{{% block page_title %}}{title}{{% endblock %}}'
        if subtitle: 
            new += f'\n\n{{% block page_subtitle %}}\n<span class="text-sm text-white text-opacity-70 ml-3">{subtitle}</span>\n{{% endblock %}}'
        
        content = re.sub(r'({% block title %}.*?{% endblock %})', r'\1' + new + '\n', content, count=1)
        
        with open(fp, 'w', encoding='utf-8') as f: 
            f.write(content)
        
        print(f"  Updated: {fp}")
        return True
    except Exception as e:
        print(f"  Error: {fp} - {e}")
        return False

print("Updating attendance pages...")
updated = 0
for fp, (title, subtitle) in PAGE_TITLES.items():
    if os.path.exists(fp):
        if add_page_title(fp, title, subtitle):
            updated += 1

print(f"\nTotal updated: {updated} files")
