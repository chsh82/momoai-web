# -*- coding: utf-8 -*-
"""API 사용량 로그 모델"""
from datetime import datetime
from app.models import db

# 단가 (USD / 1M tokens) - claude-sonnet-5 기준 (공식: platform.claude.com/docs/en/about-claude/pricing)
CLAUDE_PRICING = {
    'input':       2.00,
    'output':     10.00,
    'cache_write': 2.50,  # 5분 캐시 write = base input의 1.25배
    'cache_read':  0.20,  # 캐시 read = base input의 0.1배
}

GEMINI_PRICING = {
    'gemini-3.6-flash': {'input': 0.75, 'output': 3.75},  # gemini-2.0-flash(2026-06-01 종료) 공식 대체 모델
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50},  # OCR(gemini_ocr_service.py)에서 사용 중
    # 아래는 더 이상 API에서 서비스되지 않는 구버전 - 과거 로그 참고용으로만 남김
    'gemini-2.0-flash': {'input': 0.075, 'output': 0.30},
    'gemini-1.5-flash': {'input': 0.075, 'output': 0.30},
    'gemini-pro':       {'input': 0.50,  'output': 1.50},
}


class ApiUsageLog(db.Model):
    __tablename__ = 'api_usage_logs'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id          = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True, index=True)
    api_type         = db.Column(db.String(20),  nullable=False)   # 'claude' | 'gemini'
    model_name       = db.Column(db.String(50))
    usage_type       = db.Column(db.String(50))   # 'correction' | 'regeneration' | 'ocr'
    essay_id         = db.Column(db.String(36),  nullable=True)

    input_tokens     = db.Column(db.Integer, default=0)
    output_tokens    = db.Column(db.Integer, default=0)
    cache_read_tokens  = db.Column(db.Integer, default=0)
    cache_write_tokens = db.Column(db.Integer, default=0)
    cost_usd         = db.Column(db.Float,   default=0.0)

    created_at       = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    # ── 비용 계산 ─────────────────────────────────────────
    @staticmethod
    def calc_claude_cost(input_tokens, output_tokens,
                         cache_read=0, cache_write=0):
        p = CLAUDE_PRICING
        return round(
            input_tokens  * p['input']       / 1_000_000 +
            output_tokens * p['output']      / 1_000_000 +
            cache_read    * p['cache_read']  / 1_000_000 +
            cache_write   * p['cache_write'] / 1_000_000,
            6
        )

    @staticmethod
    def calc_gemini_cost(model_name, input_tokens, output_tokens):
        p = GEMINI_PRICING.get(model_name, GEMINI_PRICING['gemini-2.5-flash'])
        return round(
            input_tokens  * p['input']  / 1_000_000 +
            output_tokens * p['output'] / 1_000_000,
            6
        )
