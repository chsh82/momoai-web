import anthropic
from pathlib import Path
from datetime import datetime
from typing import Optional
import config


class MOMOAICore:
    """MOMOAI 핵심 로직 클래스"""

    def __init__(self, api_key: str):
        """
        Initialize MOMOAI Core

        Args:
            api_key: Anthropic API key
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = self.load_momoai_document()

    def load_momoai_document(self) -> str:
        """MOMOAI 규칙 문서 로드"""
        try:
            with open(config.MOMOAI_DOC_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"MOMOAI 문서를 로드할 수 없습니다: {e}")

    def create_analysis_prompt(self, student_name: str, grade: str, essay_text: str) -> str:
        """분석 프롬프트 생성"""
        return f"""학생 정보:
- 이름: {student_name}
- 학년: {grade}

논술문:
{essay_text}

위 논술문을 MOMOAI v3.3.0 규칙에 따라 첨삭해주세요.
반드시 HTML 완전 템플릿 형식으로 출력하고, 모든 규칙을 준수해주세요.

v3.3.0 필수 포함 사항:
1. 윤문 완성본 (원문 대비 1.3~2배 분량, 통계+사례 필수)
2. 💭 생각해볼 쟁점 세 가지 (내용첨삭과 비중복되는 심화 질문)
3. 교사 종합 제언
4. 푸터까지 완전한 HTML 문서

특히 "생각해볼 쟁점 세 가지" 섹션은 필수입니다. 내용 첨삭에서 지적한 문제가 아닌, 글을 넘어서는 심화 토론 주제 3가지를 제시해주세요.
"""

    def analyze_essay(self, student_name: str, grade: str, essay_text: str) -> str:
        """
        논술문 분석 및 HTML 리포트 생성

        Args:
            student_name: 학생 이름
            grade: 학년 (초등/중등/고등)
            essay_text: 논술문 텍스트

        Returns:
            HTML 형식의 첨삭 리포트
        """
        user_prompt = self.create_analysis_prompt(student_name, grade, essay_text)

        try:
            response = self.client.messages.create(
                model="claude-opus-4-5-20251101",
                max_tokens=24000,
                timeout=600.0,  # 10분 타임아웃
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract HTML from response
            html_content = response.content[0].text

            # Remove markdown code blocks if present
            if '```html' in html_content:
                # Extract HTML from markdown code block
                start = html_content.find('```html') + 7
                end = html_content.find('```', start)
                if end != -1:
                    html_content = html_content[start:end].strip()
            elif '```' in html_content:
                # Extract from generic code block
                start = html_content.find('```') + 3
                end = html_content.find('```', start)
                if end != -1:
                    html_content = html_content[start:end].strip()

            # Find DOCTYPE or <html tag in the response
            if '<!DOCTYPE' in html_content or '<html' in html_content:
                # Extract from DOCTYPE if exists
                if '<!DOCTYPE' in html_content:
                    html_start = html_content.find('<!DOCTYPE')
                    html_content = html_content[html_start:]
                elif '<html' in html_content:
                    html_start = html_content.find('<html')
                    html_content = html_content[html_start:]

                return html_content
            else:
                raise Exception("API 응답에서 HTML을 찾을 수 없습니다.")


        except Exception as e:
            raise Exception(f"첨삭 중 오류가 발생했습니다: {e}")

    def save_html(self, html_content: str, filename: str) -> str:
        """
        HTML 파일 저장

        Args:
            html_content: HTML 콘텐츠
            filename: 파일명 (확장자 포함)

        Returns:
            저장된 파일의 전체 경로
        """
        try:
            file_path = config.HTML_FOLDER / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return str(file_path)
        except Exception as e:
            raise Exception(f"HTML 파일 저장 중 오류가 발생했습니다: {e}")

    def generate_filename(self, student_name: str, grade: str, extension: str = 'html') -> str:
        """
        파일명 생성

        Args:
            student_name: 학생 이름
            grade: 학년
            extension: 파일 확장자

        Returns:
            생성된 파일명
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{student_name}_{grade}_{timestamp}.{extension}"
