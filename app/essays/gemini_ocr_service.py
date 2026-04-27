# -*- coding: utf-8 -*-
"""Gemini AI 기반 고급 OCR 서비스 (google.genai SDK)"""
import os
import time
import json
import random
import threading
import PIL.Image
from google import genai
from google.genai import types
from config import Config


class GeminiOCRService:
    """Gemini AI를 활용한 OCR 및 분석 서비스"""

    # 동시 Gemini API 호출을 2개로 제한 (concurrent request 429 방지)
    _semaphore = threading.Semaphore(2)

    _SYSTEM_INSTRUCTION = (
        "너는 15년 경력의 베테랑 독서논술 강사이자 '초사고력' 교육 전문가야. "
        "학생의 수기 글쓰기 이미지를 받으면 문맥을 파악해 정확히 OCR하고, "
        "논술 9유형에 근거하여 날카롭지만 따뜻한 피드백을 제공해줘."
    )

    _PROMPT = (
        "학생의 글을 읽고 다음 세 가지 항목을 JSON 형식으로 작성해줘.\n"
        "1. original_text: 오타를 포함하여 써진 그대로의 원문 텍스트.\n"
        "2. summary: 글의 핵심 논리와 학생의 사고 수준에 대한 분석 (초사고력 관점).\n"
        "3. corrected_text: 가독성과 맞춤법을 고려하여 자연스럽게 다듬은 교정본."
    )

    def __init__(self, api_key=None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = 'gemini-2.5-flash'
        self.client = genai.Client(api_key=self.api_key)

    def _log_gemini_usage(self, response, user_id=None, essay_id=None, usage_type='ocr'):
        try:
            from app.models.api_usage_log import ApiUsageLog
            from app.models import db
            meta = getattr(response, 'usage_metadata', None)
            input_tok  = getattr(meta, 'prompt_token_count',     0) if meta else 0
            output_tok = getattr(meta, 'candidates_token_count', 0) if meta else 0
            cost = ApiUsageLog.calc_gemini_cost(self.model_name, input_tok, output_tok)
            log = ApiUsageLog(
                user_id=user_id,
                api_type='gemini',
                model_name=self.model_name,
                usage_type=usage_type,
                essay_id=essay_id,
                input_tokens=input_tok,
                output_tokens=output_tok,
                cost_usd=cost,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"[Gemini 사용량 로그 저장 실패] {e}")

    def extract_and_analyze(self, image_path, user_id=None, essay_id=None):
        """
        이미지 또는 PDF에서 텍스트 추출 + 내용 분석 + 맞춤법 교정

        Returns:
            tuple: (추출된 텍스트, 요약/분석, 교정된 텍스트, 처리 시간)
        """
        start_time = time.time()
        ext = os.path.splitext(image_path)[1].lower()
        is_pdf = (ext == '.pdf')

        config = types.GenerateContentConfig(
            system_instruction=self._SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
        )

        max_retries = 4
        last_exc = None
        for attempt in range(max_retries):
            try:
                with self._semaphore:
                    if is_pdf:
                        uploaded_file = self.client.files.upload(
                            file=image_path,
                            config={'mime_type': 'application/pdf'},
                        )
                        try:
                            response = self.client.models.generate_content(
                                model=self.model_name,
                                contents=[uploaded_file, self._PROMPT],
                                config=config,
                            )
                        finally:
                            try:
                                self.client.files.delete(name=uploaded_file.name)
                            except Exception:
                                pass
                    else:
                        with PIL.Image.open(image_path) as img:
                            response = self.client.models.generate_content(
                                model=self.model_name,
                                contents=[img, self._PROMPT],
                                config=config,
                            )

                result = json.loads(response.text)
                if isinstance(result, list):
                    result = result[0] if result else {}
                original_text   = result.get('original_text',  '텍스트 추출 실패')
                summary         = result.get('summary',        '분석 불가')
                corrected_text  = result.get('corrected_text', '교정 불가')
                self._log_gemini_usage(response, user_id=user_id, essay_id=essay_id, usage_type='ocr')
                last_exc = None
                break

            except Exception as e:
                err_str = str(e)
                print(f"[Gemini Error] {err_str}")
                last_exc = e
                if '429' in err_str and attempt < max_retries - 1:
                    wait = 5 * (2 ** attempt) + random.uniform(0, 2)
                    print(f"[Gemini] Rate limit, {wait:.1f}초 후 재시도 ({attempt+1}/{max_retries-1})")
                    time.sleep(wait)
                    continue
                raise e

        if last_exc:
            raise last_exc

        return original_text, summary, corrected_text, time.time() - start_time

    def simple_extract(self, image_path):
        """간단한 텍스트 추출만 수행 (분석/교정 없음)"""
        start_time = time.time()
        try:
            with PIL.Image.open(image_path) as img:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        img,
                        "이미지의 모든 텍스트를 정확하게 추출해주세요. 텍스트만 반환하고 다른 설명은 하지 마세요.",
                    ],
                )
            return response.text.strip(), time.time() - start_time
        except Exception as e:
            raise Exception(f'Gemini OCR 처리 중 오류가 발생했습니다: {str(e)}')
