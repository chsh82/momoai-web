from playwright.sync_api import sync_playwright
from pathlib import Path
import config


class PDFGenerator:
    """PDF 생성 클래스"""

    def generate_pdf(self, html_path: str) -> str:
        """
        HTML을 PDF로 변환

        Args:
            html_path: HTML 파일 경로

        Returns:
            생성된 PDF 파일 경로
        """
        try:
            # PDF 파일 경로 생성
            html_file = Path(html_path)
            pdf_filename = html_file.stem + '.pdf'
            pdf_path = config.PDF_FOLDER / pdf_filename

            # Playwright로 PDF 생성
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()

                # HTML 파일 로드
                page.goto(f'file:///{html_path.replace(chr(92), "/")}')

                # 페이지가 완전히 로드될 때까지 대기
                page.wait_for_load_state('networkidle')

                # PDF 생성
                page.pdf(
                    path=str(pdf_path),
                    format='A4',
                    print_background=True,
                    margin={
                        'top': '12mm',
                        'bottom': '12mm',
                        'left': '12mm',
                        'right': '12mm'
                    }
                )

                browser.close()

            return str(pdf_path)

        except Exception as e:
            raise Exception(f"PDF 생성 중 오류가 발생했습니다: {e}")
