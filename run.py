#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MOMOAI v4.0 서버 실행"""
import os
import sys
import io
from app import create_app
from config import Config

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 환경 변수에서 설정 가져오기 (FLASK_ENV 누락 시 안전한 쪽인 production으로 폴백)
config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    print("=" * 50)
    print("MOMOAI v4.0 Web Application")
    print("=" * 50)
    print(f"Environment: {config_name}")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Debug Mode: {app.config['DEBUG']}")
    print("=" * 50)
    print("Server starting...")
    print("URL: http://localhost:5000")
    print("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5000)
