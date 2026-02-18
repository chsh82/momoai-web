# -*- coding: utf-8 -*-
"""대시보드 라우트"""
from flask import render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func

from app.dashboard import dashboard_bp
from app.models import db, Student, Essay, Post, Book, EssayBook


@dashboard_bp.route('/')
@login_required
def index():
    """대시보드 메인"""
    user_id = current_user.user_id

    # 통계 계산
    # 1. 총 첨삭 수
    total_essays = Essay.query.filter_by(user_id=user_id).count()

    # 2. 진행 중인 첨삭 (processing, reviewing)
    in_progress_essays = Essay.query.filter_by(user_id=user_id)\
        .filter(Essay.status.in_(['processing', 'reviewing'])).count()

    # 3. 이번 달 첨삭 수
    now = datetime.utcnow()
    first_day_of_month = datetime(now.year, now.month, 1)
    this_month_essays = Essay.query.filter_by(user_id=user_id)\
        .filter(Essay.created_at >= first_day_of_month).count()

    # 4. 완료된 첨삭 수
    completed_essays = Essay.query.filter_by(user_id=user_id)\
        .filter_by(is_finalized=True).count()

    # 5. 총 학생 수
    total_students = Student.query.filter_by(teacher_id=user_id).count()

    # 진행 중인 첨삭 목록 (최신 5개)
    processing_list = Essay.query.filter_by(user_id=user_id)\
        .filter(Essay.status.in_(['processing', 'reviewing']))\
        .order_by(Essay.created_at.desc())\
        .limit(5).all()

    # 최근 완료된 첨삭 목록 (최신 5개)
    recent_completed = Essay.query.filter_by(user_id=user_id)\
        .filter(Essay.status.in_(['completed', 'reviewing']))\
        .order_by(Essay.completed_at.desc())\
        .limit(5).all()

    # 학생별 첨삭 수 (상위 5명)
    top_students = db.session.query(
        Student.student_id,
        Student.name,
        Student.grade,
        func.count(Essay.essay_id).label('essay_count')
    ).join(Essay, Essay.student_id == Student.student_id)\
     .filter(Student.teacher_id == user_id)\
     .group_by(Student.student_id)\
     .order_by(func.count(Essay.essay_id).desc())\
     .limit(5).all()

    # 최근 7일 첨삭 통계
    seven_days_ago = now - timedelta(days=7)
    recent_essays = Essay.query.filter_by(user_id=user_id)\
        .filter(Essay.created_at >= seven_days_ago).count()

    # Phase 2: 차트 데이터 수집
    from app.models import EssayResult, EssayScore
    import calendar

    # 1. 월별 첨삭 수 (최근 6개월)
    monthly_data = {
        'labels': [],
        'counts': [],
        'has_data': False
    }

    for i in range(5, -1, -1):  # 6개월 전부터 현재까지
        # i개월 전 계산
        year = now.year
        month = now.month - i

        while month <= 0:
            month += 12
            year -= 1

        month_start = datetime(year, month, 1)

        # 다음 달 1일 계산
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        month_end = datetime(next_year, next_month, 1)

        count = Essay.query.filter_by(user_id=user_id)\
            .filter(Essay.created_at >= month_start)\
            .filter(Essay.created_at < month_end).count()

        monthly_data['labels'].append(month_start.strftime('%Y-%m'))
        monthly_data['counts'].append(count)
        if count > 0:
            monthly_data['has_data'] = True

    # 2. 평균 점수 추이 (최근 10개 완료된 첨삭)
    score_trend_data = {
        'labels': [],
        'scores': [],
        'has_data': False
    }

    recent_results = db.session.query(Essay, EssayResult)\
        .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
        .filter(Essay.user_id == user_id)\
        .filter(EssayResult.total_score.isnot(None))\
        .order_by(Essay.completed_at.desc())\
        .limit(10).all()

    for essay, result in reversed(recent_results):  # 오래된 것부터
        label = essay.student.name[:4] + f" v{essay.current_version}"
        score_trend_data['labels'].append(label)
        score_trend_data['scores'].append(float(result.total_score))
        score_trend_data['has_data'] = True

    # 3. 학생별 평균 점수 (Top 5)
    student_avg_data = {
        'labels': [],
        'scores': [],
        'has_data': False
    }

    student_averages = db.session.query(
        Student.name,
        func.avg(EssayResult.total_score).label('avg_score')
    ).join(Essay, Essay.student_id == Student.student_id)\
     .join(EssayResult, EssayResult.essay_id == Essay.essay_id)\
     .filter(Student.teacher_id == user_id)\
     .filter(EssayResult.total_score.isnot(None))\
     .group_by(Student.student_id)\
     .order_by(func.avg(EssayResult.total_score).desc())\
     .limit(5).all()

    for student_name, avg_score in student_averages:
        student_avg_data['labels'].append(student_name)
        student_avg_data['scores'].append(float(avg_score))
        student_avg_data['has_data'] = True

    # 4. 18개 지표 전체 평균 (레이더 차트)
    radar_avg_data = {
        'thinking_types': {},
        'integrated_indicators': {},
        'has_data': False
    }

    all_scores = db.session.query(
        EssayScore.category,
        EssayScore.indicator_name,
        func.avg(EssayScore.score).label('avg_score')
    ).join(Essay, Essay.essay_id == EssayScore.essay_id)\
     .filter(Essay.user_id == user_id)\
     .group_by(EssayScore.category, EssayScore.indicator_name).all()

    for category, indicator, avg_score in all_scores:
        if category == '사고유형':
            radar_avg_data['thinking_types'][indicator] = float(avg_score)
        elif category == '통합지표':
            radar_avg_data['integrated_indicators'][indicator] = float(avg_score)
        radar_avg_data['has_data'] = True

    # Phase 3: 커뮤니티 및 도서 통계
    # 커뮤니티 통계
    total_posts = Post.query.filter_by(user_id=user_id).count()
    recent_posts = Post.query.filter_by(user_id=user_id)\
        .order_by(Post.created_at.desc())\
        .limit(5).all()

    # 인기 게시글 (좋아요 기준, 최근 30일)
    thirty_days_ago = now - timedelta(days=30)
    popular_posts = Post.query.filter_by(user_id=user_id)\
        .filter(Post.created_at >= thirty_days_ago)\
        .order_by(Post.likes_count.desc())\
        .limit(3).all()

    # 도서 통계
    total_books = Book.query.filter_by(user_id=user_id).count()
    recent_books = Book.query.filter_by(user_id=user_id)\
        .order_by(Book.created_at.desc())\
        .limit(5).all()

    # 많이 참고된 도서 (Top 5)
    most_referenced_books = db.session.query(
        Book.book_id,
        Book.title,
        Book.author,
        Book.cover_image_url,
        func.count(EssayBook.essay_id).label('reference_count')
    ).join(EssayBook, EssayBook.book_id == Book.book_id)\
     .filter(Book.user_id == user_id)\
     .group_by(Book.book_id)\
     .order_by(func.count(EssayBook.essay_id).desc())\
     .limit(5).all()

    return render_template('dashboard/index.html',
                         total_essays=total_essays,
                         in_progress_essays=in_progress_essays,
                         this_month_essays=this_month_essays,
                         completed_essays=completed_essays,
                         total_students=total_students,
                         processing_list=processing_list,
                         recent_completed=recent_completed,
                         top_students=top_students,
                         recent_essays=recent_essays,
                         monthly_data=monthly_data,
                         score_trend_data=score_trend_data,
                         student_avg_data=student_avg_data,
                         radar_avg_data=radar_avg_data,
                         total_posts=total_posts,
                         recent_posts=recent_posts,
                         popular_posts=popular_posts,
                         total_books=total_books,
                         recent_books=recent_books,
                         most_referenced_books=most_referenced_books)
