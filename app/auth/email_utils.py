# -*- coding: utf-8 -*-
"""이메일 인증 유틸리티"""
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app, url_for


def generate_verification_token(email):
    """이메일 인증 토큰 생성"""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(email, salt='email-verification-salt')


def verify_email_token(token, max_age=86400):
    """이메일 인증 토큰 검증 (기본 유효시간: 24시간)"""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='email-verification-salt', max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None


def send_verification_email(user):
    """이메일 인증 메일 발송"""
    if not current_app.config.get('MAIL_SERVER'):
        return False

    from app.extensions import mail
    from flask_mail import Message

    token = generate_verification_token(user.email)
    user.email_verification_token = token

    verify_url = url_for('auth.verify_email', token=token, _external=True)

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Noto Sans KR', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f0f2f5;">
        <div style="background: linear-gradient(135deg, #1A2744, #1E3A5F); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">📚 모모의 책장</h1>
            <p style="color: rgba(255,255,255,0.7); margin: 8px 0 0; font-size: 13px;">MOMOAI v4.0</p>
        </div>
        <div style="background: white; padding: 40px 30px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <h2 style="color: #1A2744; margin-top: 0;">이메일 인증</h2>
            <p style="color: #475569;">안녕하세요, <strong>{user.name}</strong>님!</p>
            <p style="color: #475569;">MOMOAI에 가입해 주셔서 감사합니다.<br>아래 버튼을 클릭하여 이메일 인증을 완료해주세요.</p>
            <div style="text-align: center; margin: 35px 0;">
                <a href="{verify_url}"
                   style="background: #3B82F6; color: white; padding: 15px 35px;
                          border-radius: 8px; text-decoration: none; font-weight: bold;
                          font-size: 16px; display: inline-block;">
                    ✉️ 이메일 인증하기
                </a>
            </div>
            <div style="background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 8px; padding: 15px; margin-top: 20px;">
                <p style="color: #92400E; margin: 0; font-size: 13px;">
                    ⚠️ 이 링크는 <strong>24시간</strong> 동안 유효합니다.<br>
                    본인이 가입하지 않으셨다면 이 이메일을 무시해주세요.
                </p>
            </div>
            <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 25px 0;">
            <p style="color: #94A3B8; font-size: 12px; text-align: center; margin: 0;">
                © 2026 MOMOAI - 모모의 책장. All rights reserved.
            </p>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject='[MOMOAI] 이메일 인증을 완료해주세요',
        sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@momoai.kr'),
        recipients=[user.email],
        html=html_body
    )

    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'이메일 발송 실패 ({user.email}): {e}')
        return False
