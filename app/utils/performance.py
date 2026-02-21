# -*- coding: utf-8 -*-
"""성능 최적화 유틸리티"""
from PIL import Image
import os
from pathlib import Path


def optimize_image(image_path, output_path=None, max_width=1920, quality=85):
    """
    이미지 최적화 및 크기 조정

    Args:
        image_path: 원본 이미지 경로
        output_path: 출력 경로 (None이면 원본 덮어쓰기)
        max_width: 최대 너비 (기본 1920px)
        quality: JPEG 품질 (1-100, 기본 85)

    Returns:
        bool: 성공 여부
    """
    try:
        # 이미지 열기
        img = Image.open(image_path)

        # EXIF 회전 정보 적용
        if hasattr(img, '_getexif') and img._getexif():
            exif = dict(img._getexif().items())
            if 274 in exif:  # Orientation tag
                if exif[274] == 3:
                    img = img.rotate(180, expand=True)
                elif exif[274] == 6:
                    img = img.rotate(270, expand=True)
                elif exif[274] == 8:
                    img = img.rotate(90, expand=True)

        # 크기 조정 (비율 유지)
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # RGB 모드로 변환 (JPEG 저장을 위해)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 저장 경로 결정
        if output_path is None:
            output_path = image_path

        # 최적화하여 저장
        img.save(output_path, 'JPEG', quality=quality, optimize=True)

        return True
    except Exception as e:
        print(f"이미지 최적화 실패: {e}")
        return False


def create_thumbnail(image_path, thumbnail_path, size=(300, 300)):
    """
    썸네일 생성

    Args:
        image_path: 원본 이미지 경로
        thumbnail_path: 썸네일 저장 경로
        size: 썸네일 크기 (width, height)

    Returns:
        bool: 성공 여부
    """
    try:
        img = Image.open(image_path)

        # RGB 모드로 변환
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 썸네일 생성 (비율 유지하며 크기 맞춤)
        img.thumbnail(size, Image.Resampling.LANCZOS)

        # 저장
        img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)

        return True
    except Exception as e:
        print(f"썸네일 생성 실패: {e}")
        return False


def get_file_size_mb(file_path):
    """
    파일 크기를 MB 단위로 반환

    Args:
        file_path: 파일 경로

    Returns:
        float: 파일 크기 (MB)
    """
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        return round(size_mb, 2)
    except Exception:
        return 0


def batch_optimize_images(directory, max_width=1920, quality=85):
    """
    디렉토리 내 모든 이미지 일괄 최적화

    Args:
        directory: 이미지가 있는 디렉토리
        max_width: 최대 너비
        quality: JPEG 품질

    Returns:
        dict: 최적화 결과 통계
    """
    stats = {
        'total': 0,
        'optimized': 0,
        'failed': 0,
        'size_before': 0,
        'size_after': 0
    }

    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')

    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(image_extensions):
                file_path = os.path.join(root, filename)

                # 최적화 전 크기
                size_before = get_file_size_mb(file_path)
                stats['size_before'] += size_before
                stats['total'] += 1

                # 최적화 실행
                if optimize_image(file_path, max_width=max_width, quality=quality):
                    size_after = get_file_size_mb(file_path)
                    stats['size_after'] += size_after
                    stats['optimized'] += 1
                    print(f"✓ {filename}: {size_before}MB → {size_after}MB")
                else:
                    stats['failed'] += 1
                    print(f"✗ {filename}: 최적화 실패")

    return stats
