# -*- coding: utf-8 -*-
"""Gemini AI 기반 고급 OCR 서비스"""
import time
import json
import re
import google.generativeai as genai
import PIL.Image
from config import Config


class GeminiOCRService:
    """Gemini AI를 활용한 OCR 및 분석 서비스"""

    def __init__(self, api_key=None):
        """초기화"""
        self.api_key = api_key or Config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
        # 모델 명칭을 최신 안정화 버전으로 수정
        self.model_name = 'gemini-2.0-flash'
        self.model = None

    def _init_model(self):
        """Gemini 모델 초기화 (처음 호출 시에만)"""
        if not self.model:
            # 모델 생성 시 'system_instruction'을 직접 주입합니다.
            # 이것이 제가 직접 읽을 때와 같은 지능을 발휘하게 만드는 핵심입니다.
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction="""
                너는 15년 경력의 베테랑 독서논술 강사이자 '초사고력' 교육 전문가야.
                학생의 수기 글쓰기 이미지를 받으면 문맥을 파악해 정확히 OCR하고,
                논술 9유형에 근거하여 날카롭지만 따뜻한 피드백을 제공해줘.
                """
            )

    def extract_and_analyze(self, image_path):
        """
        이미지에서 텍스트 추출 + 내용 분석 + 맞춤법 교정

        Args:
            image_path: 이미지 파일 경로

        Returns:
            tuple: (추출된 텍스트, 요약/분석, 교정된 텍스트, 처리 시간)
        """
        start_time = time.time()
        self._init_model()

        image = PIL.Image.open(image_path)

        # 9유형 및 초사고력 철학을 반영한 프롬프트 강화
        prompt = """
        이미지 속 학생의 글을 읽고 다음 세 가지 항목을 JSON 형식으로 작성해줘.
        1. original_text: 오타를 포함하여 이미지에 써진 그대로의 원문 텍스트.
        2. summary: 글의 핵심 논리와 학생의 사고 수준에 대한 분석 (초사고력 관점).
        3. corrected_text: 가독성과 맞춤법을 고려하여 자연스럽게 다듬은 교정본.
        """

        try:
            # [핵심] 출력 형식을 JSON으로 강제하여 정확도를 높입니다.
            response = self.model.generate_content(
                [image, prompt],
                generation_config={"response_mime_type": "application/json"}
            )

            # JSON 파싱 (마크다운 제거 불필요 - 순수 JSON 반환됨)
            result = json.loads(response.text)

            original_text = result.get('original_text', '텍스트 추출 실패')
            summary = result.get('summary', '분석 불가')
            corrected_text = result.get('corrected_text', '교정 불가')

        except Exception as e:
            print(f"[Gemini Error] {str(e)}")
            raise e  # 상위 route에서 catch하여 에러 표시

        processing_time = time.time() - start_time
        return original_text, summary, corrected_text, processing_time

    def simple_extract(self, image_path):
        """
        간단한 텍스트 추출만 수행 (분석/교정 없음)

        Args:
            image_path: 이미지 파일 경로

        Returns:
            tuple: (추출된 텍스트, 처리 시간)
        """
        start_time = time.time()

        # 모델 초기화
        self._init_model()

        # 이미지 로드
        try:
            image = PIL.Image.open(image_path)
        except Exception as e:
            raise Exception(f'이미지 파일을 열 수 없습니다: {str(e)}')

        # 간단한 프롬프트
        prompt = "이미지의 모든 텍스트를 정확하게 추출해주세요. 텍스트만 반환하고 다른 설명은 하지 마세요."

        # API 호출
        try:
            response = self.model.generate_content([prompt, image])
            text = response.text.strip()
            processing_time = time.time() - start_time

            return text, processing_time

        except Exception as e:
            raise Exception(f'Gemini OCR 처리 중 오류가 발생했습니다: {str(e)}')
