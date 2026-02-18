#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
주요 페이지에 동적 제목 추가 스크립트
"""

import os
import re
import sys

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 페이지별 제목 매핑
PAGE_TITLES = {
    # Admin Portal
    'templates/admin/index.html': ('📊 관리자 대시보드', '전체 현황 및 통계'),
    'templates/admin/courses.html': ('📚 수업 관리', '전체 수업 목록'),
    'templates/admin/course_detail.html': ('📚 수업 상세', None),
    'templates/admin/course_form.html': ('➕ 수업 생성', None),
    'templates/admin/create_course_new.html': ('➕ 새 수업 만들기', None),
    'templates/admin/all_schedule.html': ('📅 전체 수업 현황', '주간 시간표'),
    'templates/admin/students.html': ('👥 학생 관리', '전체 학생 목록'),
    'templates/admin/student_profiles.html': ('📋 학생 프로필 관리', '기초 조사 및 프로필'),
    'templates/admin/consultations.html': ('🗣️ 상담 관리', '전체 상담 기록'),
    'templates/admin/consultation_detail.html': ('🗣️ 상담 상세', None),
    'templates/admin/payments.html': ('💰 수납 관리', '전체 결제 내역'),
    'templates/admin/payment_detail.html': ('💰 결제 상세', None),
    'templates/admin/parent_link_requests.html': ('🔗 학부모 연결 관리', '학부모-자녀 연결 요청'),
    'templates/admin/parent_link_request_detail.html': ('🔗 연결 요청 상세', None),
    'templates/admin/staff_management.html': ('👨‍🏫 강사 관리', '전체 강사 목록'),
    'templates/admin/teaching_materials.html': ('📚 학습 교재 관리', '교재 업로드 및 관리'),
    'templates/admin/videos.html': ('🎬 학습 동영상 관리', '동영상 업로드 및 관리'),
    'templates/admin/announcements.html': ('📢 공지사항 관리', '전체 공지사항'),
    'templates/admin/announcement_detail.html': ('📢 공지사항 상세', None),
    'templates/admin/makeup_requests.html': ('🔄 보강수업 관리', '전체 보강 요청'),

    # Teacher Portal
    'templates/teacher/index.html': ('🏠 강사 대시보드', '내 수업 현황'),
    'templates/teacher/courses.html': ('📚 내 수업', '담당 수업 목록'),
    'templates/teacher/course_detail.html': ('📚 수업 상세', None),
    'templates/teacher/students.html': ('👥 학생 관리', '내 학생 목록'),
    'templates/teacher/attendance.html': ('✅ 출결 관리', '수업별 출석 체크'),
    'templates/teacher/consultations.html': ('🗣️ 상담 기록', '학생 상담 관리'),
    'templates/teacher/consultation_form.html': ('✍️ 상담 기록 작성', None),
    'templates/teacher/consultation_detail.html': ('🗣️ 상담 상세', None),
    'templates/teacher/class_messages.html': ('💬 수업 공지/과제', '학생 메시지 발송'),
    'templates/teacher/materials.html': ('📁 학습 자료', '내 수업 자료'),

    # Parent Portal
    'templates/parent_portal/index.html': ('🏠 학부모 대시보드', '자녀 학습 현황'),
    'templates/parent_portal/children.html': ('👶 자녀 정보', '등록된 자녀 목록'),
    'templates/parent_portal/child_detail.html': ('👶 자녀 상세', None),
    'templates/parent_portal/essays.html': ('📝 과제 및 첨삭', '자녀 과제 현황'),
    'templates/parent_portal/attendance.html': ('✅ 출결 현황', '자녀 출석 기록'),
    'templates/parent_portal/payments.html': ('💰 수납 내역', '결제 및 납부 현황'),
    'templates/parent_portal/all_payments.html': ('💰 전체 결제 내역', '자녀별 결제 이력'),
    'templates/parent_portal/consultations.html': ('🗣️ 상담 내역', '자녀 상담 기록'),
    'templates/parent_portal/makeup_classes.html': ('🔄 보강수업', '보강 신청 및 이력'),
    'templates/parent_portal/link_child.html': ('🔗 자녀 연결', '학생 계정 연결 신청'),
    'templates/parent_portal/link_requests.html': ('🔗 연결 요청 관리', '신청 이력 조회'),
    'templates/parent_portal/materials.html': ('📚 학습 교재', '자녀 열람 가능 교재'),
    'templates/parent_portal/videos.html': ('🎬 학습 동영상', '자녀 열람 가능 동영상'),

    # Student Portal
    'templates/student_portal/index.html': ('🏠 학생 대시보드', '내 학습 현황'),
    'templates/student_portal/courses.html': ('📚 내 수업', '수강 중인 수업'),
    'templates/student_portal/course_detail.html': ('📚 수업 상세', None),
    'templates/student_portal/essays.html': ('📝 과제 제출', '내 과제 목록'),
    'templates/student_portal/essay_detail.html': ('📝 과제 상세', None),
    'templates/student_portal/attendance.html': ('✅ 출결 현황', '내 출석 기록'),
    'templates/student_portal/announcements.html': ('📢 공지사항', '학원 공지'),
    'templates/student_portal/makeup_classes.html': ('🔄 보강수업', '보강 신청하기'),
    'templates/student_portal/materials.html': ('📚 학습 교재', '열람 가능 교재'),
    'templates/student_portal/videos.html': ('🎬 학습 동영상', '열람 가능 동영상'),
}


def add_page_title_to_template(filepath, title, subtitle=None):
    """템플릿 파일에 page_title 블록 추가"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 이미 page_title 블록이 있는지 확인
        if '{% block page_title %}' in content:
            print(f"  ⏭️  이미 적용됨: {filepath}")
            return False

        # {% block title %} 다음에 page_title 블록 추가
        title_pattern = r'({% block title %}.*?{% endblock %})'

        if not re.search(title_pattern, content):
            print(f"  ⚠️  title 블록을 찾을 수 없음: {filepath}")
            return False

        # 새로운 블록 생성
        new_blocks = f'\n\n{{% block page_title %}}{title}{{% endblock %}}'

        if subtitle:
            new_blocks += f'\n\n{{% block page_subtitle %}}\n<span class="text-sm text-white text-opacity-70 ml-3">{subtitle}</span>\n{{% endblock %}}'

        new_blocks += '\n'

        # title 블록 다음에 삽입
        updated_content = re.sub(
            title_pattern,
            r'\1' + new_blocks,
            content,
            count=1
        )

        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        print(f"  ✅ 업데이트 완료: {filepath}")
        return True

    except Exception as e:
        print(f"  ❌ 오류 발생 ({filepath}): {e}")
        return False


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📝 페이지 제목 일괄 업데이트 시작")
    print("=" * 60)

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for filepath, (title, subtitle) in PAGE_TITLES.items():
        if os.path.exists(filepath):
            result = add_page_title_to_template(filepath, title, subtitle)
            if result:
                updated_count += 1
            else:
                skipped_count += 1
        else:
            print(f"  ❌ 파일 없음: {filepath}")
            error_count += 1

    print("\n" + "=" * 60)
    print("📊 업데이트 결과")
    print("=" * 60)
    print(f"✅ 업데이트: {updated_count}개")
    print(f"⏭️  스킵: {skipped_count}개")
    print(f"❌ 오류: {error_count}개")
    print("=" * 60)
    print("\n✨ 완료! 페이지를 새로고침하여 확인하세요.")


if __name__ == '__main__':
    main()
