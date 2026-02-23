# -*- coding: utf-8 -*-
"""SQLAlchemy 모델 패키지"""
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy 인스턴스 생성
db = SQLAlchemy()

# 모델 import (순환 참조 방지를 위해 db 정의 후 import)
from app.models.user import User
from app.models.student import Student
from app.models.essay import Essay, EssayVersion, EssayResult, CorrectionAttachment
from app.models.essay_score import EssayScore, EssayNote
from app.models.book import Book, EssayBook
from app.models.community import Post, Comment, PostLike
from app.models.notification import Notification
from app.models.tag import Tag, PostTag, Bookmark
from app.models.post_file import PostFile
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.payment import Payment
from app.models.parent_student import ParentStudent
from app.models.teacher_feedback import TeacherFeedback
from app.models.announcement import Announcement, AnnouncementRead
from app.models.message import Message, MessageRecipient
from app.models.teaching_material import TeachingMaterial, TeachingMaterialDownload, TeachingMaterialFile
from app.models.video import Video, VideoView
from app.models.makeup_request import MakeupClassRequest
from app.models.parent_link_request import ParentLinkRequest
from app.models.teacher_board import TeacherBoard, TeacherBoardAttachment
from app.models.harkness_board import HarknessBoard, HarknessPost, HarknessComment, HarknessPostLike
from app.models.library import HallOfFame, AdmissionInfo
from app.models.class_board import ClassBoardPost, ClassBoardComment
from app.models.reading_mbti import (
    ReadingMBTITest,
    ReadingMBTIQuestion,
    ReadingMBTIType,
    ReadingMBTIResponse,
    ReadingMBTIResult
)
from app.models.zoom_access import ZoomAccessLog
from app.models.ocr_history import OCRHistory
from app.models.consultation import ConsultationRecord
from app.models.student_profile import StudentProfile
from app.models.login_log import LoginAttemptLog
from app.models.ace_evaluation import WeeklyEvaluation, AceEvaluation, ACE_AXES, ACE_ALL_ITEMS
from app.models.notification_reply import NotificationReply

__all__ = [
    'db',
    'User',
    'Student',
    'Essay',
    'EssayVersion',
    'EssayResult',
    'CorrectionAttachment',
    'EssayScore',
    'EssayNote',
    'Book',
    'EssayBook',
    'Post',
    'Comment',
    'PostLike',
    'Notification',
    'Tag',
    'PostTag',
    'Bookmark',
    'PostFile',
    'Course',
    'CourseEnrollment',
    'CourseSession',
    'Attendance',
    'Payment',
    'ParentStudent',
    'TeacherFeedback',
    'Announcement',
    'AnnouncementRead',
    'Message',
    'MessageRecipient',
    'TeachingMaterial',
    'TeachingMaterialDownload',
    'TeachingMaterialFile',
    'Video',
    'VideoView',
    'MakeupClassRequest',
    'ParentLinkRequest',
    'TeacherBoard',
    'TeacherBoardAttachment',
    'HarknessBoard',
    'HarknessPost',
    'HarknessComment',
    'HarknessPostLike',
    'HallOfFame',
    'AdmissionInfo',
    'ClassBoardPost',
    'ClassBoardComment',
    'ReadingMBTITest',
    'ReadingMBTIQuestion',
    'ReadingMBTIType',
    'ReadingMBTIResponse',
    'ReadingMBTIResult',
    'ZoomAccessLog',
    'OCRHistory',
    'ConsultationRecord',
    'StudentProfile',
    'LoginAttemptLog',
    'WeeklyEvaluation',
    'AceEvaluation',
    'ACE_AXES',
    'ACE_ALL_ITEMS',
    'NotificationReply',
]
