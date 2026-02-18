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
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab이 설치되어 있지 않습니다. pip install reportlab을 실행하세요.")

    try:
        # Windows 기본 폰트 경로
        font_path = 'C:\\Windows\\Fonts\\malgun.ttf'

        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('MalgunGothic', font_path))
            return 'MalgunGothic'
        else:
            # 폰트 없으면 기본 폰트 사용
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
