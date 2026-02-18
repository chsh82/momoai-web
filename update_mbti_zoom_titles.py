#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, re, sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

PAGE_TITLES = {
    # Admin - MBTI & Zoom
    'templates/admin/mbti_result_detail.html': ('🧠 MBTI 결과 상세', '독서논술 성향 분석'),
    'templates/admin/zoom_links.html': ('🎥 줌 링크 관리', '강사별 줌 링크 설정'),
    'templates/admin/edit_zoom_link.html': ('✏️ 줌 링크 수정', None),
    'templates/admin/zoom_access_logs.html': ('📊 접속 로그', '줌 수업 접속 기록'),
    
    # Teacher - MBTI
    'templates/teacher/reading_mbti/index.html': ('🧠 독서논술 MBTI', '학생 성향 분석'),
    'templates/teacher/reading_mbti/course_stats.html': ('📊 수업별 MBTI 통계', None),
    'templates/teacher/reading_mbti/student_detail.html': ('🧠 학생 MBTI 상세', None),
    
    # Student - MBTI
    'templates/student/reading_mbti/index.html': ('🧠 독서논술 MBTI', '내 학습 성향 알아보기'),
    'templates/student/reading_mbti/take_test.html': ('📝 MBTI 테스트', '독서논술 성향 검사'),
    'templates/student/reading_mbti/result.html': ('🎯 MBTI 결과', '내 독서논술 성향'),
    
    # Parent - MBTI
    'templates/parent/reading_mbti/index.html': ('🧠 독서논술 MBTI', '자녀 학습 성향'),
    'templates/parent/reading_mbti/child_detail.html': ('🧠 자녀 MBTI 상세', None),
    
    # Zoom pages
    'templates/zoom/preview.html': ('🎥 줌 수업 입장', '수업 미리보기'),
    'templates/zoom/waiting.html': ('⏰ 수업 대기', '수업 시작 전'),
}

def add_page_title(fp, title, subtitle=None):
    try:
        with open(fp, 'r', encoding='utf-8') as f: 
            content = f.read()
        
        if '{% block page_title %}' in content: 
            print(f"  Skip: {fp}")
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

print("Updating MBTI, Zoom, and Log pages...")
updated = 0
for fp, (title, subtitle) in PAGE_TITLES.items():
    if os.path.exists(fp):
        if add_page_title(fp, title, subtitle):
            updated += 1
    else:
        print(f"  Not found: {fp}")

print(f"\nTotal updated: {updated} files")
