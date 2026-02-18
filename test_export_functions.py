#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Excel 및 PDF 내보내기 기능 테스트"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Excel 및 PDF 내보내기 기능 테스트")
print("=" * 60)

# 1. 라이브러리 설치 확인
print("\n[1단계] 라이브러리 설치 확인")
print("-" * 60)

try:
    import openpyxl
    print(f"[OK] openpyxl 설치됨 (버전: {openpyxl.__version__})")
except ImportError:
    print("[ERROR] openpyxl이 설치되어 있지 않습니다.")
    print("        해결: pip install openpyxl")
    sys.exit(1)

try:
    import reportlab
    print(f"[OK] reportlab 설치됨 (버전: {reportlab.Version})")
except ImportError:
    print("[ERROR] reportlab이 설치되어 있지 않습니다.")
    print("        해결: pip install reportlab")
    sys.exit(1)

# 2. 유틸리티 파일 존재 확인
print("\n[2단계] 유틸리티 파일 확인")
print("-" * 60)

export_utils_path = os.path.join(os.path.dirname(__file__), 'app', 'utils', 'export_utils.py')
if os.path.exists(export_utils_path):
    print(f"[OK] export_utils.py 존재")
else:
    print(f"[ERROR] export_utils.py 파일을 찾을 수 없습니다.")
    print(f"        경로: {export_utils_path}")
    sys.exit(1)

pdf_utils_path = os.path.join(os.path.dirname(__file__), 'app', 'utils', 'pdf_utils.py')
if os.path.exists(pdf_utils_path):
    print(f"[OK] pdf_utils.py 존재")
else:
    print(f"[ERROR] pdf_utils.py 파일을 찾을 수 없습니다.")
    print(f"        경로: {pdf_utils_path}")
    sys.exit(1)

# 3. 유틸리티 함수 import 테스트
print("\n[3단계] 유틸리티 함수 import 테스트")
print("-" * 60)

try:
    from app.utils.export_utils import (
        create_excel_workbook,
        style_header_row,
        style_data_rows,
        auto_adjust_column_width,
        OPENPYXL_AVAILABLE
    )
    print("[OK] export_utils 모듈 import 성공")
    print(f"     OPENPYXL_AVAILABLE: {OPENPYXL_AVAILABLE}")
except Exception as e:
    print(f"[ERROR] export_utils 모듈 import 실패: {e}")
    sys.exit(1)

try:
    from app.utils.pdf_utils import (
        register_korean_font,
        get_korean_styles,
        REPORTLAB_AVAILABLE
    )
    print("[OK] pdf_utils 모듈 import 성공")
    print(f"     REPORTLAB_AVAILABLE: {REPORTLAB_AVAILABLE}")
except Exception as e:
    print(f"[ERROR] pdf_utils 모듈 import 실패: {e}")
    sys.exit(1)

# 4. Excel 생성 테스트
print("\n[4단계] Excel 생성 테스트")
print("-" * 60)

try:
    wb, ws = create_excel_workbook("테스트 시트")

    # 제목 추가
    ws.append(['번호', '이름', '학년', '점수'])
    style_header_row(ws, row_num=1, column_count=4)

    # 데이터 추가
    test_data = [
        [1, '김모모', '초6', 95],
        [2, '이모모', '중1', 88],
        [3, '박모모', '중2', 92]
    ]
    for row in test_data:
        ws.append(row)

    style_data_rows(ws, start_row=2, column_count=4)
    auto_adjust_column_width(ws)

    # 테스트 파일 저장
    test_file = os.path.join(os.path.dirname(__file__), 'test_output.xlsx')
    wb.save(test_file)

    if os.path.exists(test_file):
        file_size = os.path.getsize(test_file)
        print(f"[OK] Excel 파일 생성 성공")
        print(f"     파일: {test_file}")
        print(f"     크기: {file_size:,} bytes")

        # 테스트 파일 삭제
        os.remove(test_file)
        print(f"[OK] 테스트 파일 삭제 완료")
    else:
        print("[ERROR] Excel 파일이 생성되지 않았습니다.")

except Exception as e:
    print(f"[ERROR] Excel 생성 실패: {e}")
    import traceback
    traceback.print_exc()

# 5. PDF 생성 테스트
print("\n[5단계] PDF 생성 테스트")
print("-" * 60)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from io import BytesIO

    # 한글 폰트 등록
    font_name = register_korean_font()
    print(f"[OK] 한글 폰트 등록: {font_name}")

    # 스타일 생성
    styles = get_korean_styles()
    print(f"[OK] 한글 스타일 생성 완료")

    # PDF 생성 테스트
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    story = []

    # 제목
    title = Paragraph("테스트 PDF 문서", styles['KoreanTitle'])
    story.append(title)
    story.append(Spacer(1, 20))

    # 표
    data = [
        ['번호', '이름', '학년'],
        ['1', '김모모', '초6'],
        ['2', '이모모', '중1']
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(table)

    # PDF 빌드
    doc.build(story)

    # 크기 확인
    pdf_size = buffer.tell()
    print(f"[OK] PDF 생성 성공")
    print(f"     크기: {pdf_size:,} bytes")

    # 테스트 파일로 저장
    test_pdf = os.path.join(os.path.dirname(__file__), 'test_output.pdf')
    buffer.seek(0)
    with open(test_pdf, 'wb') as f:
        f.write(buffer.read())

    if os.path.exists(test_pdf):
        print(f"[OK] PDF 파일 저장 완료")
        print(f"     파일: {test_pdf}")

        # 테스트 파일 삭제
        os.remove(test_pdf)
        print(f"[OK] 테스트 파일 삭제 완료")

except Exception as e:
    print(f"[ERROR] PDF 생성 실패: {e}")
    import traceback
    traceback.print_exc()

# 6. 데이터베이스 연결 테스트
print("\n[6단계] 데이터베이스 연결 테스트")
print("-" * 60)

try:
    from app import create_app
    from app.models import db, Student, Course

    app = create_app('development')

    with app.app_context():
        # 학생 수 확인
        student_count = Student.query.count()
        print(f"[OK] 학생 수: {student_count}명")

        # 수업 수 확인
        course_count = Course.query.count()
        print(f"[OK] 수업 수: {course_count}개")

        if student_count == 0:
            print("[WARNING] 학생 데이터가 없습니다. 테스트 데이터를 생성하세요.")

        if course_count == 0:
            print("[WARNING] 수업 데이터가 없습니다. 테스트 데이터를 생성하세요.")

except Exception as e:
    print(f"[ERROR] 데이터베이스 연결 실패: {e}")
    import traceback
    traceback.print_exc()

# 최종 결과
print("\n" + "=" * 60)
print("테스트 완료!")
print("=" * 60)
print("\n다음 단계:")
print("1. 서버 실행: python run.py")
print("2. 브라우저에서 각 포털 접속")
print("3. 데이터 내보내기 버튼 테스트")
print("\n포털 URL:")
print("  - Admin:   http://localhost:5000/admin")
print("  - Teacher: http://localhost:5000/teacher")
print("  - Parent:  http://localhost:5000/parent")
print("  - Student: http://localhost:5000/student")
print("\n" + "=" * 60)
