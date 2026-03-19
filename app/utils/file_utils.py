import os
import re


def safe_original_filename(filename):
    """
    원본 파일명을 안전하게 정제합니다.
    - 한글 등 유니코드 문자는 보존
    - 경로 구분자, null byte, 위험 문자만 제거
    - secure_filename()과 달리 한글 파일명 손상 없음
    """
    if not filename:
        return ''
    # null byte 및 경로 구분자 제거
    filename = filename.replace('\0', '').replace('/', '').replace('\\', '')
    # os.path.basename으로 경로 트래버설 방지
    filename = os.path.basename(filename)
    # 제어 문자 제거 (출력 가능한 문자 + 유니코드만 허용)
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    # 앞뒤 공백/점 제거
    filename = filename.strip().strip('.')
    return filename


def get_safe_filenames(file):
    """
    업로드 파일로부터 안전한 원본 파일명과 저장용 파일명을 반환합니다.

    Returns:
        (original_filename, stored_filename, raw_ext)
        - original_filename: DB/다운로드에 사용할 파일명 (한글 보존)
        - stored_filename:   디스크에 저장할 파일명 (UUID + 확장자)
        - raw_ext:           확장자 (예: '.hwp')
    """
    raw_ext = os.path.splitext(file.filename)[1]  # 원본에서 확장자 추출
    original = safe_original_filename(file.filename) or f"file{raw_ext}"
    stored = f"{_uuid_hex()}{raw_ext}"
    return original, stored, raw_ext


def _uuid_hex():
    import uuid
    return uuid.uuid4().hex
