import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR / 'outputs'
HTML_FOLDER = OUTPUT_FOLDER / 'html'
PDF_FOLDER = OUTPUT_FOLDER / 'pdf'
MOMOAI_DOC_PATH = Path(r"C:\Users\aproa\Downloads\MOMOAI_v3_3_0_final (20260112).md")

# API 키
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# 업로드 제한
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'xlsx', 'csv'}

# 폴더 생성
for folder in [UPLOAD_FOLDER, HTML_FOLDER, PDF_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)
