# -*- coding: utf-8 -*-
"""초등 관심탐험 (모모의 이야기 탐험단) 블루프린트.

app/src/build.py로 이미지·데이터를 전부 base64로 내장해 빌드한 단일
정적 HTML(static/interest_quest/index.html)을 그대로 서빙한다. 서버
저장 없이 클라이언트(localStorage)에만 응답·별점을 남기는 독립 앱이라
DB 모델이 없다 - momoai_web의 다른 퀴즈(독서논술MBTI 등)와 달리 이 앱은
결과를 momoai_web으로 전송하지 않는다.
"""
from flask import Blueprint

interest_quest_bp = Blueprint('interest_quest', __name__)

from app.interest_quest import routes  # noqa: E402,F401
