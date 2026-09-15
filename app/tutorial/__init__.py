# -*- coding: utf-8 -*-
"""글쓰기 튜토리얼 Blueprint (1단계: 초등 코스1).

url_prefix는 다른 학생용 블루프린트(students_bp/student_bp)와 같은 방식으로
app.register_blueprint() 호출부에서 지정한다(Blueprint 생성자에는 안 둠).
"""
from flask import Blueprint

tutorial_bp = Blueprint('tutorial', __name__, template_folder='templates', static_folder=None)

from app.tutorial import routes  # noqa: E402,F401
