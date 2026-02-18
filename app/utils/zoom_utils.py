# -*- coding: utf-8 -*-
"""온라인 강의실 (Zoom) 관련 유틸리티"""
import secrets
import string
from cryptography.fernet import Fernet
from flask import current_app
from datetime import datetime, timedelta


def generate_zoom_token(teacher_name):
    """
    강사별 고정 줌 토큰 생성
    형식: momoai-{이름이니셜}{랜덤6자리}
    예: momoai-PSJ001, momoai-KMH002
    """
    # 이름에서 이니셜 추출 (한글 → 로마자 변환)
    initials = get_korean_initials(teacher_name)

    # 랜덤 3자리 숫자 생성
    random_num = ''.join(secrets.choice(string.digits) for _ in range(3))

    return f"momoai-{initials}{random_num}"


def get_korean_initials(name):
    """
    한글 이름에서 이니셜 추출
    예: 박선진 → PSJ, 김민희 → KMH
    """
    # 한글 초성 → 로마자 매핑
    chosung_map = {
        'ㄱ': 'G', 'ㄲ': 'KK', 'ㄴ': 'N', 'ㄷ': 'D', 'ㄸ': 'DD',
        'ㄹ': 'R', 'ㅁ': 'M', 'ㅂ': 'B', 'ㅃ': 'BB', 'ㅅ': 'S',
        'ㅆ': 'SS', 'ㅇ': '', 'ㅈ': 'J', 'ㅉ': 'JJ', 'ㅊ': 'C',
        'ㅋ': 'K', 'ㅌ': 'T', 'ㅍ': 'P', 'ㅎ': 'H'
    }

    initials = []
    for char in name:
        if '가' <= char <= '힣':
            # 유니코드에서 초성 추출
            chosung_index = (ord(char) - ord('가')) // 588
            chosung = chr(0x1100 + chosung_index)

            # 초성을 로마자로 변환
            for key, value in chosung_map.items():
                if chosung == chr(0x1100 + list(chosung_map.keys()).index(key)):
                    if value:  # 'ㅇ'은 빈 문자열이므로 제외
                        initials.append(value)
                    break

    return ''.join(initials)[:3]  # 최대 3글자까지


def encrypt_zoom_link(zoom_url):
    """
    줌 링크 암호화
    실제 줌 URL을 암호화하여 저장
    """
    if not zoom_url:
        return None

    # Fernet 암호화 키 (환경변수에서 가져오거나 생성)
    key = current_app.config.get('ZOOM_ENCRYPTION_KEY')
    if not key:
        # 개발 환경용 임시 키 (실제로는 환경변수에서 가져와야 함)
        key = b'rARYZ-FKOPSy6vhz4672zlKGV6lgxwN3M4_QLiOEymY='

    fernet = Fernet(key)
    encrypted = fernet.encrypt(zoom_url.encode())
    return encrypted.decode()


def decrypt_zoom_link(encrypted_zoom_link):
    """
    암호화된 줌 링크 복호화
    """
    if not encrypted_zoom_link:
        return None

    key = current_app.config.get('ZOOM_ENCRYPTION_KEY')
    if not key:
        key = b'rARYZ-FKOPSy6vhz4672zlKGV6lgxwN3M4_QLiOEymY='

    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(encrypted_zoom_link.encode())
        return decrypted.decode()
    except Exception as e:
        current_app.logger.error(f"줌 링크 복호화 실패: {e}")
        return None


def can_access_zoom(session_start_time, current_time=None):
    """
    줌 강의실 접속 가능 여부 확인
    수업 시작 10분 전부터 접속 가능

    Args:
        session_start_time: 수업 시작 시간 (datetime)
        current_time: 현재 시간 (datetime, 테스트용)

    Returns:
        tuple: (접속가능여부, 메시지)
    """
    if current_time is None:
        current_time = datetime.now()

    # 수업 시작 10분 전
    access_time = session_start_time - timedelta(minutes=10)

    if current_time < access_time:
        # 아직 접속 불가
        minutes_left = int((access_time - current_time).total_seconds() / 60)
        return False, f"수업 시작 10분 전부터 입장 가능합니다. (약 {minutes_left}분 후)"

    # 접속 가능
    return True, "입장 가능합니다."


def get_current_or_upcoming_session(student_id):
    """
    학생의 현재 또는 다가오는 수업 세션 찾기
    오늘 또는 내일의 수업 중에서 가장 가까운 수업 반환

    Args:
        student_id: 학생 ID

    Returns:
        CourseSession 또는 None
    """
    from app.models import CourseSession, CourseEnrollment, db
    from sqlalchemy import and_

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = (today_start + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

    # 학생이 등록한 코스들의 세션 조회
    session = db.session.query(CourseSession).join(
        CourseEnrollment,
        CourseSession.course_id == CourseEnrollment.course_id
    ).filter(
        and_(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == 'active',
            CourseSession.session_date >= today_start,
            CourseSession.session_date < tomorrow_end,
            CourseSession.status == 'scheduled'
        )
    ).order_by(CourseSession.session_date).first()

    return session


def log_zoom_access(student_id, teacher_id, course_id=None, session_id=None,
                    ip_address=None, user_agent=None):
    """
    줌 접속 로그 기록

    Args:
        student_id: 학생 ID
        teacher_id: 강사 ID
        course_id: 코스 ID (선택)
        session_id: 세션 ID (선택)
        ip_address: IP 주소 (선택)
        user_agent: User Agent (선택)
    """
    from app.models import ZoomAccessLog, db

    log = ZoomAccessLog(
        student_id=student_id,
        teacher_id=teacher_id,
        course_id=course_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(log)
    db.session.commit()

    return log
