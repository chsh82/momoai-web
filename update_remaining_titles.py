#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

PAGE_TITLES = {
    # Parent Portal (올바른 경로)
    'templates/parent/index.html': ('🏠 학부모 대시보드', '자녀 학습 현황'),
    'templates/parent/essays_index.html': ('📝 과제 및 첨삭', '자녀 과제 현황'),
    'templates/parent/attendance_index.html': ('✅ 출결 현황', '자녀 출석 기록'),
    'templates/parent/child_attendance.html': ('✅ 자녀 출결', None),
    'templates/parent/all_payments.html': ('💰 전체 결제 내역', '자녀별 결제 이력'),
    'templates/parent/child_payments.html': ('💰 결제 상세', None),
    'templates/parent/consultations_index.html': ('🗣️ 상담 내역', '자녀 상담 기록'),
    'templates/parent/makeup_classes_index.html': ('🔄 보강수업', '보강 신청 및 이력'),
    'templates/parent/makeup_classes_history.html': ('🔄 보강 이력', '전체 신청 내역'),
    'templates/parent/link_child.html': ('🔗 자녀 연결', '학생 계정 연결 신청'),
    'templates/parent/link_requests.html': ('🔗 연결 요청 관리', '신청 이력 조회'),
    'templates/parent/materials_index.html': ('📚 학습 교재', '자녀 열람 가능 교재'),
    'templates/parent/videos_index.html': ('🎬 학습 동영상', '자녀 열람 가능 동영상'),
    
    # Student Portal (올바른 경로)
    'templates/student/index.html': ('🏠 학생 대시보드', '내 학습 현황'),
    'templates/student/courses.html': ('📚 내 수업', '수강 중인 수업'),
    'templates/student/attendance.html': ('✅ 출결 현황', '내 출석 기록'),
    'templates/student/makeup_classes.html': ('🔄 보강수업', '보강 신청하기'),
    'templates/student/makeup_classes_history.html': ('🔄 보강 이력', '전체 신청 내역'),
    'templates/student/materials_index.html': ('📚 학습 교재', '열람 가능 교재'),
    'templates/student/videos_index.html': ('🎬 학습 동영상', '열람 가능 동영상'),
}

def add_page_title_to_template(filepath, title, subtitle=None):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '{% block page_title %}' in content:
            print(f"  Skip (already has title): {filepath}")
            return False
        
        title_pattern = r'({% block title %}.*?{% endblock %})'
        if not re.search(title_pattern, content):
            print(f"  Warning (no title block): {filepath}")
            return False
        
        new_blocks = f'\n\n{{% block page_title %}}{title}{{% endblock %}}'
        if subtitle:
            new_blocks += f'\n\n{{% block page_subtitle %}}\n<span class="text-sm text-white text-opacity-70 ml-3">{subtitle}</span>\n{{% endblock %}}'
        new_blocks += '\n'
        
        updated_content = re.sub(title_pattern, r'\1' + new_blocks, content, count=1)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"  Updated: {filepath}")
        return True
    except Exception as e:
        print(f"  Error ({filepath}): {e}")
        return False

updated = 0
skipped = 0
errors = 0

print("Updating remaining pages...")
for filepath, (title, subtitle) in PAGE_TITLES.items():
    if os.path.exists(filepath):
        if add_page_title_to_template(filepath, title, subtitle):
            updated += 1
        else:
            skipped += 1
    else:
        print(f"  Not found: {filepath}")
        errors += 1

print(f"\nResults: Updated={updated}, Skipped={skipped}, Errors={errors}")
