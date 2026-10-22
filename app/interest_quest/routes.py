# -*- coding: utf-8 -*-
"""초등 관심탐험 라우트.

index.html 하나가 전체 앱(질문·채점·결과·인쇄)을 담고 있으므로 라우트는
로그인·권한 확인 후 그 파일을 그대로 돌려주는 것뿐이다.
"""
import os

from flask import send_file

from app.interest_quest import interest_quest_bp
from app.utils.student_launch import student_launch_required


@interest_quest_bp.route('/')
@student_launch_required('STUDENT_INTEREST_QUEST_ENABLED')
def index():
    """로그인·출시 게이트 뒤에서만 제공하는 단일 HTML."""
    path = os.path.join(os.path.dirname(__file__), 'protected', 'index.html')
    response = send_file(path)
    response.headers['Cache-Control'] = 'private, no-store'
    return response
