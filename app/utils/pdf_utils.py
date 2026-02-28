# -*- coding: utf-8 -*-
"""PDF 리포트 생성 유틸리티"""
from io import BytesIO
from datetime import datetime
from flask import send_file

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.units import mm, inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.platypus import Image as RLImage
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

import os


def register_korean_font():
    """
    한글 폰트 등록
    Windows: 맑은 고딕 (malgun.ttf)
    Linux (GCP): NanumGothic (fonts-nanum 패키지)
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab이 설치되어 있지 않습니다. pip install reportlab을 실행하세요.")

    candidates = [
        # Windows
        ('MalgunGothic', 'C:\\Windows\\Fonts\\malgun.ttf'),
        # Linux - Nanum Gothic (sudo apt install fonts-nanum)
        ('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'),
        ('NanumGothic', '/usr/share/fonts/nanum/NanumGothic.ttf'),
        ('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf'),
        # Linux - Noto CJK
        ('NotoSansCJK', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        ('NotoSansCJK', '/usr/share/fonts/noto-cjk/NotoSansCJKkr-Regular.otf'),
    ]

    try:
        for font_name, font_path in candidates:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                return font_name
        # 폰트 없으면 기본 폰트 사용 (한글 깨짐)
        return 'Helvetica'
    except Exception as e:
        print(f"폰트 등록 실패: {e}")
        return 'Helvetica'


def get_korean_styles():
    """
    한글 지원 스타일 생성
    """
    font_name = register_korean_font()

    styles = getSampleStyleSheet()

    # 제목 스타일
    styles.add(ParagraphStyle(
        name='KoreanTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1F4E78'),
        spaceAfter=20
    ))

    # 부제목 스타일
    styles.add(ParagraphStyle(
        name='KoreanSubtitle',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#4472C4'),
        spaceAfter=12
    ))

    # 본문 스타일
    styles.add(ParagraphStyle(
        name='KoreanBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT
    ))

    # 작은 글씨
    styles.add(ParagraphStyle(
        name='KoreanSmall',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=colors.grey
    ))

    return styles


def create_pdf_response(buffer, filename):
    """
    PDF 다운로드 응답 생성

    Args:
        buffer: BytesIO 객체
        filename: 파일명 (확장자 제외)

    Returns:
        Flask send_file response
    """
    buffer.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    full_filename = f"{filename}_{timestamp}.pdf"

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=full_filename
    )


# ==================== 성적표 PDF ====================

def generate_student_report_card_pdf(student, enrollments, essays, attendance_stats):
    """
    학생 성적표 PDF 생성

    Args:
        student: Student 객체
        enrollments: CourseEnrollment 리스트
        essays: Essay 리스트
        attendance_stats: 출석 통계 dict

    Returns:
        Flask response
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)

    styles = get_korean_styles()
    story = []

    # 제목
    title = Paragraph(f"{student.name} 학생 성적표", styles['KoreanTitle'])
    story.append(title)
    story.append(Spacer(1, 10*mm))

    # 생성 정보
    info = Paragraph(
        f"발급일: {datetime.now().strftime('%Y년 %m월 %d일')}<br/>학년: {student.grade or '-'} | 등급: {student.tier or '-'}",
        styles['KoreanSmall']
    )
    story.append(info)
    story.append(Spacer(1, 10*mm))

    # 출석 통계
    story.append(Paragraph("출석 현황", styles['KoreanSubtitle']))

    attendance_data = [
        ['구분', '값'],
        ['총 세션', str(attendance_stats.get('total_sessions', 0))],
        ['출석', str(attendance_stats.get('present', 0))],
        ['지각', str(attendance_stats.get('late', 0))],
        ['결석', str(attendance_stats.get('absent', 0))],
        ['출석률', f"{attendance_stats.get('attendance_rate', 0):.1f}%"]
    ]

    attendance_table = Table(attendance_data, colWidths=[80*mm, 80*mm])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(attendance_table)
    story.append(Spacer(1, 10*mm))

    # 수강 수업
    story.append(Paragraph("수강 중인 수업", styles['KoreanSubtitle']))

    course_data = [['수업명', '강사', '출석률', '상태']]
    for enrollment in enrollments[:10]:  # 최대 10개
        course_data.append([
            enrollment.course.course_name,
            enrollment.course.teacher.name if enrollment.course.teacher else '-',
            f"{enrollment.attendance_rate:.1f}%",
            '진행중' if enrollment.status == 'active' else '완료'
        ])

    course_table = Table(course_data, colWidths=[60*mm, 40*mm, 30*mm, 30*mm])
    course_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(course_table)
    story.append(Spacer(1, 10*mm))

    # 첨삭 기록
    if essays:
        story.append(Paragraph("첨삭 기록 (최근 10개)", styles['KoreanSubtitle']))

        essay_data = [['제출일', '버전', '상태']]
        for essay in essays[:10]:
            essay_data.append([
                essay.created_at.strftime('%Y-%m-%d'),
                f"v{essay.current_version}",
                '완료' if essay.is_finalized else '진행중'
            ])

        essay_table = Table(essay_data, colWidths=[60*mm, 50*mm, 50*mm])
        essay_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(essay_table)

    # PDF 생성
    doc.build(story)

    return create_pdf_response(buffer, f"{student.name}_성적표")


# ==================== 출석 확인서 PDF ====================

