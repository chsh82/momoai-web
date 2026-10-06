"""
학생 데이터 교차분석 및 인사이트 생성
"""
from datetime import datetime, timedelta
from sqlalchemy import func


def calculate_attendance_rate(enrollments):
    """출석률 계산"""
    if not enrollments:
        return 0

    total_sessions = 0
    attended_sessions = 0

    for enrollment in enrollments:
        total = enrollment.attended_sessions + enrollment.late_sessions + enrollment.absent_sessions
        total_sessions += total
        attended_sessions += enrollment.attended_sessions + enrollment.late_sessions

    if total_sessions == 0:
        return 0

    return round((attended_sessions / total_sessions) * 100, 1)


def get_recent_attendance_trend(student_id):
    """최근 출석 추이 분석 (최근 2주 vs 전체) — 지각은 출석과 동일 인정,
    출석인정결석·보강처리결석·과거 버그 레코드(unconfirmed)는 분모에서 제외"""
    from app.models.attendance import Attendance
    from app.models.course import CourseSession
    from app import db

    EXCLUDED_STATUSES = ['unconfirmed', 'absent_makeup', 'excused']
    two_weeks_ago = datetime.now() - timedelta(days=14)

    def _rate(attendances):
        total = len(attendances)
        if total == 0:
            return None
        attended = sum(1 for a in attendances if a.status in ('present', 'late'))
        return round((attended / total) * 100, 1)

    # 최근 2주 출석 데이터 (강사가 실제 체크 완료한 세션만)
    recent_attendances = db.session.query(Attendance).join(CourseSession).filter(
        Attendance.student_id == student_id,
        CourseSession.session_date >= two_weeks_ago,
        CourseSession.attendance_checked == True,
        Attendance.status.notin_(EXCLUDED_STATUSES)
    ).all()

    if not recent_attendances:
        return None, None

    recent_rate = _rate(recent_attendances)

    # 전체 출석률
    all_attendances = Attendance.query.join(CourseSession).filter(
        Attendance.student_id == student_id,
        CourseSession.attendance_checked == True,
        Attendance.status.notin_(EXCLUDED_STATUSES)
    ).all()
    all_rate = _rate(all_attendances)

    return recent_rate, all_rate


def analyze_consultation_patterns(consultations):
    """상담 이력 패턴 분석"""
    if not consultations:
        return {
            'total_count': 0,
            'recent_count': 0,
            'categories': {},
            'concerning_keywords': [],
            'last_consultation_days': None
        }

    two_weeks_ago = datetime.now() - timedelta(days=14)
    recent_consultations = [c for c in consultations if c.consultation_date >= two_weeks_ago.date()]

    # 카테고리별 집계
    categories = {}
    for c in consultations:
        cat = c.major_category
        categories[cat] = categories.get(cat, 0) + 1

    # 우려 키워드 감지
    concerning_keywords = []
    concern_words = ['학습고민', '행동문제', '의욕 저하', '집중력', '스트레스', '불안', '진로고민']

    for consultation in consultations[:5]:  # 최근 5개만 체크
        content_lower = consultation.content.lower()
        for keyword in concern_words:
            if keyword in content_lower and keyword not in concerning_keywords:
                concerning_keywords.append(keyword)

    # 마지막 상담 이후 일수
    last_consultation_days = None
    if consultations:
        last_date = consultations[0].consultation_date
        last_consultation_days = (datetime.now().date() - last_date).days

    return {
        'total_count': len(consultations),
        'recent_count': len(recent_consultations),
        'categories': categories,
        'concerning_keywords': concerning_keywords,
        'last_consultation_days': last_consultation_days
    }


