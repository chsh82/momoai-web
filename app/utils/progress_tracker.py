# -*- coding: utf-8 -*-
"""학습 진도 추적 유틸리티"""
from datetime import datetime, timedelta
from sqlalchemy import func
from app.models import db, Student, Course, CourseEnrollment, Attendance
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.essay import Essay


class ProgressTracker:
    """학생 학습 진도 추적 클래스"""

    def __init__(self, student_id):
        self.student = Student.query.get_or_404(student_id)
        self.student_id = student_id

    def get_overall_progress(self):
        """전체 학습 진도율 (출석 1/3 + 과제 1/3 + 첨삭 1/3)"""
        from datetime import date
        # 수강 중인 수업들
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.student_id,
            status='active'
        ).all()

        if not enrollments:
            return {
                'total_progress': 0,
                'courses_count': 0,
                'avg_attendance_rate': 0,
                'avg_assignment_completion': 0,
                'essay_completion_rate': 0,
                'essay_weeks': 0,
                'total_weeks': 0,
            }

        # ── 출석률 (수강 수업 평균) ──────────────────────────────
        avg_attendance_rate = round(
            sum(e.attendance_rate for e in enrollments) / len(enrollments), 1
        )

        # ── 과제 완료율 (과제 없으면 100%) ──────────────────────
        course_ids = [e.course_id for e in enrollments]
        assignments = Assignment.query.filter(
            Assignment.course_id.in_(course_ids),
            Assignment.is_published == True
        ).all()

        if not assignments:
            assignment_completion = 100.0
        else:
            completed_assignments = sum(
                1 for a in assignments
                if (lambda s: s and s.is_submitted)(a.get_submission_by_student(self.student_id))
            )
            assignment_completion = round(completed_assignments / len(assignments) * 100, 1)

        # ── 첨삭 완료율 (주당 1회만 인정) ───────────────────────
        # 가장 이른 수강 시작일 기준 총 주수 계산
        earliest_date = min(
            (e.enrolled_at.date() if hasattr(e.enrolled_at, 'date') else e.enrolled_at)
            for e in enrollments
        )
        today = date.today()
        total_weeks = max(1, ((today - earliest_date).days // 7) + 1)

        # 주차별로 에세이 제출 여부 (주당 1회만 인정)
        essays = Essay.query.filter_by(student_id=self.student_id).all()
        weeks_with_essay = set()
        for essay in essays:
            if essay.created_at:
                essay_date = essay.created_at.date() if hasattr(essay.created_at, 'date') else essay.created_at
                # ISO year-week 기준
                weeks_with_essay.add(essay_date.isocalendar()[:2])  # (year, week)

        essay_weeks = len(weeks_with_essay)
        essay_completion_rate = round(min(essay_weeks / total_weeks * 100, 100), 1)

        # ── 전체 진도율 (각 1/3) ─────────────────────────────────
        total_progress = round(
            (avg_attendance_rate + assignment_completion + essay_completion_rate) / 3,
            1
        )

        return {
            'total_progress': total_progress,
            'courses_count': len(enrollments),
            'avg_attendance_rate': avg_attendance_rate,
            'avg_assignment_completion': assignment_completion,
            'essay_completion_rate': essay_completion_rate,
            'essay_weeks': essay_weeks,
            'total_weeks': total_weeks,
        }

    def get_course_progress(self):
        """수업별 진도율"""
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.student_id,
            status='active'
        ).join(Course, CourseEnrollment.course_id == Course.course_id).filter(
            Course.is_terminated == False
        ).all()

        course_progress = []
        for enrollment in enrollments:
            course = enrollment.course

            # 수업 완료율 (세션 기준)
            session_completion = 0
            if course.total_sessions > 0:
                session_completion = round(
                    course.completed_sessions / course.total_sessions * 100,
                    1
                )

            # 과제 완료율
            course_assignments = Assignment.query.filter_by(
                course_id=course.course_id,
                is_published=True
            ).all()

            completed_count = 0
            for assignment in course_assignments:
                submission = assignment.get_submission_by_student(self.student_id)
                if submission and submission.is_submitted:
                    completed_count += 1

            if not course_assignments:
                assignment_completion = 100.0
            else:
                assignment_completion = round(
                    completed_count / len(course_assignments) * 100,
                    1
                )

            course_progress.append({
                'course': course,
                'enrollment': enrollment,
                'session_completion': session_completion,
                'attendance_rate': enrollment.attendance_rate,
                'assignment_completion': assignment_completion,
                'total_assignments': len(course_assignments),
                'completed_assignments': completed_count
            })

        return course_progress

    def get_weekly_activity(self, weeks=4):
        """주간 활동 현황 (최근 N주)"""
        today = datetime.utcnow().date()
        start_date = today - timedelta(days=weeks * 7)

        # 주별 출석 수 — 실제 수업일(session_date) 기준
        from app.models.course import CourseSession
        attendances = db.session.query(
            func.strftime('%Y-%W', CourseSession.session_date).label('week'),
            func.count(Attendance.attendance_id).label('count')
        ).join(CourseSession, Attendance.session_id == CourseSession.session_id).filter(
            Attendance.student_id == self.student_id,
            CourseSession.session_date >= start_date,
            Attendance.status.in_(['present', 'late'])
        ).group_by('week').order_by('week').all()

        # 주별 과제 제출 수 (SQLite 호환)
        submissions = db.session.query(
            func.strftime('%Y-%W', AssignmentSubmission.submitted_at).label('week'),
            func.count(AssignmentSubmission.submission_id).label('count')
        ).filter(
            AssignmentSubmission.student_id == self.student_id,
            AssignmentSubmission.submitted_at >= start_date,
            AssignmentSubmission.status.in_(['submitted', 'graded'])
        ).group_by('week').order_by('week').all()

        # 주별 첨삭 수 (SQLite 호환)
        essays = db.session.query(
            func.strftime('%Y-%W', Essay.created_at).label('week'),
            func.count(Essay.essay_id).label('count')
        ).filter(
            Essay.student_id == self.student_id,
            Essay.created_at >= start_date
        ).group_by('week').order_by('week').all()

        # 데이터 병합
        weekly_data = {}
        for attendance in attendances:
            week_str = attendance.week  # 이미 문자열 형식
            weekly_data[week_str] = {'attendance': attendance.count, 'assignments': 0, 'essays': 0}

        for submission in submissions:
            week_str = submission.week  # 이미 문자열 형식
            if week_str not in weekly_data:
                weekly_data[week_str] = {'attendance': 0, 'assignments': 0, 'essays': 0}
            weekly_data[week_str]['assignments'] = submission.count

        for essay in essays:
            week_str = essay.week  # 이미 문자열 형식
            if week_str not in weekly_data:
                weekly_data[week_str] = {'attendance': 0, 'assignments': 0, 'essays': 0}
            weekly_data[week_str]['essays'] = essay.count

        return weekly_data

    def get_essay_status(self):
        """첨삭 현황"""
        essays = Essay.query.filter_by(
            student_id=self.student_id
        ).order_by(Essay.created_at.desc()).all()

        status_counts = {
            'total': len(essays),
            'finalized': sum(1 for e in essays if e.is_finalized),
            'in_progress': sum(1 for e in essays if not e.is_finalized and e.status in ('processing', 'reviewing', 'completed')),
            'draft': sum(1 for e in essays if not e.is_finalized and e.status == 'draft'),
        }

        essay_list = []
        for essay in essays[:5]:
            if essay.is_finalized:
                status = 'finalized'
            elif essay.status in ('processing', 'reviewing'):
                status = 'in_progress'
            elif essay.status == 'completed':
                status = 'completed'
            else:
                status = 'draft'

            score = None
            if essay.result and essay.result.total_score is not None:
                score = float(essay.result.total_score)

            essay_list.append({
                'essay': essay,
                'status': status,
                'score': score,
            })

        return {
            'status_counts': status_counts,
            'essays': essay_list,
        }

    def get_assignment_status(self):
        """과제 현황"""
        # 수강 중인 수업들의 과제
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.student_id,
            status='active'
        ).all()
        course_ids = [e.course_id for e in enrollments]

        assignments = Assignment.query.filter(
            Assignment.course_id.in_(course_ids),
            Assignment.is_published == True
        ).order_by(Assignment.due_date.asc()).all()

        status_counts = {
            'total': len(assignments),
            'completed': 0,
            'graded': 0,
            'pending': 0,
            'overdue': 0
        }

        assignment_list = []
        for assignment in assignments:
            submission = assignment.get_submission_by_student(self.student_id)

            if submission and submission.is_graded:
                status = 'graded'
                status_counts['graded'] += 1
                status_counts['completed'] += 1
            elif submission and submission.is_submitted:
                status = 'submitted'
                status_counts['completed'] += 1
            elif assignment.is_overdue:
                status = 'overdue'
                status_counts['overdue'] += 1
            else:
                status = 'pending'
                status_counts['pending'] += 1

            assignment_list.append({
                'assignment': assignment,
                'submission': submission,
                'status': status
            })

        return {
            'status_counts': status_counts,
            'assignments': assignment_list
        }

    def get_performance_summary(self):
        """학습 성과 요약"""
        # 최근 첨삭 평균 점수 (완료된 첨삭의 total_score 기준)
        recent_essays = Essay.query.filter_by(
            student_id=self.student_id,
            is_finalized=True
        ).order_by(Essay.created_at.desc()).limit(10).all()

        avg_essay_score = None  # None = 완료된 첨삭 없음
        if recent_essays:
            scores = [
                float(e.result.total_score)
                for e in recent_essays
                if e.result and e.result.total_score is not None
            ]
            if scores:
                avg_essay_score = round(sum(scores) / len(scores), 1)

        return {
            'avg_essay_score': avg_essay_score,  # None이면 데이터 없음
            'completed_essays_count': len(recent_essays)
        }
