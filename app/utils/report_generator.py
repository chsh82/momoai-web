# -*- coding: utf-8 -*-
"""학생 리포트 생성 유틸리티"""
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from app.models import db, Student, CourseEnrollment, Attendance
from app.models.essay import Essay, EssayVersion


class ReportGenerator:
    """학생 리포트 생성 클래스"""

    def __init__(self, student_id, start_date=None, end_date=None):
        """
        Args:
            student_id: 학생 ID
            start_date: 리포트 시작일 (None이면 최근 30일)
            end_date: 리포트 종료일 (None이면 오늘)
        """
        self.student = Student.query.get_or_404(student_id)
        self.end_date = end_date or datetime.utcnow()
        self.start_date = start_date or (self.end_date - timedelta(days=30))

    def generate_report(self):
        """전체 리포트 데이터 생성"""
        return {
            'student': self.student,
            'period': {
                'start': self.start_date,
                'end': self.end_date,
                'days': (self.end_date - self.start_date).days
            },
            'essays': self._get_essay_statistics(),
            'attendance': self._get_attendance_statistics(),
            'scores': self._get_score_analysis(),
            'progress': self._get_progress_analysis(),
            'comparison': self._get_peer_comparison(),
            'summary': self._generate_summary()
        }

    def _get_essay_statistics(self):
        """첨삭 통계"""
        essays = Essay.query.filter(
            Essay.student_id == self.student.student_id,
            Essay.created_at >= self.start_date,
            Essay.created_at <= self.end_date
        ).all()

        completed_essays = [e for e in essays if e.status == 'completed']

        # 평균 점수 계산
        total_score = 0
        score_count = 0

        for essay in completed_essays:
            latest_version = EssayVersion.query.filter_by(
                essay_id=essay.essay_id
            ).order_by(EssayVersion.version_number.desc()).first()

            if latest_version and latest_version.total_score:
                total_score += latest_version.total_score
                score_count += 1

        avg_score = (total_score / score_count) if score_count > 0 else 0

        return {
            'total': len(essays),
            'completed': len(completed_essays),
            'in_progress': len([e for e in essays if e.status in ['processing', 'reviewing']]),
            'avg_score': round(avg_score, 1),
            'essays': completed_essays
        }

    def _get_attendance_statistics(self):
        """출석 통계"""
        # 학생의 모든 수강 신청
        enrollments = CourseEnrollment.query.filter_by(
            student_id=self.student.student_id
        ).all()

        total_sessions = 0
        attended = 0
        absent = 0
        late = 0

        for enrollment in enrollments:
            attendances = Attendance.query.filter(
                Attendance.enrollment_id == enrollment.enrollment_id,
                Attendance.session_date >= self.start_date,
                Attendance.session_date <= self.end_date
            ).all()

            for att in attendances:
                total_sessions += 1
                if att.status == 'present':
                    attended += 1
                elif att.status == 'absent':
                    absent += 1
                elif att.status == 'late':
                    late += 1

        attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 0

        return {
            'total_sessions': total_sessions,
            'attended': attended,
            'absent': absent,
            'late': late,
            'attendance_rate': round(attendance_rate, 1)
        }

    def _get_score_analysis(self):
        """지표별 점수 분석"""
        essays = Essay.query.filter(
            Essay.student_id == self.student.student_id,
            Essay.created_at >= self.start_date,
            Essay.created_at <= self.end_date,
            Essay.status == 'completed'
        ).all()

        if not essays:
            return None

        # 18개 지표 점수 집계
        indicator_scores = {}
        indicator_counts = {}

        for essay in essays:
            latest_version = EssayVersion.query.filter_by(
                essay_id=essay.essay_id
            ).order_by(EssayVersion.version_number.desc()).first()

            if latest_version and latest_version.scores_json:
                import json
                try:
                    scores = json.loads(latest_version.scores_json)
                    for indicator, score in scores.items():
                        if indicator not in indicator_scores:
                            indicator_scores[indicator] = 0
                            indicator_counts[indicator] = 0
                        indicator_scores[indicator] += score
                        indicator_counts[indicator] += 1
                except:
                    pass

        # 평균 계산
        avg_scores = {}
        for indicator in indicator_scores:
            avg_scores[indicator] = round(
                indicator_scores[indicator] / indicator_counts[indicator], 1
            )

        # 강점/약점 식별
        sorted_scores = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

        return {
            'avg_scores': avg_scores,
            'strengths': sorted_scores[:3] if len(sorted_scores) >= 3 else sorted_scores,
            'weaknesses': sorted_scores[-3:] if len(sorted_scores) >= 3 else []
        }

    def _get_progress_analysis(self):
        """진도 분석 (점수 추이)"""
        essays = Essay.query.filter(
            Essay.student_id == self.student.student_id,
            Essay.created_at >= self.start_date,
            Essay.created_at <= self.end_date,
            Essay.status == 'completed'
        ).order_by(Essay.created_at.asc()).all()

        scores_timeline = []
        for essay in essays:
            latest_version = EssayVersion.query.filter_by(
                essay_id=essay.essay_id
            ).order_by(EssayVersion.version_number.desc()).first()

            if latest_version and latest_version.total_score:
                scores_timeline.append({
                    'date': essay.created_at.strftime('%Y-%m-%d'),
                    'score': latest_version.total_score,
                    'title': essay.title
                })

        # 성장률 계산
        growth_rate = 0
        if len(scores_timeline) >= 2:
            first_score = scores_timeline[0]['score']
            last_score = scores_timeline[-1]['score']
            growth_rate = ((last_score - first_score) / first_score * 100) if first_score > 0 else 0

        return {
            'timeline': scores_timeline,
            'growth_rate': round(growth_rate, 1)
        }

    def _get_peer_comparison(self):
        """동급생 평균과 비교"""
        # 같은 학년 학생들의 평균 점수
        same_grade_students = Student.query.filter_by(grade=self.student.grade).all()
        same_grade_ids = [s.student_id for s in same_grade_students]

        if not same_grade_ids:
            return None

        # 같은 학년 학생들의 평균 점수 계산
        peer_essays = Essay.query.filter(
            Essay.student_id.in_(same_grade_ids),
            Essay.created_at >= self.start_date,
            Essay.created_at <= self.end_date,
            Essay.status == 'completed'
        ).all()

        peer_total_score = 0
        peer_count = 0

        for essay in peer_essays:
            latest_version = EssayVersion.query.filter_by(
                essay_id=essay.essay_id
            ).order_by(EssayVersion.version_number.desc()).first()

            if latest_version and latest_version.total_score:
                peer_total_score += latest_version.total_score
                peer_count += 1

        peer_avg = (peer_total_score / peer_count) if peer_count > 0 else 0

        # 내 평균
        my_avg = self._get_essay_statistics()['avg_score']

        return {
            'peer_avg': round(peer_avg, 1),
            'my_avg': my_avg,
            'difference': round(my_avg - peer_avg, 1)
        }

    def _generate_summary(self):
        """종합 요약"""
        essay_stats = self._get_essay_statistics()
        attendance_stats = self._get_attendance_statistics()
        score_analysis = self._get_score_analysis()
        progress = self._get_progress_analysis()

        # 자동 코멘트 생성
        comments = []

        # 출석률 코멘트
        if attendance_stats['attendance_rate'] >= 90:
            comments.append("출석률이 매우 우수합니다.")
        elif attendance_stats['attendance_rate'] >= 80:
            comments.append("출석률이 양호합니다.")
        else:
            comments.append("출석률을 개선할 필요가 있습니다.")

        # 첨삭 완료 코멘트
        if essay_stats['completed'] >= 5:
            comments.append("활발하게 첨삭을 완료하고 있습니다.")
        elif essay_stats['completed'] >= 3:
            comments.append("꾸준히 첨삭을 진행하고 있습니다.")
        else:
            comments.append("과제 제출 횟수를 늘릴 필요가 있습니다.")

        # 점수 추이 코멘트
        if progress['growth_rate'] > 10:
            comments.append("점수가 크게 향상되었습니다.")
        elif progress['growth_rate'] > 0:
            comments.append("점수가 조금씩 향상되고 있습니다.")
        elif progress['growth_rate'] < -10:
            comments.append("점수가 하락하는 추세입니다. 주의가 필요합니다.")

        return {
            'comments': comments,
            'overall_grade': self._calculate_overall_grade(essay_stats, attendance_stats)
        }

    def _calculate_overall_grade(self, essay_stats, attendance_stats):
        """종합 등급 계산"""
        score = essay_stats['avg_score']
        attendance = attendance_stats['attendance_rate']

        # 평균 점수 + 출석률로 종합 평가
        combined = (score + attendance) / 2

        if combined >= 90:
            return 'A+'
        elif combined >= 85:
            return 'A'
        elif combined >= 80:
            return 'B+'
        elif combined >= 75:
            return 'B'
        elif combined >= 70:
            return 'C+'
        elif combined >= 65:
            return 'C'
        else:
            return 'D'
