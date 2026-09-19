# -*- coding: utf-8 -*-
"""초등 관심탐험 라우트.

index.html 하나가 전체 앱(질문·채점·결과·인쇄)을 담고 있으므로 라우트는
로그인·권한 확인 후 그 파일을 그대로 돌려주는 것뿐이다.
"""
import os

from flask import current_app, send_file

from app.interest_quest import interest_quest_bp
from app.utils.decorators import requires_role


@interest_quest_bp.route('/')
@requires_role('admin')
def index():
    """모모의 이야기 탐험단 - 초등 관심탐험 (정적 단일 HTML)."""
    path = os.path.join(current_app.static_folder, 'interest_quest', 'index.html')
    return send_file(path)
