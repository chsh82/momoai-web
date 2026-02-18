#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""프로젝트 구조 생성 스크립트"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 생성할 디렉토리 목록
directories = [
    'app',
    'app/models',
    'app/auth',
    'app/essays',
    'app/students',
    'app/dashboard',
    'migrations',
]

# 디렉토리 생성
for dir_path in directories:
    full_path = BASE_DIR / dir_path
    full_path.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Created: {dir_path}")

# __init__.py 파일 생성
init_files = [
    'app/__init__.py',
    'app/models/__init__.py',
    'app/auth/__init__.py',
    'app/essays/__init__.py',
    'app/students/__init__.py',
    'app/dashboard/__init__.py',
]

for init_file in init_files:
    file_path = BASE_DIR / init_file
    if not file_path.exists():
        file_path.write_text('# -*- coding: utf-8 -*-\n', encoding='utf-8')
        print(f"[OK] Created: {init_file}")

print("\n[SUCCESS] Project structure created!")