def get_mbti_learning_insights(mbti_result, mbti_type):
    """MBTI 기반 학습 인사이트"""
    if not mbti_result or not mbti_type:
        return None

    insights = {
        'strengths': [],
        'challenges': [],
        'recommendations': []
    }

    # 읽기 유형별 인사이트
    read_insights = {
        'vocab': {
            'strength': '어휘력이 뛰어나 정확한 이해 가능',
            'challenge': '반복 학습 없이 지나칠 수 있음',
            'recommendation': '핵심 개념 복습 시간 배정'
        },
        'reread': {
            'strength': '꼼꼼한 재독으로 깊은 이해',
            'challenge': '학습 속도가 느릴 수 있음',
            'recommendation': '충분한 읽기 시간 제공'
        },
        'analyze': {
            'strength': '비판적 사고와 분석력 우수',
            'challenge': '세부 내용 놓칠 수 있음',
            'recommendation': '전체 구조와 세부 균형 지도'
        }
    }

    # 말하기 유형별 인사이트
    speech_insights = {
        'textual': {
            'strength': '텍스트 기반 정확한 답변',
            'challenge': '창의적 확장이 부족할 수 있음',
            'recommendation': '토론 시 자유로운 의견 표현 격려'
        },
        'expand': {
            'strength': '창의적이고 풍부한 표현',
            'challenge': '주제에서 벗어날 수 있음',
            'recommendation': '명확한 구조와 가이드 제공'
        },
        'lead': {
            'strength': '적극적 참여와 리더십',
            'challenge': '독립적 사고 부족 가능',
            'recommendation': '비판적 사고 훈련 필요'
        }
    }

    # 쓰기 유형별 인사이트
    write_insights = {
        'summary': {
            'strength': '핵심 요약 능력 뛰어남',
            'challenge': '논리적 전개 약할 수 있음',
            'recommendation': '논증 구조 훈련 강화'
        },
        'logic': {
            'strength': '논리적 전개와 구조화 우수',
            'challenge': '창의성이 부족할 수 있음',
            'recommendation': '다양한 관점 탐색 격려'
        },
        'rewrite': {
            'strength': '창의적 재구성 능력',
            'challenge': '원문 정확성 떨어질 수 있음',
            'recommendation': '핵심 내용 파악 훈련'
        }
    }

    # 인사이트 수집
    read_type = mbti_result.read_type
    speech_type = mbti_result.speech_type
    write_type = mbti_result.write_type

    if read_type in read_insights:
        insights['strengths'].append(read_insights[read_type]['strength'])
        insights['challenges'].append(read_insights[read_type]['challenge'])
        insights['recommendations'].append(read_insights[read_type]['recommendation'])

    if speech_type in speech_insights:
        insights['strengths'].append(speech_insights[speech_type]['strength'])
        insights['challenges'].append(speech_insights[speech_type]['challenge'])
        insights['recommendations'].append(speech_insights[speech_type]['recommendation'])

    if write_type in write_insights:
        insights['strengths'].append(write_insights[write_type]['strength'])
        insights['challenges'].append(write_insights[write_type]['challenge'])
        insights['recommendations'].append(write_insights[write_type]['recommendation'])

    return insights


def generate_student_insights(student, enrollments, profile, mbti_result, mbti_type, consultations, feedbacks=None):
    """학생 종합 인사이트 생성"""
    insights = {
        'risk_factors': [],      # 위험 요소
        'warning_factors': [],   # 주의 요소
        'strengths': [],         # 강점
        'recommendations': []    # 추천 액션
    }

    # 1. 출석률 분석
    recent_rate, overall_rate = get_recent_attendance_trend(student.student_id)

    if recent_rate is not None and overall_rate is not None:
        if recent_rate < 70:
            insights['risk_factors'].append({
                'category': '출석',
                'severity': 'high',
                'description': f'최근 2주 출석률 {recent_rate}% (전체 평균 {overall_rate}%)',
                'icon': '🔴'
            })
            insights['recommendations'].append({
                'priority': 'high',
                'action': '출석 패턴 개선을 위한 긴급 상담 필요',
                'category': '학습 참여'
            })
        elif recent_rate < overall_rate - 15:
            insights['warning_factors'].append({
                'category': '출석',
                'description': f'최근 출석률 하락 추세 ({overall_rate}% → {recent_rate}%)',
                'icon': '🟡'
            })
            insights['recommendations'].append({
                'priority': 'medium',
                'action': '출석률 하락 원인 파악 면담',
                'category': '학습 참여'
            })
        elif recent_rate >= 90:
            insights['strengths'].append({
                'category': '출석',
                'description': f'우수한 출석률 유지 ({recent_rate}%)',
                'icon': '🟢'
            })

    # 2. 상담 이력 분석
    consultation_analysis = analyze_consultation_patterns(consultations)

    if consultation_analysis['concerning_keywords']:
        insights['warning_factors'].append({
            'category': '상담',
            'description': f"최근 상담에서 '{', '.join(consultation_analysis['concerning_keywords'][:3])}' 언급",
            'icon': '🟡'
        })
        insights['recommendations'].append({
            'priority': 'medium',
            'action': '심층 상담 및 학부모 면담 고려',
            'category': '정서 지원'
        })

    if consultation_analysis['last_consultation_days'] and consultation_analysis['last_consultation_days'] > 90:
        insights['warning_factors'].append({
            'category': '상담',
            'description': f"마지막 상담 이후 {consultation_analysis['last_consultation_days']}일 경과",
            'icon': '🟡'
        })
        insights['recommendations'].append({
            'priority': 'low',
            'action': '정기 상담 일정 수립',
            'category': '학생 관리'
        })

    # 3. MBTI 기반 분석
    if mbti_result and mbti_type:
        mbti_insights = get_mbti_learning_insights(mbti_result, mbti_type)

        if mbti_insights:
            # 강점 추가
            for strength in mbti_insights['strengths'][:2]:
                insights['strengths'].append({
                    'category': 'MBTI 학습 성향',
                    'description': strength,
                    'icon': '🟢'
                })

            # 도전 과제를 주의 요소로
            for challenge in mbti_insights['challenges'][:2]:
                insights['warning_factors'].append({
                    'category': 'MBTI 학습 성향',
                    'description': challenge,
                    'icon': '🟡'
                })

            # 추천사항 추가
            for rec in mbti_insights['recommendations'][:2]:
                insights['recommendations'].append({
                    'priority': 'low',
                    'action': rec,
                    'category': '학습 전략'
                })

    # 4. 프로필 기반 분석
    if profile:
        # 독서 역량
        if profile.reading_competency:
            if profile.reading_competency >= 4:
                insights['strengths'].append({
                    'category': '독서 역량',
                    'description': f'높은 독서 역량 ({profile.reading_competency}/5)',
                    'icon': '🟢'
                })
            elif profile.reading_competency <= 2:
                insights['warning_factors'].append({
                    'category': '독서 역량',
                    'description': f'독서 역량 보강 필요 ({profile.reading_competency}/5)',
                    'icon': '🟡'
                })
                insights['recommendations'].append({
                    'priority': 'medium',
                    'action': '기초 독서 능력 향상 프로그램 권장',
                    'category': '학습 지원'
                })

        # 진학 목표
        if profile.academic_goals_list:
            insights['strengths'].append({
                'category': '진로',
                'description': f"명확한 진학 목표: {profile.academic_goals_list[0]}",
                'icon': '🟢'
            })

    # 5. 학부모 연락 가능 여부
    from app.models.parent_student import ParentStudent
    parent_relations = ParentStudent.query.filter_by(student_id=student.student_id, is_active=True).all()

    if parent_relations:
        insights['strengths'].append({
            'category': '학부모',
            'description': f'학부모 {len(parent_relations)}명 연결됨 (협조 가능)',
            'icon': '🟢'
        })
    else:
        insights['warning_factors'].append({
            'category': '학부모',
            'description': '학부모 연락처 미등록',
            'icon': '🟡'
        })
        insights['recommendations'].append({
            'priority': 'low',
            'action': '학부모 정보 등록 및 연결 필요',
            'category': '학생 관리'
        })

    # 위험도 점수 계산
    risk_score = len(insights['risk_factors']) * 3 + len(insights['warning_factors']) * 1
    insights['risk_score'] = risk_score

    # 전체 상태
    if risk_score >= 5:
        insights['overall_status'] = 'high_risk'
        insights['overall_label'] = '높은 관심 필요'
        insights['overall_color'] = 'red'
    elif risk_score >= 3:
        insights['overall_status'] = 'medium_risk'
        insights['overall_label'] = '주의 관찰 필요'
        insights['overall_color'] = 'yellow'
    else:
        insights['overall_status'] = 'low_risk'
        insights['overall_label'] = '양호'
        insights['overall_color'] = 'green'

    return insights


