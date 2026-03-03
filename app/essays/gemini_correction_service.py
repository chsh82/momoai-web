# -*- coding: utf-8 -*-
"""Gemini 기반 첨삭 서비스 - MOMOAIService와 동일한 인터페이스"""
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import google.generativeai as genai
from flask import current_app

from app.models import db, Essay, EssayVersion, EssayResult, EssayScore, EssayNote
from app.essays.score_parser import get_parser

# 동시 호출 제한 (momoai_service와 공유하지 않고 별도 관리)
_gemini_semaphore = threading.Semaphore(2)


class GeminiCorrectionService:
    """Gemini 기반 첨삭 서비스 (Claude API 대체용)"""

    MODEL_NAME = 'gemini-2.0-flash'

    def __init__(self, api_key: Optional[str] = None):
        from config import Config
        self.api_key = api_key or Config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError('GEMINI_API_KEY가 설정되지 않았습니다.')
        genai.configure(api_key=self.api_key)

    # ------------------------------------------------------------------ #
    # 내부 유틸리티
    # ------------------------------------------------------------------ #

    def _load_system_prompt(self, correction_model: str = 'standard') -> str:
        """correction_model에 맞는 시스템 프롬프트 로드"""
        if correction_model == 'harkness':
            doc_path = current_app.config.get('MOMOAI_DOC_PATH')
        else:
            doc_path = current_app.config.get('MOMOAI_STANDARD_DOC_PATH')
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _create_prompt(self, student_name: str, grade: str, essay_text: str,
                       notes: Optional[str] = None,
                       teacher_name: Optional[str] = None,
                       revision_note: Optional[str] = None,
                       is_revision_of_completed: bool = False) -> str:
        """분석 프롬프트 생성 (MOMOAIService.create_analysis_prompt와 동일)"""
        if is_revision_of_completed:
            prompt = f"""학생 정보:
- 이름: {student_name}
- 학년: {grade}

이전 첨삭본:
{essay_text}

수정 요청 사항:
{revision_note}

위 첨삭본을 기반으로 수정 요청 사항을 반영하여 개선된 첨삭본을 생성해주세요.
MOMOAI v3.3.0 규칙을 준수하고, 반드시 HTML 완전 템플릿 형식으로 출력해주세요.
"""
        else:
            prompt = f"""학생 정보:
- 이름: {student_name}
- 학년: {grade}

논술문:
{essay_text}
"""
            if notes:
                prompt += f"\n주의사항:\n{notes}\n"
            if revision_note:
                prompt += f"\n수정 요청 사항:\n{revision_note}\n"

            prompt += """
위 논술문을 MOMOAI v3.3.0 규칙에 따라 첨삭해주세요.
반드시 HTML 완전 템플릿 형식으로 출력하고, 모든 규칙을 준수해주세요.

v3.3.0 필수 포함 사항:
1. 윤문 완성본 (원문 대비 1.3~2배 분량, 통계+사례 필수)
2. 💭 생각해볼 쟁점 세 가지 (내용첨삭과 비중복되는 심화 질문)
3. 교사 종합 제언
4. 푸터까지 완전한 HTML 문서

특히 "생각해볼 쟁점 세 가지" 섹션은 필수입니다. 내용 첨삭에서 지적한 문제가 아닌, 글을 넘어서는 심화 토론 주제 3가지를 제시해주세요.
"""

        if teacher_name:
            prompt += f"\n\n중요: HTML 문서의 맨 마지막 </body> 태그 직전에 다음 형식의 첨삭자 사인을 추가해주세요:\n"
            prompt += f'<div style="text-align: right; margin-top: 50px; padding: 20px; color: #666; font-style: italic;">\n'
            prompt += f'    첨삭: {teacher_name} (Gemini)\n'
            prompt += f'</div>\n'

        return prompt

    def _call_gemini(self, system_prompt: str, user_prompt: str,
                     max_retries: int = 3) -> str:
        """Gemini API 호출 (재시도 포함)"""
        model = genai.GenerativeModel(
            model_name=self.MODEL_NAME,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=8192,
                temperature=0.7,
            ),
        )

        delays = [30, 60, 120]
        for attempt in range(max_retries):
            try:
                with _gemini_semaphore:
                    response = model.generate_content(user_prompt)
                return response.text
            except Exception as e:
                print(f'[Gemini 오류] 시도 {attempt + 1}/{max_retries}: {e}')
                if attempt < max_retries - 1:
                    time.sleep(delays[attempt])
                else:
                    raise

    def generate_filename(self, student_name: str, grade: str, version: int) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name  = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in student_name)
        safe_grade = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in grade)
        return f'{safe_name}_{safe_grade}_v{version}_{timestamp}_gemini.html'

    def save_html(self, html_content: str, filename: str) -> str:
        html_folder = Path(current_app.config['HTML_FOLDER'])
        html_folder.mkdir(parents=True, exist_ok=True)
        filepath = html_folder / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return str(filepath)

    # ------------------------------------------------------------------ #
    # 공개 인터페이스 (MOMOAIService와 동일한 시그니처)
    # ------------------------------------------------------------------ #

    def process_essay(self, essay: Essay, student_name: str,
                      teacher_name: Optional[str] = None) -> Tuple[EssayVersion, str]:
        """첨삭 처리 (MOMOAIService.process_essay와 동일한 인터페이스)"""
        essay.status = 'processing'
        db.session.commit()

        try:
            notes = None
            if essay.notes:
                notes = '\n'.join([note.content for note in essay.notes])

            correction_model = getattr(essay, 'correction_model', 'standard') or 'standard'
            system_prompt = self._load_system_prompt(correction_model)
            user_prompt   = self._create_prompt(
                student_name, essay.grade, essay.original_text,
                notes=notes, teacher_name=teacher_name
            )

            html_content = self._call_gemini(system_prompt, user_prompt)

            filename = self.generate_filename(student_name, essay.grade, essay.current_version)
            html_path = self.save_html(html_content, filename)

            version = EssayVersion(
                essay_id=essay.essay_id,
                version_number=essay.current_version,
                html_content=html_content,
                html_path=html_path,
            )
            db.session.add(version)

            result = EssayResult(
                essay_id=essay.essay_id,
                version_id=version.version_id,
                html_path=html_path,
            )
            db.session.add(result)

            essay.status = 'reviewing'
            essay.completed_at = datetime.utcnow()
            db.session.commit()

            # 점수 파싱
            try:
                from app.essays.momoai_service import MOMOAIService
                from config import Config
                svc = MOMOAIService.__new__(MOMOAIService)
                svc.parse_and_save_scores(html_content, essay.essay_id, version.version_id)
            except Exception:
                pass  # 점수 파싱 실패는 무시 (첨삭 자체는 성공)

            return version, html_path

        except Exception as e:
            essay.status = 'failed'
            db.session.commit()
            raise e

    def regenerate_essay(self, essay: Essay, student_name: str,
                         revision_note: str,
                         teacher_name: Optional[str] = None) -> Tuple[EssayVersion, str]:
        """첨삭 재생성 (MOMOAIService.regenerate_essay와 동일한 인터페이스)"""
        essay.current_version += 1
        essay.status = 'processing'

        is_finalized = essay.is_finalized
        if is_finalized:
            essay.is_finalized = False
            essay.finalized_at = None

        db.session.commit()

        try:
            if is_finalized and essay.latest_version:
                essay_text = essay.latest_version.html_content
                notes = None
                is_revision_of_completed = True
            else:
                essay_text = essay.original_text
                notes = None
                if essay.notes:
                    notes = '\n'.join([note.content for note in essay.notes])
                is_revision_of_completed = False

            correction_model = getattr(essay, 'correction_model', 'standard') or 'standard'
            system_prompt = self._load_system_prompt(correction_model)
            user_prompt   = self._create_prompt(
                student_name, essay.grade, essay_text,
                notes=notes, teacher_name=teacher_name,
                revision_note=revision_note,
                is_revision_of_completed=is_revision_of_completed,
            )

            html_content = self._call_gemini(system_prompt, user_prompt)

            filename = self.generate_filename(student_name, essay.grade, essay.current_version)
            html_path = self.save_html(html_content, filename)

            version = EssayVersion(
                essay_id=essay.essay_id,
                version_number=essay.current_version,
                html_content=html_content,
                html_path=html_path,
                revision_note=revision_note,
            )
            db.session.add(version)

            essay.result.version_id = version.version_id
            essay.result.html_path = html_path
            essay.status = 'reviewing'
            db.session.commit()

            try:
                from app.essays.momoai_service import MOMOAIService
                svc = MOMOAIService.__new__(MOMOAIService)
                svc.parse_and_save_scores(html_content, essay.essay_id, version.version_id)
            except Exception:
                pass

            return version, html_path

        except Exception as e:
            essay.status = 'failed'
            db.session.commit()
            raise e