def generate_attendance_certificate_pdf(student, start_date, end_date, attendance_records):
    """
    출석 확인서 PDF 생성

    Args:
        student: Student 객체
        start_date: 시작 날짜
        end_date: 종료 날짜
        attendance_records: 출석 기록 리스트

    Returns:
        Flask response
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)

    styles = get_korean_styles()
    story = []

    # 제목
    title = Paragraph("출석 확인서", styles['KoreanTitle'])
    story.append(title)
    story.append(Spacer(1, 15*mm))

    # 학생 정보
    story.append(Paragraph("학생 정보", styles['KoreanSubtitle']))

    student_data = [
        ['이름', student.name],
        ['학년', student.grade or '-'],
        ['등급', student.tier or '-'],
        ['기간', f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"]
    ]

    student_table = Table(student_data, colWidths=[50*mm, 110*mm])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E7E6E6')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))

    story.append(student_table)
    story.append(Spacer(1, 10*mm))

    # 출석 기록
    story.append(Paragraph("출석 기록", styles['KoreanSubtitle']))

    attendance_data = [['날짜', '수업명', '출석상태', '비고']]

    for record in attendance_records:
        status_text = {
            'present': '출석',
            'late': '지각',
            'absent': '결석',
            'excused': '결석(사유)'
        }.get(record.get('status'), '-')

        attendance_data.append([
            record.get('date', '-'),
            record.get('course_name', '-')[:20],  # 수업명 길이 제한
            status_text,
            record.get('notes', '-')[:30] if record.get('notes') else '-'
        ])

    attendance_table = Table(attendance_data, colWidths=[35*mm, 55*mm, 30*mm, 40*mm])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(attendance_table)
    story.append(Spacer(1, 20*mm))

    # 발급 정보
    issue_text = f"""
    위 내용이 사실임을 확인합니다.

    발급일: {datetime.now().strftime('%Y년 %m월 %d일')}
    발급처: MOMOAI 학원
    """

    issue_para = Paragraph(issue_text, styles['KoreanBody'])
    story.append(issue_para)

    # PDF 생성
    doc.build(story)

    return create_pdf_response(buffer, f"{student.name}_출석확인서")


# ==================== 월간 종합 리포트 PDF ====================

def generate_monthly_report_pdf(month_str, statistics):
    """
    월간 종합 리포트 PDF 생성

    Args:
        month_str: 월 문자열 (예: "2026년 02월")
        statistics: 통계 데이터 dict

    Returns:
        Flask response
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)

    styles = get_korean_styles()
    story = []

    # 제목
    title = Paragraph(f"{month_str} 종합 리포트", styles['KoreanTitle'])
    story.append(title)
    story.append(Spacer(1, 10*mm))

    # 생성 정보
    info = Paragraph(
        f"생성일: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}",
        styles['KoreanSmall']
    )
    story.append(info)
    story.append(Spacer(1, 10*mm))

    # 전체 통계
    story.append(Paragraph("전체 통계", styles['KoreanSubtitle']))

    stats_data = [
        ['구분', '전체', '이번 달', '증감'],
        ['학생 수', str(statistics.get('total_students', 0)),
         str(statistics.get('month_students', 0)),
         f"+{statistics.get('month_students', 0)}"],
        ['진행 중인 수업', str(statistics.get('total_courses', 0)),
         str(statistics.get('month_courses', 0)),
         f"+{statistics.get('month_courses', 0)}"],
        ['첨삭 수', str(statistics.get('total_essays', 0)),
         str(statistics.get('month_essays', 0)),
         f"+{statistics.get('month_essays', 0)}"],
        ['이번 달 수익', '',
         f"{statistics.get('month_revenue', 0):,}원", '']
    ]

    stats_table = Table(stats_data, colWidths=[50*mm, 35*mm, 35*mm, 35*mm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(stats_table)
    story.append(Spacer(1, 10*mm))

    # 상위 수업
    if statistics.get('top_courses'):
        story.append(Paragraph("상위 5개 수업", styles['KoreanSubtitle']))

        course_data = [['수업명', '강사', '수강생', '출석률']]
        for course in statistics.get('top_courses', []):
            course_data.append([
                course['name'][:25],
                course['teacher'],
                course['students'],
                course['attendance_rate']
            ])

        course_table = Table(course_data, colWidths=[60*mm, 40*mm, 30*mm, 30*mm])
        course_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), register_korean_font()),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(course_table)

    # PDF 생성
    doc.build(story)

    return create_pdf_response(buffer, f"월간리포트_{month_str}")


# ==================== 강사 사용 설명서 PDF ====================

