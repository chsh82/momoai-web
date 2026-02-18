# -*- coding: utf-8 -*-
"""OCR 히스토리 모델"""
from datetime import datetime
from app.models import db


class OCRHistory(db.Model):
    """OCR 인식 히스토리"""
    __tablename__ = 'ocr_history'

    ocr_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    essay_id = db.Column(db.Integer, db.ForeignKey('essays.essay_id'), nullable=True)  # 과제에서 OCR한 경우

    # 원본 이미지 정보
    original_filename = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)

    # OCR 결과
    extracted_text = db.Column(db.Text, nullable=False)

    # Gemini AI 분석 결과 (선택적)
    summary = db.Column(db.Text)  # 내용 요약 및 분석
    corrected_text = db.Column(db.Text)  # 맞춤법 교정된 텍스트

    # 메타 정보
    ocr_method = db.Column(db.String(50), default='easyocr')  # 'easyocr' 또는 'gemini'
    processing_time = db.Column(db.Float)  # OCR 처리 시간 (초)
    character_count = db.Column(db.Integer)  # 추출된 글자 수

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 관계
    user = db.relationship('User', backref='ocr_history')
    essay = db.relationship('Essay', backref='ocr_records')

    def __repr__(self):
        return f'<OCRHistory {self.ocr_id}: {self.original_filename}>'
