# -*- coding: utf-8 -*-
"""특정 강사에게 줌 링크 설정"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.utils.zoom_utils import encrypt_zoom_link, generate_zoom_token

def setup_zoom_for_teacher(teacher_name):
    """특정 강사에게 줌 링크 설정"""
    app = create_app()

    with app.app_context():
        # 강사 찾기
        teacher = User.query.filter_by(name=teacher_name, role='teacher', is_active=True).first()

        if not teacher:
            print(f"Error: '{teacher_name}' 강사를 찾을 수 없습니다.")
            return False

        # 테스트 줌 링크
        test_zoom_link = "https://zoom.us/j/9876543210?pwd=test5678"

        # 줌 링크 암호화
        encrypted_link = encrypt_zoom_link(test_zoom_link)
        teacher.zoom_link = encrypted_link

        # 토큰 생성
        if not teacher.zoom_token:
            teacher.zoom_token = generate_zoom_token(teacher.name)

        db.session.commit()

        print(f"Success: {teacher.name} 강사에게 줌 링크 설정 완료!")
        print(f"  Email: {teacher.email}")
        print(f"  Zoom Token: {teacher.zoom_token}")
        print(f"  Zoom Link: {test_zoom_link}")

        return True

if __name__ == '__main__':
    # 강현우 강사에게 줌 링크 설정
    setup_zoom_for_teacher("강현우")
