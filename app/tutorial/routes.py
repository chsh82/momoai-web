# -*- coding: utf-8 -*-
"""글쓰기 튜토리얼 라우트.

레슨 열람(GET)은 비로그인도 허용한다 - 이 프로젝트는 aprolabs와 달리 전역
"미로그인 리다이렉트" 미들웨어가 없고 라우트별 @login_required만 쓰므로,
그냥 데코레이터를 안 붙이면 자연스럽게 공개된다. 저장 API(POST)만 로그인을
요구하고, JSON 응답이어야 하므로 @login_required(302 리다이렉트) 대신
feedback_bp와 동일하게 수동으로 current_user.is_authenticated를 확인해
401 JSON을 반환한다.

2단계(트랙/코스 확장)부터 URL의 track/course를 그대로 content.py에 넘긴다 -
TutorialProgress 등 모델은 처음부터 track/course 컬럼을 갖고 있었으므로
스키마 변경 없이 라우트만 파라미터화하면 된다. 중등(middle) 등 콘텐츠
파일이 없는 트랙은 content.get_course()가 None을 반환하니 그대로 404 처리.
"""
from datetime import datetime

from flask import render_template, request, jsonify, current_app, abort
from flask_login import current_user

from app.tutorial import tutorial_bp
from app.tutorial import content
from app.tutorial.models import TutorialProgress, TutorialAttempt, TutorialCourseReward
from app.models import db
from app.models.student import Student

# 실제 콘텐츠가 있는 트랙만 화이트리스트로 관리한다 - URL의 track을 그대로
# content.get_course()에 넘기면 임의 문자열로 파일시스템 경로를 조립하게
# 되므로, 라우트 단계에서 먼저 걸러낸다.
SUPPORTED_TRACKS = {'elem'}
TRACK_COURSES = {
    'elem': ['course1', 'course2', 'course3'],
}


@tutorial_bp.route('/')
def track_select():
    """트랙(초등/중등) 선택 화면."""
    return render_template('tutorial/track_select.html')


@tutorial_bp.route('/<track>/')
def index(track):
    """코스 목록 - 해당 트랙의 코스 카드 + 코스별 진도."""
    if track not in SUPPORTED_TRACKS:
        abort(404)

    courses = []
    for course_code in TRACK_COURSES[track]:
        course_data = content.get_course(track, course_code)
        lesson_ids = content.get_lesson_ids(track, course_code)
        total_lessons = len(lesson_ids)

        done_count = 0
        if current_user.is_authenticated and total_lessons:
            done_count = TutorialProgress.query.filter_by(
                user_id=current_user.user_id, track=track, course=course_code, status='done',
            ).count()

        courses.append({
            'code': course_code,
            'data': course_data,
            'total_lessons': total_lessons,
            'done_count': done_count,
            'first_lesson_id': lesson_ids[0] if lesson_ids else None,
        })

    # 관리자는 순서(잠금)와 상관없이 모든 코스를 열어볼 수 있어야 콘텐츠 점검이
    # 편하다 - 학생 진도 게이트는 화면 표시만 우회하고, 저장 대상 여부(api_complete의
    # role 체크)는 그대로 둔다(관리자 진도는 계속 저장 안 됨, 열람만 허용).
    bypass_gate = current_user.is_authenticated and current_user.role == 'admin'

    return render_template('tutorial/home.html', track=track, courses=courses, bypass_gate=bypass_gate)


@tutorial_bp.route('/<track>/<course_code>/<lesson_id>')
def lesson(track, course_code, lesson_id):
    """레슨 화면 - 학습(#learn) + 퀴즈(#quiz-screen) + 결과(#result) 세 화면을 한 템플릿에 담는다."""
    if track not in SUPPORTED_TRACKS or course_code not in TRACK_COURSES[track]:
        abort(404)

    lesson_data = content.get_lesson(track, course_code, lesson_id)
    if lesson_data is None:
        return render_template('tutorial/home.html', track=track, courses=[],
                              error='레슨을 찾을 수 없습니다.'), 404

    course = content.get_course(track, course_code)
    return render_template(
        'tutorial/lesson.html',
        lesson=lesson_data,
        course_title=course.get('title') if course else '',
        track=track, course_code=course_code,
    )


@tutorial_bp.route('/api/answer', methods=['POST'])
def api_answer():
    """문항 1개 응답 기록 (best-effort - 저장 실패해도 화면 진행은 프런트에서 안 막음)."""
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role != 'student':
        # 학부모/교사/관리자 등은 진도 저장 대상이 아니다 - 오류가 아니라 조용히 무시.
        return '', 204

    data = request.get_json(silent=True) or {}
    lesson_id = data.get('lesson_id')
    question_id = data.get('question_id')
    correct = data.get('correct')
    rule_no = data.get('rule_no')

    if not lesson_id or not question_id or correct is None:
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400

    try:
        attempt = TutorialAttempt(
            user_id=current_user.user_id,
            lesson_id=lesson_id,
            question_id=question_id,
            rule_no=rule_no,
            correct=bool(correct),
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            '[tutorial.api_answer] 저장 실패 (user_id=%s, question_id=%s)',
            current_user.user_id, question_id)
        return jsonify({'error': '저장에 실패했습니다'}), 500

    return jsonify({'saved': True})


