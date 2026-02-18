"""Content access control utilities for teaching materials and videos."""

import json
import re
from datetime import date
from app.models.course import CourseEnrollment


# Grade mapping from broad to specific grades
GRADE_MAP = {
    '초등': ['초1', '초2', '초3', '초4', '초5', '초6'],
    '중등': ['중1', '중2', '중3'],
    '고등': ['고1', '고2', '고3']
}


def can_access_content(content, user, student=None):
    """
    Check if user/student can access content (material or video).

    Args:
        content: TeachingMaterial or Video object
        user: User object (current_user)
        student: Student object (for student/parent access)

    Returns:
        bool: True if access is allowed
    """
    # 1. Admin/Manager always have access
    if user.role_level <= 2:
        return True

    # 2. Check if published
    if not content.is_public:
        return False

    # 3. Check date range
    today = date.today()
    if not (content.publish_date <= today <= content.end_date):
        return False

    # 4. If no student context (shouldn't happen for student/parent), deny access
    if not student:
        return False

    # 5. Check target audience
    try:
        target = json.loads(content.target_audience)
    except (json.JSONDecodeError, TypeError):
        return False

    if target.get('type') == 'grade':
        # Map student's broad grade to specific grades
        target_grades = target.get('grades', [])
        if not target_grades:  # Empty = all grades
            return True

        # If student.grade is in GRADE_MAP (broad like '중등'), expand it
        # Otherwise use the specific grade directly (like '중2')
        student_grades = GRADE_MAP.get(student.grade, [student.grade])
        return any(g in target_grades for g in student_grades)

    elif target.get('type') == 'course':
        # Check if student enrolled in target courses
        target_course_ids = target.get('course_ids', [])
        if not target_course_ids:  # Empty = all courses
            return True

        enrollments = CourseEnrollment.query.filter_by(
            student_id=student.student_id,
            status='active'
        ).all()
        enrolled_ids = [e.course_id for e in enrollments]
        return any(cid in target_course_ids for cid in enrolled_ids)

    return False


def get_accessible_materials(student, material_model):
    """
    Get all materials accessible to a student.

    Args:
        student: Student object
        material_model: TeachingMaterial class

    Returns:
        list: List of accessible TeachingMaterial objects
    """
    today = date.today()
    all_materials = material_model.query.filter(
        material_model.is_public == True,
        material_model.publish_date <= today,
        material_model.end_date >= today
    ).order_by(material_model.created_at.desc()).all()

    # Need to pass a user context - we'll check this in the route
    # For now, just return materials that match date/public criteria
    # Final filtering will happen in the route with can_access_content
    return all_materials


def get_accessible_videos(student, video_model):
    """
    Get all videos accessible to a student.

    Args:
        student: Student object
        video_model: Video class

    Returns:
        list: List of accessible Video objects
    """
    today = date.today()
    all_videos = video_model.query.filter(
        video_model.is_public == True,
        video_model.publish_date <= today,
        video_model.end_date >= today
    ).order_by(video_model.created_at.desc()).all()

    return all_videos


def extract_youtube_video_id(url):
    """
    Extract video ID from YouTube URL.

    Supports formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID

    Args:
        url: YouTube URL string

    Returns:
        str: Video ID or None if not found
    """
    if not url:
        return None

    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def format_file_size(bytes):
    """
    Format file size in human-readable format.

    Args:
        bytes: File size in bytes

    Returns:
        str: Formatted file size (e.g., "1.5 MB")
    """
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.1f} GB"
