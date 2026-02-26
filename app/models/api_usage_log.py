# -*- coding: utf-8 -*-
"""API 사용량 로그 모델"""
from datetime import datetime
from app.models import db

# 단가 (USD / 1M tokens)
CLAUDE_PRICING = {
    'input':       3.00,
    'output':     15.00,
    'cache_write': 3.75,
    'cache_read':  0.30,
}

GEMINI_PRICING = {
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
        p = GEMINI_PRICING.get(model_name, {'input': 0.075, 'output': 0.30})
        return round(
            input_tokens  * p['input']  / 1_000_000 +
            output_tokens * p['output'] / 1_000_000,
            6
        )