def _resolve_student():
    """current_user(User)로 명부(Student) 레코드를 찾는다. 없으면 None(정상 상황 - 오류 아님)."""
    return Student.query.filter_by(user_id=current_user.user_id).first()


def _award_course_completion(student, track, course):
    """코스 완료 보상을 별도 트랜잭션으로 지급한다.

    호출 시점에는 이미 코스 전체 레슨이 done임이 확인된 상태다. 여기서는
    (student_id, track, course) 중복 여부와 실제 지급만 처리한다.
    실패해도 예외를 밖으로 던지지 않는다 - 호출부가 진도 저장을 이미
    커밋했으므로, 여기서 실패해도 다음 완료 시도 때 자연스럽게 재시도된다.

    Returns: 지급한 points(int). 이미 지급됐거나 실패하면 0.
    """
    existing = TutorialCourseReward.query.filter_by(
        student_id=student.student_id, track=track, course=course,
    ).first()
    if existing is not None:
        return 0

    try:
        from app.services.mileage_service import award_points
        source_id = f"{student.student_id}-{track}-{course}"
        event = award_points(
            student_id=student.student_id, activity_code='TU01',
            source_type='tutorial_course', source_id=source_id,
        )
        if event is None:
            # 상한 초과 등으로 award_points가 조용히 거부한 경우 - reward 행을 만들지 않는다
            # (지급이 안 됐는데 "받았다"는 기록을 남기면 안 되므로).
            return 0

        reward = TutorialCourseReward(
            student_id=student.student_id, track=track, course=course, points=event.points,
        )
        db.session.add(reward)
        db.session.commit()
        return event.points
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            '[tutorial.complete] TU01 마일리지 적립 실패 (student_id=%s, track=%s, course=%s)',
            student.student_id, track, course)
        return 0


@tutorial_bp.route('/api/complete', methods=['POST'])
def api_complete():
    """레슨 완료 처리 + 코스 완료 시 마일리지(TU01) 적립."""
    if not current_user.is_authenticated:
        return jsonify({'error': '로그인이 필요합니다'}), 401
    if current_user.role != 'student':
        # 관리자/교사/학부모 계정으로 튜토리얼을 열어볼 수는 있지만 진도는 저장 대상이
        # 아니다 - 화면에서 "저장 실패"로 오인하지 않도록 skipped 플래그를 명시한다.
        return jsonify({'skipped': True, 'points_awarded': False, 'points': 0})

    data = request.get_json(silent=True) or {}
    lesson_id = data.get('lesson_id')
    score = data.get('score')
    total = data.get('total')
    track = data.get('track')
    course_code = data.get('course')

    if not lesson_id or score is None or total is None:
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400
    if track not in SUPPORTED_TRACKS or course_code not in TRACK_COURSES.get(track, []):
        return jsonify({'error': '요청이 올바르지 않습니다'}), 400

    # 1) 진도 저장 - 먼저 커밋한다(마일리지 적립과 트랜잭션을 분리).
    try:
        progress = TutorialProgress.query.filter_by(
            user_id=current_user.user_id, lesson_id=lesson_id,
        ).first()
        if progress is None:
            progress = TutorialProgress(
                user_id=current_user.user_id, track=track, course=course_code, lesson_id=lesson_id,
            )
            db.session.add(progress)
        progress.status = 'done'
        progress.score = score
        progress.total = total
        progress.done_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            '[tutorial.api_complete] 진도 저장 실패 (user_id=%s, lesson_id=%s)',
            current_user.user_id, lesson_id)
        return jsonify({'error': '저장에 실패했습니다'}), 500

    # 2) 명부(Student) 레코드 확인 - 없으면 정상 상황으로 보고 적립만 건너뛴다.
    student = _resolve_student()
    if student is None:
        current_app.logger.info(
            '[tutorial.api_complete] 명부(Student) 레코드 없음 - 적립 건너뜀 (user_id=%s)',
            current_user.user_id)
        return jsonify({'points_awarded': False, 'points': 0})

    # 3) 코스의 전체 레슨이 done인지 판정 (레슨 수는 콘텐츠 JSON에서 센다 - 하드코딩 금지).
    all_lesson_ids = content.get_lesson_ids(track, course_code)
    done_lesson_ids = {
        p.lesson_id for p in TutorialProgress.query.filter_by(
            user_id=current_user.user_id, track=track, course=course_code, status='done',
        ).all()
    }
    all_lessons_done = bool(all_lesson_ids) and set(all_lesson_ids).issubset(done_lesson_ids)

    points = 0
    if all_lessons_done:
        # 4)+5) 중복 확인 + 적립은 별도 트랜잭션(_award_course_completion 안에서 처리).
        points = _award_course_completion(student, track, course_code)

    # points_awarded는 "코스가 다 끝났다"가 아니라 "이번 호출로 적립이 발생했다"는 뜻이다
    # (이미 지급된 코스를 다시 풀어도 all_lessons_done은 계속 true지만, 그때는 points=0이라
    # 프런트가 마일리지 줄을 또 보여주면 안 되므로 - "코스 완료! +0"처럼 어색해지는 것을 막는다).
    return jsonify({'points_awarded': points > 0, 'points': points})