def get_all_students_risk_analysis():
    """전체 학생 위험도 분석"""
    from app.models import Student
    from app.models.course import CourseEnrollment
    from app.models.student_profile import StudentProfile
    from app.models.consultation import ConsultationRecord
    from app.models.reading_mbti import ReadingMBTIResult, ReadingMBTIType
    from app import db

    students = Student.query.order_by(Student.name).all()
    risk_analysis = {
        'high_risk': [],
        'medium_risk': [],
        'low_risk': [],
        'no_data': []
    }

    for student in students:
        # 데이터 수집
        enrollments = CourseEnrollment.query.filter_by(student_id=student.student_id).all()
        profile = StudentProfile.query.filter_by(student_id=student.student_id).first()
        consultations = ConsultationRecord.query.filter_by(student_id=student.student_id)\
            .order_by(ConsultationRecord.consultation_date.desc())\
            .limit(10).all()
        mbti_result = ReadingMBTIResult.query.filter_by(student_id=student.student_id)\
            .order_by(ReadingMBTIResult.created_at.desc()).first()
        mbti_type = ReadingMBTIType.query.get(mbti_result.type_id) if mbti_result else None

        # 인사이트 생성
        insights = generate_student_insights(
            student, enrollments, profile, mbti_result, mbti_type, consultations
        )

        student_data = {
            'student': student,
            'risk_score': insights['risk_score'],
            'status': insights['overall_status'],
            'label': insights['overall_label'],
            'risk_count': len(insights['risk_factors']),
            'warning_count': len(insights['warning_factors']),
            'recent_attendance': get_recent_attendance_trend(student.student_id)[0]
        }

        if insights['overall_status'] == 'high_risk':
            risk_analysis['high_risk'].append(student_data)
        elif insights['overall_status'] == 'medium_risk':
            risk_analysis['medium_risk'].append(student_data)
        else:
            risk_analysis['low_risk'].append(student_data)

    # 위험도 순으로 정렬
    risk_analysis['high_risk'].sort(key=lambda x: x['risk_score'], reverse=True)
    risk_analysis['medium_risk'].sort(key=lambda x: x['risk_score'], reverse=True)

    return risk_analysis
