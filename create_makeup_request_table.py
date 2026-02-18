# -*- coding: utf-8 -*-
"""보강수업 신청 테이블 생성"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.makeup_request import MakeupClassRequest

def create_table():
    """MakeupClassRequest 테이블 생성"""
    app = create_app()

    with app.app_context():
        try:
            # 테이블 생성
            db.create_all()
            print("[OK] makeup_class_requests table created successfully.")

        except Exception as e:
            print(f"[ERROR] {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_table()