def generate_teacher_manual_pdf():
    """
    강사 사용 설명서 PDF 생성
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20*mm, bottomMargin=20*mm,
        leftMargin=20*mm, rightMargin=20*mm
    )

    font_name = register_korean_font()
    styles = getSampleStyleSheet()

    # ── 스타일 정의 ──────────────────────────────────────────
    title_style = ParagraphStyle(
        'ManualTitle', parent=styles['Normal'],
        fontName=font_name, fontSize=22, leading=28,
        alignment=TA_CENTER, textColor=colors.HexColor('#312E81'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'ManualSubtitle', parent=styles['Normal'],
        fontName=font_name, fontSize=11, leading=14,
        alignment=TA_CENTER, textColor=colors.HexColor('#6366F1'),
        spaceAfter=4
    )
    section_style = ParagraphStyle(
        'SectionHead', parent=styles['Normal'],
        fontName=font_name, fontSize=14, leading=18,
        textColor=colors.HexColor('#4338CA'),
        spaceBefore=14, spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontName=font_name, fontSize=10, leading=15,
        spaceAfter=4
    )
    bullet_style = ParagraphStyle(
        'Bullet', parent=styles['Normal'],
        fontName=font_name, fontSize=9.5, leading=14,
        leftIndent=14, spaceAfter=2
    )
    note_style = ParagraphStyle(
        'Note', parent=styles['Normal'],
        fontName=font_name, fontSize=9, leading=12,
        textColor=colors.HexColor('#475569'),
        leftIndent=10, spaceAfter=4
    )
    toc_style = ParagraphStyle(
        'TOC', parent=styles['Normal'],
        fontName=font_name, fontSize=10, leading=16,
        textColor=colors.HexColor('#1E40AF')
    )
    faq_q_style = ParagraphStyle(
        'FAQQ', parent=styles['Normal'],
        fontName=font_name, fontSize=10, leading=14,
        textColor=colors.HexColor('#1E293B')
    )
    faq_a_style = ParagraphStyle(
        'FAQA', parent=styles['Normal'],
        fontName=font_name, fontSize=9.5, leading=13,
        textColor=colors.HexColor('#475569'),
        leftIndent=12, spaceAfter=6
    )

    story = []

    # ── 표지 ────────────────────────────────────────────────
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph("MOMOAI v4.0", title_style))
    story.append(Paragraph("강사 사용 설명서", title_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Teacher User Manual", subtitle_style))
    story.append(Spacer(1, 8*mm))

    # 구분선 테이블
    divider = Table([['']], colWidths=[170*mm])
    divider.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#4338CA')),
    ]))
    story.append(divider)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"발급일: {datetime.now().strftime('%Y년 %m월 %d일')}", subtitle_style))
    story.append(Spacer(1, 30*mm))

    # ── 목차 ────────────────────────────────────────────────
    toc_data = [
        ['목  차 (Table of Contents)', ''],
        ['1.  로그인 및 기본 설정', ''],
        ['2.  수업 관리', ''],
        ['3.  출석 체크', ''],
        ['4.  피드백 작성', ''],
        ['5.  첨삭 (에세이)', ''],
        ['6.  수업 공지 및 메세지', ''],
        ['7.  학습 자료 등록', ''],
        ['8.  과제 출제 및 채점', ''],
        ['9.  게시판', ''],
        ['10. 학생 평가', ''],
        ['11. 자주 묻는 질문 (FAQ)', ''],
    ]
    toc_table = Table(toc_data, colWidths=[130*mm, 40*mm])
    toc_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF2FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#312E81')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E40AF')),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ── 섹션 헬퍼 ────────────────────────────────────────────
    def add_section(num, title, items):
        story.append(Paragraph(f"{num}. {title}", section_style))
        for item_type, text in items:
            if item_type == 'body':
                story.append(Paragraph(text, body_style))
            elif item_type == 'bullet':
                story.append(Paragraph(f"• {text}", bullet_style))
            elif item_type == 'numbered':
                story.append(Paragraph(text, bullet_style))
            elif item_type == 'note':
                story.append(Paragraph(f"※ {text}", note_style))
            elif item_type == 'space':
                story.append(Spacer(1, 3*mm))
        story.append(Spacer(1, 3*mm))

    # ── 1. 로그인 및 기본 설정 ──────────────────────────────
    add_section('1', '로그인 및 기본 설정', [
        ('body', '[최초 로그인]'),
        ('numbered', '1) 관리자가 발급한 이메일 / 임시 비밀번호로 로그인합니다.'),
        ('numbered', '2) 최초 로그인 시 비밀번호 변경을 요청할 수 있습니다.'),
        ('numbered', '3) 비밀번호는 영문 소문자 + 숫자 + 특수문자를 포함해야 합니다.'),
        ('space', ''),
        ('body', '[프로필 설정]'),
        ('bullet', '좌측 하단 프로필 버튼을 클릭하여 내 정보를 수정할 수 있습니다.'),
        ('bullet', '강사 소개를 작성하면 모모 소식 → 강사 소개 페이지에 표시됩니다.'),
        ('bullet', 'Zoom 링크를 등록하면 학생들에게 공유됩니다.'),
    ])

    # ── 2. 수업 관리 ─────────────────────────────────────────
    story.append(Paragraph("2. 수업 관리", section_style))
    story.append(Paragraph("사이드바 내 수업 → 수업 목록에서 담당 수업 전체를 확인합니다.", body_style))

    course_data = [
        ['메뉴', '기능'],
        ['수업 목록', '담당 수업 전체 조회 / 수업별 학생 현황 확인'],
        ['주간 시간표', '이번 주 수업 일정을 달력 형식으로 확인'],
        ['수업 상세', '수강생 목록 · 출석률 · 세션별 현황 확인'],
    ]
    ct = Table(course_data, colWidths=[50*mm, 120*mm])
    ct.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ct)
    story.append(Paragraph("※ 수업 개설 및 수강생 추가는 관리자만 가능합니다. 변경이 필요하면 관리자에게 요청하세요.", note_style))
    story.append(Spacer(1, 3*mm))

    # ── 3. 출석 체크 ─────────────────────────────────────────
    add_section('3', '출석 체크', [
        ('body', '사이드바 내 수업 → 출석 체크로 이동합니다.'),
        ('numbered', '1) 오늘 또는 해당 날짜의 세션을 선택합니다.'),
        ('numbered', '2) 학생 이름 옆 버튼으로 출석 / 지각 / 결석 / 인정결석을 선택합니다.'),
        ('numbered', '3) 기본값은 출석으로 설정되어 있습니다. 결석·지각 학생만 변경하면 됩니다.'),
        ('numbered', '4) 출석 체크 완료 버튼을 클릭하면 세션이 완료 처리됩니다.'),
        ('note', '완료 처리된 세션도 이후 수정이 가능합니다. 수업 목록 → 해당 세션 → 출석 현황에서 수정하세요.'),
    ])

    # ── 4. 피드백 작성 ───────────────────────────────────────
    add_section('4', '피드백 작성', [
        ('body', '사이드바 학생 관리 → 피드백 작성으로 이동합니다.'),
        ('numbered', '1) 피드백을 받을 학생을 선택합니다.'),
        ('numbered', '2) 수업 날짜, 피드백 내용, 점수를 입력합니다.'),
        ('numbered', '3) SMS 발송 옵션을 체크하면 학부모에게 문자가 자동 발송됩니다.'),
        ('numbered', '4) 저장하면 학부모 포털에서 확인 가능하며, 학생에게는 보이지 않습니다.'),
        ('note', '피드백은 학부모와 관리자만 열람 가능합니다. 학생은 볼 수 없습니다.'),
    ])

    # ── 5. 첨삭 (에세이) ─────────────────────────────────────
    add_section('5', '첨삭 (에세이)', [
        ('body', '학생이 에세이를 제출하면 강사에게 알림이 발송됩니다.'),
        ('numbered', '1) 좌측 상단 알림(벨 아이콘)에서 새 제출 알림을 확인합니다.'),
        ('numbered', '2) 또는 사이드바 학습 관리 → 에세이 첨삭에서 목록을 확인합니다.'),
        ('numbered', '3) 에세이를 열어 내용을 확인하고 첨삭 및 점수를 입력합니다.'),
        ('numbered', '4) AI 자동 첨삭 기능을 활용하면 초안을 빠르게 생성할 수 있습니다.'),
    ])

    # ── 6. 수업 공지 및 메세지 ───────────────────────────────
    story.append(Paragraph("6. 수업 공지 및 메세지", section_style))
    story.append(Paragraph("사이드바 내 수업 → 수업 공지 및 메세지로 이동합니다.", body_style))

    msg_data = [
        ['유형', '설명'],
        ['수업 전체 공지', '수업을 선택하여 해당 수업 수강생 전원에게 공지/과제를 발송합니다.'],
        ['개별 학생 메세지', '특정 학생에게만 개인 메세지 / 숙제를 발송합니다.'],
    ]
    mt = Table(msg_data, colWidths=[50*mm, 120*mm])
    mt.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(mt)
    story.append(Paragraph("※ 학부모 포함 발송 체크박스를 선택하면 학생과 학부모 모두에게 알림이 전달됩니다.", note_style))
    story.append(Spacer(1, 3*mm))

    # ── 7. 학습 자료 등록 ────────────────────────────────────
    add_section('7', '학습 자료 등록', [
        ('body', '사이드바 학습 자료로 이동합니다.'),
        ('bullet', 'PDF, DOC, PPT, HWP, ZIP 등 파일을 업로드할 수 있습니다.'),
        ('bullet', '학년별 또는 수업별로 공개 대상을 지정할 수 있습니다.'),
        ('bullet', '게시 기간(시작일 / 종료일)을 설정하면 해당 기간에만 표시됩니다.'),
    ])

    # ── 8. 과제 출제 및 채점 ─────────────────────────────────
    add_section('8', '과제 출제 및 채점', [
        ('body', '사이드바 학습 관리 → 과제 관리로 이동합니다.'),
        ('numbered', '1) 새 과제 출제를 클릭하여 제목, 내용, 마감일, 대상 수업을 설정합니다.'),
        ('numbered', '2) 학생이 과제를 제출하면 목록에서 확인 가능합니다.'),
        ('numbered', '3) 제출된 과제를 열어 점수 및 코멘트를 입력하고 채점합니다.'),
        ('numbered', '4) 채점 결과는 학생 포털에서 확인 가능합니다.'),
    ])

    # ── 9. 게시판 ────────────────────────────────────────────
    story.append(Paragraph("9. 게시판", section_style))

    board_data = [
        ['게시판', '설명'],
        ['강사 게시판', '강사 전용 게시판입니다. 강사끼리 정보 공유 및 소통할 수 있습니다.'],
        ['클래스 게시판', '수업별 학생 소통 공간입니다. 수업을 선택하여 게시글을 작성하세요.'],
        ['하크니스 게시판', '하크니스 수업 전용 토론 게시판입니다. 게시판을 생성하여 운영합니다.'],
    ]
    bt = Table(board_data, colWidths=[50*mm, 120*mm])
    bt.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(bt)
    story.append(Spacer(1, 3*mm))

    # ── 10. 학생 평가 ────────────────────────────────────────
    story.append(Paragraph("10. 학생 평가", section_style))

    eval_data = [
        ['평가 유형', '설명'],
        ['주간 평가', '매주 학생의 수업 참여도, 이해도 등을 항목별로 평가합니다. 누적 데이터로 성장 추이를 확인할 수 있습니다.'],
        ['ACE 평가', '분기별 종합 평가입니다. 결과는 학부모 리포트로 출력할 수 있습니다.'],
        ['독서 MBTI', '학생의 독서 성향을 파악하는 설문입니다. 결과를 바탕으로 맞춤 지도 방향을 설정할 수 있습니다.'],
    ]
    et = Table(eval_data, colWidths=[40*mm, 130*mm])
    et.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(et)
    story.append(Spacer(1, 3*mm))

    # ── 11. FAQ ─────────────────────────────────────────────
    story.append(Paragraph("11. 자주 묻는 질문 (FAQ)", section_style))

    faqs = [
        ('출석을 잘못 체크했어요.',
         '수업 목록 → 해당 수업 → 세션 클릭 → 출석 현황에서 언제든지 수정 가능합니다.'),
        ('피드백을 작성했는데 학생이 볼 수 있나요?',
         '아니요. 피드백은 학부모와 관리자만 열람할 수 있습니다. 학생에게는 표시되지 않습니다.'),
        ('수업 공지를 보냈는데 학부모한테도 가나요?',
         '메세지 작성 시 "학부모 포함 발송" 체크박스를 선택한 경우에만 학부모에게도 알림이 발송됩니다.'),
        ('학생이 에세이를 제출하면 어떻게 알 수 있나요?',
         '알림(벨 아이콘)에 새 제출 알림이 표시됩니다. 알림을 클릭하면 바로 이동됩니다.'),
        ('수업에 학생을 추가하거나 빼고 싶어요.',
         '수강생 변경은 관리자만 가능합니다. 관리자에게 요청해 주세요.'),
        ('비밀번호를 변경하고 싶어요.',
         '좌측 하단 프로필 → 비밀번호 변경에서 직접 변경할 수 있습니다.'),
    ]
    for q, a in faqs:
        story.append(Paragraph(f"Q. {q}", faq_q_style))
        story.append(Paragraph(f"A. {a}", faq_a_style))

    story.append(Spacer(1, 8*mm))

    # ── 하단 안내 ────────────────────────────────────────────
    footer_data = [['추가 문의사항이 있으면 관리자에게 문의해 주세요. | © 2026 MOMOAI - 모모의 책장']]
    ft = Table(footer_data, colWidths=[170*mm])
    ft.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#4338CA')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ft)

    doc.build(story)
    return create_pdf_response(buffer, "MOMOAI_강사사용설명서")


# ==================== 학생 사용 설명서 PDF ====================

def generate_student_manual_pdf():
    """학생 사용 설명서 PDF 생성"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    font_name = register_korean_font()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Normal'], fontName=font_name, fontSize=22, leading=28, alignment=TA_CENTER, textColor=colors.HexColor('#312E81'), spaceAfter=6)
    subtitle_style = ParagraphStyle('S', parent=styles['Normal'], fontName=font_name, fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.HexColor('#6366F1'), spaceAfter=4)
    section_style = ParagraphStyle('H', parent=styles['Normal'], fontName=font_name, fontSize=14, leading=18, textColor=colors.HexColor('#4338CA'), spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=15, spaceAfter=4)
    bullet_style = ParagraphStyle('BU', parent=styles['Normal'], fontName=font_name, fontSize=9.5, leading=14, leftIndent=14, spaceAfter=2)
    note_style = ParagraphStyle('N', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=12, textColor=colors.HexColor('#475569'), leftIndent=10, spaceAfter=4)
    faq_q_style = ParagraphStyle('FQ', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=14, textColor=colors.HexColor('#1E293B'))
    faq_a_style = ParagraphStyle('FA', parent=styles['Normal'], fontName=font_name, fontSize=9.5, leading=13, textColor=colors.HexColor('#475569'), leftIndent=12, spaceAfter=6)

    story = []

    # 표지
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph("MOMOAI v4.0", title_style))
    story.append(Paragraph("학생 사용 설명서", title_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Student User Manual", subtitle_style))
    story.append(Spacer(1, 8*mm))
    divider = Table([['']], colWidths=[170*mm])
    divider.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#4338CA'))]))
    story.append(divider)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"발급일: {datetime.now().strftime('%Y년 %m월 %d일')}", subtitle_style))
    story.append(Spacer(1, 30*mm))

    # 목차
    toc_data = [
        ['목  차', ''],
        ['1.  로그인 및 기본 설정', ''],
        ['2.  수업 확인', ''],
        ['3.  출결 현황', ''],
        ['4.  글쓰기 제출 (에세이)', ''],
        ['5.  과제 확인 및 제출', ''],
        ['6.  학습 교재 및 동영상', ''],
        ['7.  보강수업 신청', ''],
        ['8.  게시판', ''],
        ['9.  평가 및 테스트', ''],
        ['10. 자주 묻는 질문 (FAQ)', ''],
    ]
    toc_table = Table(toc_data, colWidths=[130*mm, 40*mm])
    toc_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, 0), 12), ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF2FF')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#312E81')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E40AF')),
        ('TOPPADDING', (0, 0), (-1, 0), 8), ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4), ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    def add_section(num, title, items):
        story.append(Paragraph(f"{num}. {title}", section_style))
        for item_type, text in items:
            if item_type == 'body': story.append(Paragraph(text, body_style))
            elif item_type in ('bullet', 'numbered'): story.append(Paragraph(f"• {text}" if item_type == 'bullet' else text, bullet_style))
            elif item_type == 'note': story.append(Paragraph(f"※ {text}", note_style))
            elif item_type == 'space': story.append(Spacer(1, 3*mm))
        story.append(Spacer(1, 3*mm))

    def add_table(headers, rows, widths):
        data = [headers] + rows
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t)

    # 1. 로그인
    add_section('1', '로그인 및 기본 설정', [
        ('body', '[최초 로그인]'),
        ('numbered', '1) 관리자 또는 학부모가 안내한 이메일 / 비밀번호로 로그인합니다.'),
        ('numbered', '2) 비밀번호는 영문 소문자 + 숫자 + 특수문자를 포함해야 합니다.'),
        ('numbered', '3) 비밀번호를 잊어버린 경우 관리자에게 초기화를 요청하세요.'),
        ('space', ''),
        ('body', '[프로필 설정]'),
        ('bullet', '좌측 하단 프로필 버튼에서 내 정보를 수정할 수 있습니다.'),
        ('bullet', '프로필 사진을 등록하면 게시판에서 표시됩니다.'),
    ])

    # 2. 수업
    story.append(Paragraph("2. 수업 확인", section_style))
    story.append(Paragraph("사이드바 내 수업 → 수업 목록에서 현재 수강 중인 수업을 확인합니다.", body_style))
    add_table(['메뉴', '기능'], [['수업 목록', '수강 중인 수업 목록 및 강사 정보 확인'], ['수업 상세', '수업별 세션 일정, 출석 현황, 강사 연락처 확인']], [50*mm, 120*mm])
    story.append(Paragraph("※ 수업 등록/변경은 관리자만 가능합니다. 수강 신청이 필요하면 관리자에게 문의하세요.", note_style))
    story.append(Spacer(1, 3*mm))

    # 3. 출결
    add_section('3', '출결 현황', [
        ('body', '사이드바 내 수업 → 출결 현황에서 내 출석 기록을 확인합니다.'),
        ('bullet', '수업별 출석 통계(출석 / 지각 / 결석 횟수)를 확인할 수 있습니다.'),
        ('bullet', '출석 상태는 강사가 직접 입력합니다. 오류가 있으면 강사에게 문의하세요.'),
    ])

    # 4. 에세이
    add_section('4', '글쓰기 제출 (에세이)', [
        ('body', '사이드바 학습 활동 → 글쓰기 제출로 이동합니다.'),
        ('numbered', '1) 책 제목을 검색하거나 직접 입력합니다.'),
        ('numbered', '2) 글쓰기 내용을 입력하고 제출합니다.'),
        ('numbered', '3) 제출 즉시 담당 강사에게 자동으로 알림이 발송됩니다.'),
        ('numbered', '4) 강사가 첨삭을 완료하면 알림을 받고 내 첨삭에서 확인할 수 있습니다.'),
        ('note', '첨삭 완료 알림은 좌측 상단 알림(벨 아이콘)에서 확인할 수 있습니다.'),
    ])

    # 5. 과제
    add_section('5', '과제 확인 및 제출', [
        ('body', '사이드바 내 수업 → 과제 보기로 이동합니다.'),
        ('numbered', '1) 강사가 출제한 과제 목록이 표시됩니다.'),
        ('numbered', '2) 과제를 클릭하여 내용을 확인하고 답변을 작성합니다.'),
        ('numbered', '3) 제출을 클릭하면 강사에게 전달됩니다.'),
        ('numbered', '4) 채점된 과제는 목록에서 점수와 코멘트를 확인할 수 있습니다.'),
        ('note', '마감일이 지난 과제는 제출이 불가할 수 있습니다. 기한을 꼭 확인하세요.'),
    ])

    # 6. 교재/동영상
    story.append(Paragraph("6. 학습 교재 및 동영상", section_style))
    add_table(['구분', '설명'], [['학습 교재', '사이드바 학습 활동 → 학습 교재에서 강사가 등록한 자료(PDF, 문서 등)를 다운로드할 수 있습니다.'], ['학습 동영상', '사이드바 학습 활동 → 학습 동영상에서 유튜브 강의를 시청할 수 있습니다.']], [40*mm, 130*mm])
    story.append(Paragraph("※ 내 학년과 수강 중인 수업에 맞는 교재/동영상만 표시됩니다.", note_style))
    story.append(Spacer(1, 3*mm))

    # 7. 보강
    add_section('7', '보강수업 신청', [
        ('body', '사이드바 보강수업 → 신청하기로 이동합니다.'),
        ('numbered', '1) 보강 가능한 수업 목록에서 원하는 수업을 선택합니다.'),
        ('numbered', '2) 보강이 필요한 사유를 입력하고 신청합니다.'),
        ('numbered', '3) 관리자가 승인하면 알림이 발송됩니다.'),
        ('numbered', '4) 신청 내역은 보강수업 → 신청 내역에서 확인할 수 있습니다.'),
    ])

    # 8. 게시판
    story.append(Paragraph("8. 게시판", section_style))
    add_table(['게시판', '설명'], [['공지사항', '학원 공지와 강사 메세지를 확인합니다.'], ['클래스 게시판', '수업별 게시판에서 강사·학생과 소통합니다.'], ['하크니스 게시판', '하크니스 수업 전용 토론 게시판입니다.']], [50*mm, 120*mm])
    story.append(Spacer(1, 3*mm))

    # 9. 평가
    story.append(Paragraph("9. 평가 및 테스트", section_style))
    add_table(['평가 유형', '설명'], [['독서논술 MBTI', '나의 독서 성향을 알아보는 설문입니다.'], ['주간 평가', '강사가 매주 입력하는 수업 참여도 평가입니다.'], ['학습 진도', '수업별 진행 현황을 확인합니다.']], [45*mm, 125*mm])
    story.append(Spacer(1, 3*mm))

    # 10. FAQ
    story.append(Paragraph("10. 자주 묻는 질문 (FAQ)", section_style))
    faqs = [
        ('출석이 잘못 기록된 것 같아요.', '강사에게 직접 문의하거나 관리자에게 수정을 요청하세요.'),
        ('에세이를 제출했는데 강사가 확인하나요?', '제출 즉시 담당 강사에게 알림이 발송됩니다.'),
        ('학습 교재가 보이지 않아요.', '내 학년 또는 수강 수업에 맞는 교재만 표시됩니다. 강사에게 문의하세요.'),
        ('보강수업 신청 후 승인이 안 돼요.', '관리자가 검토 중입니다. 승인/거절 시 알림으로 안내됩니다.'),
        ('비밀번호를 변경하고 싶어요.', '좌측 하단 프로필 → 비밀번호 변경에서 직접 변경할 수 있습니다.'),
    ]
    for q, a in faqs:
        story.append(Paragraph(f"Q. {q}", faq_q_style))
        story.append(Paragraph(f"A. {a}", faq_a_style))

    story.append(Spacer(1, 8*mm))
    footer_data = [['추가 문의사항이 있으면 관리자에게 문의해 주세요. | © 2026 MOMOAI - 모모의 책장']]
    ft = Table(footer_data, colWidths=[170*mm])
    ft.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#4338CA')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ft)
    doc.build(story)
    return create_pdf_response(buffer, "MOMOAI_학생사용설명서")


