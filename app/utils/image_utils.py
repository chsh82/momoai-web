# -*- coding: utf-8 -*-
"""게시판 이미지 업로드/삭제 유틸리티"""
import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_IMAGES_PER_POST = 10


def is_allowed_image(filename: str) -> bool:
    """허용된 이미지 확장자 여부 확인"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def get_images_folder() -> Path:
    """이미지 저장 폴더 경로 반환 (없으면 생성)"""
    folder = Path(current_app.config['POST_IMAGES_FOLDER'])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_post_images(files, board_type: str, post_id: str, uploader_id: str,
                     existing_count: int = 0):
    """
    여러 이미지 파일을 저장하고 PostImage 객체 리스트를 반환한다.

    :param files: request.files.getlist('images') 결과
    :param board_type: 게시판 유형 문자열
    :param post_id: 게시글 PK
    :param uploader_id: 업로드 사용자 user_id
    :param existing_count: 이미 첨부된 이미지 수 (수정 시)
    :return: 저장된 PostImage 객체 리스트
    """
    from app.models.post_image import PostImage

    saved = []
    folder = get_images_folder()
    remaining_slots = MAX_IMAGES_PER_POST - existing_count

    for idx, file in enumerate(files):
        if idx >= remaining_slots:
            break
        if not file or not file.filename:
            continue
        if not is_allowed_image(file.filename):
            continue

        original_filename = secure_filename(file.filename)
        ext = Path(original_filename).suffix.lower()
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = folder / stored_filename

        file.save(str(file_path))
        file_size = file_path.stat().st_size

        img = PostImage(
            board_type=board_type,
            post_id=post_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            order=existing_count + idx,
            uploaded_by=uploader_id,
        )
        saved.append(img)

    return saved


def delete_post_image(image_obj):
    """PostImage 객체를 DB + 파일시스템에서 삭제"""
    folder = get_images_folder()
    file_path = folder / image_obj.stored_filename
    if file_path.exists():
        file_path.unlink()

    from app.models import db
    db.session.delete(image_obj)


def delete_post_images_by_post(board_type: str, post_id: str):
    """게시글에 연결된 모든 이미지를 삭제"""
    from app.models.post_image import PostImage
    images = PostImage.query.filter_by(
        board_type=board_type, post_id=post_id
    ).all()
    for img in images:
        delete_post_image(img)


def get_post_images(board_type: str, post_id: str):
    """게시글에 연결된 이미지를 순서대로 반환"""
    from app.models.post_image import PostImage
    return PostImage.query.filter_by(
        board_type=board_type, post_id=post_id
    ).order_by(PostImage.order.asc()).all()
