# -*- coding: utf-8 -*-
"""강사 가이드 첨부파일(이미지/PDF/DOCX) 저장 및 Claude 프롬프트 변환.

첨삭을 처음 요청할 때(교사가 강사 가이드를 입력하는 시점) 함께 올린 참고자료를
저장하고, AI 첨삭 호출 시 Claude 메시지의 content 블록(이미지/문서)으로
변환한다. 학생·학부모에게는 노출하지 않는 강사/AI 전용 자료다.
"""
import base64
import os
import uuid

from flask import current_app

from app.models import db
from app.models.essay import EssayGuideAttachment
from app.utils.file_utils import safe_original_filename

MAX_FILES = 3
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # Claude 이미지 블록 권장 상한
MAX_DOC_SIZE = 15 * 1024 * 1024    # PDF/DOCX

# 확장자 -> (file_type, media_type)
EXT_MAP = {
    '.jpg': ('image', 'image/jpeg'),
    '.jpeg': ('image', 'image/jpeg'),
    '.png': ('image', 'image/png'),
    '.gif': ('image', 'image/gif'),
    '.webp': ('image', 'image/webp'),
    '.pdf': ('pdf', 'application/pdf'),
    '.docx': ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
}


class GuideAttachmentError(Exception):
    """업로드 검증 실패 시 사용자에게 그대로 보여줄 메시지를 담는다."""
    pass


def save_guide_attachments(essay, files):
    """강사 가이드 첨부파일을 저장하고 EssayGuideAttachment 레코드를 생성한다.

    Args:
        essay: Essay 객체 (essay_id 필요, 이미 커밋되어 있어야 함)
        files: request.files.getlist('guide_attachments') 결과

    Returns:
        저장된 파일 개수 (0이면 첨부 없음)

    Raises:
        GuideAttachmentError: 개수 초과, 형식/용량 검증 실패
    """
    files = [f for f in (files or []) if f and f.filename]
    if not files:
        return 0

    existing_count = len(essay.guide_attachments or [])
    if existing_count + len(files) > MAX_FILES:
        raise GuideAttachmentError(f'강사 가이드 첨부파일은 최대 {MAX_FILES}개까지 첨부할 수 있습니다.')

    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'guide_attachments')
    os.makedirs(upload_folder, exist_ok=True)

    saved = 0
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in EXT_MAP:
            raise GuideAttachmentError(
                f'"{file.filename}" - 지원하지 않는 파일 형식입니다. '
                '이미지(JPG/PNG/GIF/WEBP), PDF, DOCX(워드 최신 형식)만 첨부할 수 있습니다. '
                '구버전 워드(.doc)는 .docx나 PDF로 저장해서 올려주세요.'
            )
        file_type, media_type = EXT_MAP[ext]
        max_size = MAX_IMAGE_SIZE if file_type == 'image' else MAX_DOC_SIZE

        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > max_size:
            raise GuideAttachmentError(
                f'"{file.filename}" 용량이 너무 큽니다 (최대 {max_size // (1024 * 1024)}MB).'
            )

        original_filename = safe_original_filename(file.filename) or f'file{ext}'
        stored_filename = f'{uuid.uuid4().hex}{ext}'
        file_path = os.path.join(upload_folder, stored_filename)
        file.save(file_path)

        attachment = EssayGuideAttachment(
            essay_id=essay.essay_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=os.path.join('guide_attachments', stored_filename),
            file_type=file_type,
            media_type=media_type,
            file_size=size,
        )
        db.session.add(attachment)
        saved += 1

    db.session.commit()
    return saved


def build_guide_message_content(essay, text_content: str):
    """essay.guide_attachments를 반영해 Claude user 메시지 content를 만든다.

    첨부가 없으면 text_content(문자열)를 그대로 반환한다(기존 동작과 100%
    동일 - 캐시 프리픽스나 API 동작에 아무 영향 없음). 첨부가 있으면
    이미지/PDF는 content 블록으로, DOCX는 텍스트를 추출해 본문 앞에
    붙인 뒤 [image/document 블록..., text 블록] 리스트를 반환한다.
    """
    attachments = list(getattr(essay, 'guide_attachments', None) or [])
    if not attachments:
        return text_content

    blocks = []
    docx_text_parts = []
    upload_root = current_app.config['UPLOAD_FOLDER']

    for att in attachments:
        full_path = os.path.join(upload_root, att.file_path)
        if not os.path.exists(full_path):
            current_app.logger.warning('강사 가이드 첨부파일을 찾을 수 없음: %s', full_path)
            continue
        try:
            if att.file_type == 'image':
                with open(full_path, 'rb') as f:
                    data = base64.standard_b64encode(f.read()).decode('utf-8')
                blocks.append({
                    'type': 'image',
                    'source': {'type': 'base64', 'media_type': att.media_type, 'data': data},
                })
            elif att.file_type == 'pdf':
                with open(full_path, 'rb') as f:
                    data = base64.standard_b64encode(f.read()).decode('utf-8')
                blocks.append({
                    'type': 'document',
                    'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': data},
                })
            elif att.file_type == 'docx':
                text = _extract_docx_text(full_path)
                if text:
                    docx_text_parts.append(f'[첨부자료: {att.original_filename}]\n{text}')
        except Exception:
            current_app.logger.exception('강사 가이드 첨부파일 처리 실패: %s', att.original_filename)

    final_text = text_content
    if docx_text_parts:
        final_text = '\n\n'.join(docx_text_parts) + '\n\n' + text_content

    if not blocks and final_text == text_content:
        # docx 추출도 실패하고 이미지/PDF도 없으면(전부 파일 누락 등) 원래 텍스트만
        return text_content

    blocks.append({'type': 'text', 'text': final_text})
    return blocks


def _extract_docx_text(path: str) -> str:
    from docx import Document
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)
