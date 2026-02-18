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
        """전체 학습 진도율"""
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
                'total_essays': 0
            }

        # 평균 출석률
        total_attendance_rate = sum(e.attendance_rate for e in enrollments)
        avg_attendance_rate = round(total_attendance_rate / len(enrollments), 1)

        # 과제 완료율
        course_ids = [e.course_id for e in enrollments]
        assignments = Assignment.query.filter(
            Assignment.course_id.in_(course_ids),
            Assignment.is_published == True
        ).all()

        completed_assignments = 0
        for assignment in assignments:
            submission = assignment.get_submission_by_student(self.student_id)
            if submission and submission.is_submitted:
                completed_assignments += 1

        assignment_completion = 0
        if assignments:
            assignment_completion = round(completed_assignments / len(assignments) * 100, 1)

        # 첨삭 수
        total_essays = Essay.query.filter_by(student_id=self.student_id).count()

        # 전체 진도율 (출석률 40% + 과제완료율 40% + 첨삭활동 20%)
        essay_score = min(total_essays * 5, 100)  # 첨삭 1개당 5점, 최대 100점
        total_progress = round(
            avg_attendance_rate * 0.4 +
            assignment_completion * 0.4 +
            essay_score * 0.2,
            1
        )

        return {
            'total_progress': total_progress,
            'courses_count': len(enrollments),
            'avg_attendance_rate': avg_attendance_rate,
            'avg_assignment_completion': assignment_completion,
            'total_essays': total_essays
        }

    def get_course_progress(self):
        """수업별 진도율"""
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.student_id,
            status='active'
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

            assignment_completion = 0
            if course_assignments:
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

        # 주별 출석 수 (SQLite 호환)
        attendances = db.session.query(
            func.strftime('%Y-%W', Attendance.created_at).label('week'),
            func.count(Attendance.attendance_id).label('count')
        ).join(CourseEnrollment).filter(
            CourseEnrollment.student_id == self.student_id,
            Attendance.created_at >= start_date,
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
        # 평균 과제 점수
        submissions = AssignmentSubmission.query.filter_by(
            student_id=self.student_id,
            status='graded'
        ).all()

        avg_score = 0
        if submissions:
            total_score = sum(s.score for s in submissions if s.score)
            total_max_score = sum(s.assignment.max_score for s in submissions)
            if total_max_score > 0:
                avg_score = round(total_score / total_max_score * 100, 1)

        # 최근 첨삭 평균 점수
        recent_essays = Essay.query.filter_by(
            student_id=self.student_id,
            is_finalized=True
        ).order_by(Essay.created_at.desc()).limit(10).all()

        avg_essay_score = 0
        if recent_essays:
            # Essay 모델에 score 필드가 있다고 가정
            scores = [e.final_score for e in recent_essays if hasattr(e, 'final_score') and e.final_score]
            if scores:
                avg_essay_score = round(sum(scores) / len(scores), 1)

        return {
            'avg_assignment_score': avg_score,
            'graded_assignments_count': len(submissions),
            'avg_essay_score': avg_essay_score,
            'completed_essays_count': len(recent_essays)
        }
