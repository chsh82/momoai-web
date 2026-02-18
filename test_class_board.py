#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""클래스 게시판 테스트 데이터 생성"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, User, Course, CourseEnrollment, Student
from app.models.class_board import ClassBoardPost, ClassBoardComment
from datetime import datetime, timedelta

def create_test_data():
    """테스트용 클래스 게시판 데이터 생성"""
    app = create_app('development')

    with app.app_context():
        # 첫 번째 active 수업 찾기
        course = Course.query.filter_by(status='active').first()

        if not course:
            print("[ERROR] Active 수업을 찾을 수 없습니다.")
            return

        print(f"[OK] 테스트 수업: {course.course_name} (ID: {course.course_id})")

        # 강사 확인
        teacher = course.teacher
        if not teacher:
            print("[ERROR] 수업에 강사가 배정되지 않았습니다.")
            return

        print(f"[OK] 강사: {teacher.name}")

        # 해당 수업의 수강생 확인
        enrollments = CourseEnrollment.query.filter_by(
            course_id=course.course_id,
            status='active'
        ).all()

        if not enrollments:
            print("[ERROR] 수강생이 없습니다.")
            return

        print(f"[OK] 수강생: {len(enrollments)}명")

        # 기존 테스트 게시글 삭제
        existing_posts = ClassBoardPost.query.filter(
            ClassBoardPost.course_id == course.course_id,
            ClassBoardPost.title.like('%[테스트]%')
        ).all()
        for post in existing_posts:
            db.session.delete(post)
        db.session.commit()
        print(f"[OK] 기존 테스트 게시글 {len(existing_posts)}개 삭제")

        # 테스트 게시글 생성
        posts_data = [
            {
                'author': teacher,
                'title': '[테스트] 첫 수업 안내',
                'content': '안녕하세요! 첫 수업 안내드립니다.\n\n수업 준비물:\n- 교재\n- 필기도구\n- 노트북 (선택)',
                'post_type': 'notice',
                'is_pinned': True,
                'is_notice': True
            },
            {
                'author': teacher,
                'title': '[테스트] 다음 주 숙제 안내',
                'content': '다음 주까지 다음 과제를 완료해 주세요:\n\n1. Chapter 3 읽기\n2. 연습문제 풀기\n3. 에세이 작성',
                'post_type': 'notice',
                'is_pinned': True,
                'is_notice': False
            }
        ]

        # 학생 게시글 추가
        for i, enrollment in enumerate(enrollments[:3]):  # 처음 3명만
            student = enrollment.student
            posts_data.append({
                'author': student.user if hasattr(student, 'user') else User.query.filter_by(email=student.email).first(),
                'title': f'[테스트] 질문있어요 - {student.name}',
                'content': f'안녕하세요, {student.name}입니다.\n\n수업 중에 궁금한 점이 있는데요,\n설명 부탁드립니다!',
                'post_type': 'question',
                'is_pinned': False,
                'is_notice': False
            })

        created_count = 0
        for data in posts_data:
            if data['author']:
                post = ClassBoardPost(
                    course_id=course.course_id,
                    author_id=data['author'].user_id,
                    title=data['title'],
                    content=data['content'],
                    post_type=data['post_type'],
                    is_pinned=data['is_pinned'],
                    is_notice=data['is_notice']
                )
                db.session.add(post)
                db.session.flush()

                # 첫 번째 게시글에 댓글 추가
                if created_count == 0:
                    # 학생 댓글
                    for enrollment in enrollments[:2]:
                        student = enrollment.student
                        student_user = User.query.filter_by(email=student.email).first()
                        if student_user:
                            comment = ClassBoardComment(
                                post_id=post.post_id,
                                author_id=student_user.user_id,
                                content=f'{student.name}입니다. 잘 알겠습니다!'
                            )
                            db.session.add(comment)
                            post.comment_count += 1

                    # 강사 댓글
                    comment = ClassBoardComment(
                        post_id=post.post_id,
                        author_id=teacher.user_id,
                        content='질문 있으면 언제든지 물어보세요!'
                    )
                    db.session.add(comment)
                    post.comment_count += 1

                created_count += 1

        db.session.commit()
        print(f"[OK] 테스트 게시글 {created_count}개 생성 완료")

        # 생성된 게시글 목록 출력
        print("\n=== 생성된 게시글 목록 ===")
        all_posts = ClassBoardPost.query.filter(
            ClassBoardPost.course_id == course.course_id,
            ClassBoardPost.title.like('%[테스트]%')
        ).all()

        for post in all_posts:
            print(f"\n- {post.title}")
            print(f"  작성자: {post.author.name}")
            print(f"  유형: {post.post_type}")
            print(f"  고정: {'예' if post.is_pinned else '아니오'}")
            print(f"  공지: {'예' if post.is_notice else '아니오'}")
            print(f"  댓글: {post.comment_count}개")

if __name__ == '__main__':
    print("=" * 50)
    print("클래스 게시판 테스트 데이터 생성")
    print("=" * 50)
    create_test_data()
    print("\n[OK] 완료!")
