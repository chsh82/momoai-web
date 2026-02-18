# -*- coding: utf-8 -*-
"""OCR 서비스"""
import time
import os
import tempfile
from PIL import Image


class OCRService:
    """OCR 인식 서비스"""

    def __init__(self):
        """초기화"""
        self.reader = None

    def _init_reader(self):
        """EasyOCR reader 초기화 (처음 호출 시에만)"""
        if self.reader is None:
            try:
                import easyocr
                # 한글과 영어 지원
                self.reader = easyocr.Reader(['ko', 'en'], gpu=False)
            except ImportError:
                raise Exception(
                    'EasyOCR 라이브러리가 설치되지 않았습니다. '
                    'pip install easyocr 명령으로 설치해주세요.'
                )

    def extract_text_from_image(self, image_path):
        """
        이미지에서 텍스트 추출

        Args:
            image_path: 이미지 파일 경로

        Returns:
            tuple: (추출된 텍스트, 처리 시간)
        """
        start_time = time.time()

        # Reader 초기화
        self._init_reader()

        # 이미지 파일 확인
        if not os.path.exists(image_path):
            raise FileNotFoundError(f'이미지 파일을 찾을 수 없습니다: {image_path}')

        # PIL로 이미지 열기 및 RGB 변환
        temp_file = None
        try:
            # 이미지 열기
            img = Image.open(image_path)

            # RGB로 변환 (easyocr이 처리하기 좋은 형식)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # 임시 파일로 저장
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            img.save(temp_file.name, 'JPEG', quality=95)
            temp_file.close()

            # OCR 수행 (임시 파일 경로 전달)
            results = self.reader.readtext(
                temp_file.name,
                paragraph=False,
                detail=1
            )

            # 결과 텍스트 조합
            extracted_lines = []
            for (bbox, text, confidence) in results:
                # 신뢰도가 0.1 이상인 것만 추출
                if confidence >= 0.1:
                    extracted_lines.append(text)

            extracted_text = '\n'.join(extracted_lines)
            processing_time = time.time() - start_time

            return extracted_text, processing_time

        except Exception as e:
            raise Exception(f'OCR 처리 중 오류가 발생했습니다: {str(e)}')

        finally:
            # 임시 파일 삭제
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

    def is_supported_image(self, filename):
        """
        지원되는 이미지 파일 형식인지 확인

        Args:
            filename: 파일명

        Returns:
            bool: 지원 여부
        """
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        ext = os.path.splitext(filename)[1].lower()
        return ext in allowed_extensions
