# -*- coding: utf-8 -*-
"""문자 메시지 테이블 생성 스크립트"""
from app import create_app, db
from app.models.message import Message, MessageRecipient

app = create_app()

with app.app_context():
    print("=" * 60)
    print("문자 메시지 테이블 생성")
    print("=" * 60)

    # 테이블 생성
    db.create_all()

    print("\n[OK] 테이블 생성 완료!")
    print("\n생성된 테이블:")
    print("  - messages: 문자 메시지 (SMS/LMS)")
    print("  - message_recipients: 문자 수신자 상세")

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)