# ==================== 학부모 사용 설명서 PDF ====================

def generate_parent_manual_pdf():
    """학부모 사용 설명서 PDF 생성"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    font_name = register_korean_font()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Normal'], fontName=font_name, fontSize=22, leading=28, alignment=TA_CENTER, textColor=colors.HexColor('#312E81'), spaceAfter=6)
    subtitle_style = ParagraphStyle('S', parent=styles['Normal'], fontName=font_name, fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.HexColor('#6366F1'), spaceAfter=4)
    section_style = ParagraphStyle('H', parent=styles['Normal'], fontName=font_name, fontSize=14, leading=18, textColor=colors.HexColor('#4338CA'), spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=15, spaceAfter=4)
    bullet_style = ParagraphStyle('BU', parent=styles['Normal'], fontName=font_name, fontSize=9.5, leading=14, leftIndent=14, spaceAfter=2)
    note_style = ParagraphStyle('N', parent=styles['Normal'], fontName=font_name, fontSize=9, leading=12, textColor=colors.HexColor('#475569'), leftIndent=10, spaceAfter=4)
    faq_q_style = ParagraphStyle('FQ', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=14, textColor=colors.HexColor('#1E293B'))
    faq_a_style = ParagraphStyle('FA', parent=styles['Normal'], fontName=font_name, fontSize=9.5, leading=13, textColor=colors.HexColor('#475569'), leftIndent=12, spaceAfter=6)

    story = []

    # 표지
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph("MOMOAI v4.0", title_style))
    story.append(Paragraph("학부모 사용 설명서", title_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Parent User Manual", subtitle_style))
    story.append(Spacer(1, 8*mm))
    divider = Table([['']], colWidths=[170*mm])
    divider.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#4338CA'))]))
    story.append(divider)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"발급일: {datetime.now().strftime('%Y년 %m월 %d일')}", subtitle_style))
    story.append(Spacer(1, 30*mm))

    # 목차
    toc_data = [
        ['목  차', ''],
        ['1.  로그인 및 기본 설정', ''],
        ['2.  자녀 연결', ''],
        ['3.  자녀 출결 현황', ''],
        ['4.  과제 및 첨삭 확인', ''],
        ['5.  학습 교재 및 동영상', ''],
        ['6.  평가 정보', ''],
        ['7.  보강수업 신청', ''],
        ['8.  수납 관리', ''],
        ['9.  게시판 및 피드백', ''],
        ['10. 자주 묻는 질문 (FAQ)', ''],
    ]
    toc_table = Table(toc_data, colWidths=[130*mm, 40*mm])
    toc_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, 0), 12), ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF2FF')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#312E81')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E40AF')),
        ('TOPPADDING', (0, 0), (-1, 0), 8), ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4), ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    def add_section(num, title, items):
        story.append(Paragraph(f"{num}. {title}", section_style))
        for item_type, text in items:
            if item_type == 'body': story.append(Paragraph(text, body_style))
            elif item_type in ('bullet', 'numbered'): story.append(Paragraph(f"• {text}" if item_type == 'bullet' else text, bullet_style))
            elif item_type == 'note': story.append(Paragraph(f"※ {text}", note_style))
            elif item_type == 'space': story.append(Spacer(1, 3*mm))
        story.append(Spacer(1, 3*mm))

    def add_table(headers, rows, widths):
        data = [headers] + rows
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338CA')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F3FF')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t)

    # 1. 로그인
    add_section('1', '로그인 및 기본 설정', [
        ('body', '[회원가입 및 로그인]'),
        ('numbered', '1) MOMOAI 홈페이지에서 회원가입 후 관리자 승인을 기다립니다.'),
        ('numbered', '2) 승인 완료 시 SMS 문자가 발송됩니다.'),
        ('numbered', '3) 비밀번호는 영문 소문자 + 숫자 + 특수문자를 포함해야 합니다.'),
        ('space', ''),
        ('body', '[프로필 설정]'),
        ('bullet', '좌측 하단 프로필 버튼에서 내 정보 및 비밀번호를 변경할 수 있습니다.'),
        ('bullet', '전화번호를 등록해 두면 중요 알림을 SMS로 받을 수 있습니다.'),
    ])

    # 2. 자녀 연결
    add_section('2', '자녀 연결', [
        ('body', 'MOMOAI에서 자녀 정보를 확인하려면 먼저 자녀 연결을 해야 합니다.'),
        ('numbered', '1) 사이드바 자녀 관리 → 자녀 연결을 클릭합니다.'),
        ('numbered', '2) 자녀의 이름, 학년, 학원 등록 코드를 입력하고 신청합니다.'),
        ('numbered', '3) 관리자가 확인 후 승인하면 자녀 정보가 연동됩니다.'),
        ('numbered', '4) 승인/거절 여부는 알림과 SMS로 안내됩니다.'),
        ('note', '한 자녀에 여러 학부모 계정(엄마, 아빠 등)을 연결할 수 있습니다.'),
    ])

    # 3. 출결
    add_section('3', '자녀 출결 현황', [
        ('body', '사이드바 학습 현황 → 출결 현황으로 이동합니다.'),
        ('bullet', '자녀가 여러 명이라면 상단 탭에서 자녀를 선택합니다.'),
        ('bullet', '수업별 출석률, 출석/지각/결석 횟수를 확인할 수 있습니다.'),
        ('bullet', '세션별 상세 출석 내역도 확인 가능합니다.'),
    ])

    # 4. 과제/첨삭
    add_section('4', '과제 및 첨삭 확인', [
        ('body', '사이드바 학습 현황 → 과제 및 첨삭으로 이동합니다.'),
        ('bullet', '자녀가 제출한 에세이 목록을 확인할 수 있습니다.'),
        ('bullet', '첨삭이 완료된 글쓰기의 점수, 강사 코멘트, 수정 내용을 확인할 수 있습니다.'),
        ('note', '첨삭 내용은 학부모에게만 공개됩니다. 학생 본인은 강사가 별도 공유한 경우에만 볼 수 있습니다.'),
    ])

    # 5. 교재/동영상
    story.append(Paragraph("5. 학습 교재 및 동영상", section_style))
    add_table(['구분', '설명'], [['학습 교재', '사이드바 학습 현황 → 학습 교재에서 자녀의 학습 자료를 다운로드할 수 있습니다.'], ['학습 동영상', '사이드바 학습 현황 → 학습 동영상에서 자녀에게 배정된 강의 영상을 시청할 수 있습니다.']], [40*mm, 130*mm])
    story.append(Spacer(1, 3*mm))

    # 6. 평가
    story.append(Paragraph("6. 평가 정보", section_style))
    add_table(['평가 유형', '설명'], [['독서논술 MBTI', '자녀의 독서 성향 유형 결과를 확인합니다.'], ['주간 평가', '강사가 매주 입력하는 수업 참여도, 이해도 평가를 확인합니다.'], ['ACE 분기 평가', '분기별 종합 평가 결과 및 리포트를 확인합니다.']], [45*mm, 125*mm])
    story.append(Spacer(1, 3*mm))

    # 7. 보강
    add_section('7', '보강수업 신청', [
        ('body', '사이드바 보강수업으로 이동합니다.'),
        ('numbered', '1) 보강 가능한 수업 목록에서 원하는 수업을 선택합니다.'),
        ('numbered', '2) 사유를 입력하고 신청하면 관리자가 검토 후 승인합니다.'),
        ('numbered', '3) 승인/거절 여부는 알림으로 안내됩니다.'),
    ])

    # 8. 수납
    add_section('8', '수납 관리', [
        ('body', '사이드바 수납 관리로 이동합니다.'),
        ('bullet', '자녀의 수업별 수강료 납부 현황을 확인할 수 있습니다.'),
        ('bullet', '미납, 납부 완료 상태를 한눈에 파악할 수 있습니다.'),
        ('bullet', '납부 관련 문의는 관리자에게 직접 연락해 주세요.'),
    ])

    # 9. 게시판
    story.append(Paragraph("9. 게시판 및 피드백", section_style))
    add_table(['게시판', '설명'], [['공지사항', '학원 공지 및 수업 안내를 확인합니다.'], ['선생님 피드백', '강사가 작성한 자녀의 수업 피드백을 확인합니다. 학생에게는 공개되지 않습니다.'], ['문의 게시판', '학원에 문의사항을 남기면 관리자/강사가 답변합니다.']], [45*mm, 125*mm])
    story.append(Spacer(1, 3*mm))

    # 10. FAQ
    story.append(Paragraph("10. 자주 묻는 질문 (FAQ)", section_style))
    faqs = [
        ('자녀를 연결했는데 정보가 보이지 않아요.', '관리자 승인이 필요합니다. 승인 후 SMS로 안내되며 보통 1영업일 내 처리됩니다.'),
        ('피드백을 받았는데 자녀도 볼 수 있나요?', '아니요. 선생님 피드백은 학부모와 관리자만 열람할 수 있습니다.'),
        ('출결 정보가 잘못된 것 같아요.', '담당 강사 또는 관리자에게 문의해 주세요.'),
        ('수납 내역이 맞지 않아요.', '관리자에게 직접 문의해 주세요.'),
        ('보강수업 신청 후 답변이 없어요.', '관리자가 검토 중입니다. 승인/거절 시 알림과 SMS로 안내됩니다.'),
        ('비밀번호를 잊어버렸어요.', '로그인 화면에서 재설정하거나 관리자에게 초기화를 요청하세요.'),
    ]
    for q, a in faqs:
        story.append(Paragraph(f"Q. {q}", faq_q_style))
        story.append(Paragraph(f"A. {a}", faq_a_style))

    story.append(Spacer(1, 8*mm))
    footer_data = [['추가 문의사항이 있으면 관리자에게 문의해 주세요. | © 2026 MOMOAI - 모모의 책장']]
    ft = Table(footer_data, colWidths=[170*mm])
    ft.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#4338CA')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ft)
    doc.build(story)
    return create_pdf_response(buffer, "MOMOAI_학부모사용설명서")


def generate_admin_manual_pdf():
    """관리자 사이트 사용 설명서 PDF 생성"""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    buffer = BytesIO()
    font_name = register_korean_font()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    title_style   = ParagraphStyle('KTitle',   fontName=font_name, fontSize=22, leading=28, spaceAfter=6,  textColor=colors.HexColor('#1E3A5F'), alignment=1)
    sub_style     = ParagraphStyle('KSub',     fontName=font_name, fontSize=11, leading=16, spaceAfter=16, textColor=colors.HexColor('#4B5563'), alignment=1)
    h2_style      = ParagraphStyle('KH2',      fontName=font_name, fontSize=14, leading=20, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor('#1E3A5F'))
    body_style    = ParagraphStyle('KBody',    fontName=font_name, fontSize=10, leading=16, spaceAfter=4,  textColor=colors.HexColor('#374151'))
    bullet_style  = ParagraphStyle('KBullet',  fontName=font_name, fontSize=10, leading=15, spaceAfter=3,  leftIndent=12, textColor=colors.HexColor('#374151'))
    numbered_style= ParagraphStyle('KNum',     fontName=font_name, fontSize=10, leading=15, spaceAfter=3,  leftIndent=12, textColor=colors.HexColor('#374151'))
    note_style    = ParagraphStyle('KNote',    fontName=font_name, fontSize=9,  leading=14, spaceAfter=4,  leftIndent=12, textColor=colors.HexColor('#6B7280'))

    story = []

    # 표지
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("📚 MOMOAI v4.0", title_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("관리자 사이트 사용 설명서", title_style))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("관리자 기능 전체 안내", sub_style))
    story.append(Spacer(1, 20*mm))

    toc_data = [
        ["목  차"],
        ["1. 로그인 및 계정 관리"],
        ["2. 학생 관리"],
        ["3. 수업 관리"],
        ["4. 수납 관리"],
        ["5. 강사 관리"],
        ["6. 학부모 관리"],
        ["7. 교재 및 동영상 관리"],
        ["8. 공지사항 및 문자 발송"],
        ["9. 전체 수업 현황"],
        ["10. 자주 묻는 질문"],
    ]
    toc_styles = [
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (0, 0), 13), ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#374151')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]
    toc = Table(toc_data, colWidths=[150*mm])
    toc.setStyle(TableStyle(toc_styles))
    story.append(toc)
    story.append(Spacer(1, 10*mm))

    def add_section(num, title, items):
        story.append(Paragraph(f"{num}. {title}", h2_style))
        for kind, text in items:
            if kind == 'body':
                story.append(Paragraph(text, body_style))
            elif kind == 'bullet':
                story.append(Paragraph(f"• {text}", bullet_style))
            elif kind == 'numbered':
                story.append(Paragraph(text, numbered_style))
            elif kind == 'note':
                story.append(Paragraph(f"※ {text}", note_style))
            elif kind == 'space':
                story.append(Spacer(1, 3*mm))
        story.append(Spacer(1, 5*mm))

    add_section('1', '로그인 및 계정 관리', [
        ('body', 'momoai.kr 접속 후 관리자 계정(이메일/비밀번호)으로 로그인합니다.'),
        ('bullet', 'master_admin(최고 관리자): 모든 기능 사용 가능, 완전 삭제 권한 포함'),
        ('bullet', 'manager(매니저): 대부분의 관리 기능 사용 가능'),
        ('note', '계정 완전 삭제는 복원이 불가능합니다. 신중하게 진행하세요.'),
    ])

    add_section('2', '학생 관리', [
        ('body', '사이드바 → 학생 관리 → 학생 목록에서 전체 학생을 조회합니다.'),
        ('numbered', '1) 학생 추가: 이름, 학년, 이메일, 담당 강사 입력'),
        ('numbered', '2) 학생 프로필: 학습 성향, 독서 이력, 티어(A/B/C/VIP) 관리'),
        ('numbered', '3) 학생 삭제: 상세 페이지 → 삭제 버튼 (모든 관련 데이터 함께 삭제)'),
    ])

    add_section('3', '수업 관리', [
        ('body', '사이드바 → 수업 관리 → 수업 개설에서 새 수업을 만듭니다.'),
        ('bullet', '학년, 수업 유형, 시작일, 강사 선택 시 수업명·코드 자동 생성'),
        ('bullet', '수업별 학생 등록: 수업 상세 → 학생 관리 탭'),
        ('bullet', '보강수업 승인: 학생 신청 → 관리자 승인 → 1회 보강 수업 자동 생성'),
        ('bullet', '전체 수업 현황: 강사별 주간 시간표 조회'),
    ])

    add_section('4', '수납 관리', [
        ('body', '사이드바 → 수납 관리에서 월별, 학생별 수납 내역을 확인합니다.'),
        ('bullet', '출결 기반 자동 수업료 계산'),
        ('bullet', '납부 상태(대기/완료/취소)로 필터링하여 미납 학생 파악'),
    ])

    add_section('5', '강사 관리', [
        ('body', '사이드바 → 강사 관리에서 강사 계정을 생성하고 관리합니다.'),
        ('bullet', '강사 추가: 이메일, 이름, 권한 레벨 설정'),
        ('bullet', '전체 수업 현황에서 강사별 주간 일정 확인 가능'),
    ])

    add_section('6', '학부모 관리', [
        ('body', '사이드바 → 학부모 관리에서 학부모 계정을 조회합니다.'),
        ('bullet', '자녀 연결 승인: 사이드바 → 학부모 연결 관리'),
        ('bullet', '학부모 완전 삭제: 학부모 목록 → 완전 삭제 (master_admin 전용)'),
    ])

    add_section('7', '교재 및 동영상 관리', [
        ('body', '사이드바 → 학습 교재 / 학습 동영상에서 학습 자료를 등록합니다.'),
        ('bullet', '지원 파일 형식: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, HWP, ZIP'),
        ('bullet', '유튜브 URL 입력 또는 직접 파일 업로드'),
        ('bullet', '학년별 / 수업별 공개 범위 설정, 게시 기간 설정'),
    ])

    add_section('8', '공지사항 및 문자 발송', [
        ('body', '사이드바 → 공지사항 관리에서 전체 또는 역할별 공지를 작성합니다.'),
        ('bullet', '문자 발송: 학생/학부모 선택 후 메시지 발송 (개별/그룹)'),
        ('bullet', '발송 내역: 발신자, 내용 키워드로 검색 가능'),
    ])

    add_section('9', '전체 수업 현황', [
        ('body', '사이드바 → 전체 수업현황. 강사 드롭다운으로 강사별 주간 일정 조회.'),
        ('bullet', '이전 주 / 이번 주 / 다음 주 버튼으로 주차 이동'),
        ('bullet', '상단 통계: 전체/예정/완료/취소 세션 수'),
    ])

    add_section('10', '자주 묻는 질문', [
        ('body', 'Q. 삭제한 학생 데이터를 복구할 수 있나요?'),
        ('bullet', 'A. 영구 삭제 후에는 복구 불가. 삭제 전 비활성화를 먼저 고려하세요.'),
        ('space', ''),
        ('body', 'Q. 비활성 계정과 영구 삭제의 차이는?'),
        ('bullet', 'A. 비활성화는 로그인만 차단(복원 가능), 영구 삭제는 모든 데이터 삭제(복원 불가).'),
        ('space', ''),
        ('body', 'Q. 강사/학부모 신규 계정은 어떻게 만드나요?'),
        ('bullet', 'A. 강사: 강사 관리 → 강사 추가. 학부모: 직접 회원가입 후 자녀 연결 신청 → 관리자 승인.'),
    ])

    ft = Table([["MOMOAI v4.0 관리자 사이트 사용 설명서"]], colWidths=[170*mm])
    ft.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A5F')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(ft)
    doc.build(story)
    return create_pdf_response(buffer, "MOMOAI_관리자사용설명서")
