# 스키마 퀴즈 결과 및 히스토리 기능 추가 ✅

## 개요
스키마 퀴즈 완료 후 상세 답안 비교와 메인 페이지에 테스트 히스토리 기능을 추가했습니다.

## 새로운 기능

### 1. 상세 답안 비교 페이지
**위치**: `/student/schema-quiz/result/<session_id>`

#### 기능:
- 전체 점수 및 통계 표시
- 문제별 상세 답안 비교
  - 문제 번호 및 정답/오답 표시 (✅/❌)
  - 문제 내용 (정의/설명)
  - 학생이 입력한 답안
  - 정답 (틀렸을 때만 표시)
- 색상 구분:
  - 정답: 초록색 배경 (green-50, green-200)
  - 오답: 빨간색 배경 (red-50, red-200)

#### 화면 구성:
```
┌─────────────────────────────────────────┐
│ 📝 상세 답안 보기                       │
│                                         │
│ ✅ 문제 1                               │
│ 다음 설명에 해당하는 용어는?            │
│ 국민이 권력을 가지고 그 권력을...       │
│                                         │
│ 내 답안: 민주주의                       │
│                                         │
│ ❌ 문제 2                               │
│ 다음 설명에 해당하는 용어는?            │
│ 생물이 환경에 적응하여...               │
│                                         │
│ 내 답안: 진화                           │
│ 정답: 자연선택                          │
└─────────────────────────────────────────┘
```

### 2. 테스트 히스토리 (메인 페이지)
**위치**: `/student/schema-quiz`

#### 표시 내용:
- 최근 10개 테스트 결과
- 표 형식으로 보기 쉽게 정리
- 각 행 정보:
  - 날짜/시간 (YYYY-MM-DD HH:MM)
  - 과목 (🌏 사회 / 🔬 과학)
  - 문제 수
  - 정답 수
  - 점수 (색상 구분)
    - 90점 이상: 초록색
    - 80점 이상: 파란색
    - 60점 이상: 노란색
    - 60점 미만: 빨간색
  - 결과 보기 링크

#### 화면 구성:
```
┌──────────────────────────────────────────────────────────┐
│ 📊 최근 테스트 결과                                      │
├──────────────┬─────────┬────────┬────────┬──────┬──────┤
│ 날짜         │ 과목    │ 문제수 │ 정답수 │ 점수 │ 상세 │
├──────────────┼─────────┼────────┼────────┼──────┼──────┤
│ 2026-02-12   │ 🌏 사회 │   10   │   8    │ 80점 │ 보기 │
│ 14:30        │         │        │        │      │      │
├──────────────┼─────────┼────────┼────────┼──────┼──────┤
│ 2026-02-11   │ 🔬 과학 │   10   │   9    │ 90점 │ 보기 │
│ 16:45        │         │        │        │      │      │
└──────────────┴─────────┴────────┴────────┴──────┴──────┘
```

## 데이터베이스 변경

### SchemaQuizResult 모델 수정
**파일**: `app/models/schema_quiz.py`

#### 추가된 필드:
```python
session_id = db.Column(db.String(36), db.ForeignKey('schema_quiz_sessions.session_id'))
```

#### 추가된 관계:
```python
session = db.relationship('SchemaQuizSession', backref=db.backref('results', lazy='dynamic'))
```

### 마이그레이션
- **파일**: `migrations/versions/bb1ff7e14a16_add_session_id_to_schema_quiz_results.py`
- **적용 상태**: ✅ 완료

## 코드 변경

### 1. 라우트 수정 (`app/student_portal/routes.py`)

#### schema_quiz() - 메인 페이지:
```python
# 최근 테스트 히스토리 가져오기 (최근 10개)
recent_sessions = SchemaQuizSession.query.filter_by(
    student_id=student.student_id
).filter(
    SchemaQuizSession.completed_at.isnot(None)
).order_by(
    SchemaQuizSession.completed_at.desc()
).limit(10).all()
```

#### schema_quiz_submit() - 답안 제출:
```python
# session_id 추가
result = SchemaQuizResult(
    student_id=student.student_id,
    quiz_id=quiz_id,
    session_id=session_id,  # 추가됨
    student_answer=answer,
    is_correct=is_correct
)
```

#### schema_quiz_result() - 결과 페이지:
```python
# 이 세션의 모든 결과 가져오기
results = SchemaQuizResult.query.filter_by(
    session_id=session_id
).order_by(SchemaQuizResult.attempted_at).all()
```

### 2. 템플릿 수정

#### `templates/student/schema_quiz/result.html`:
- 상세 답안 비교 섹션 추가
- 문제별 답안 표시
- 정답/오답 색상 구분
- 반응형 디자인

#### `templates/student/schema_quiz/index.html`:
- 히스토리 테이블 추가
- 과목별 색상 배지
- 점수별 색상 구분
- 결과 보기 링크
- 반응형 테이블

## 사용 흐름

1. **퀴즈 시작**: 메인 페이지에서 사회 또는 과학 선택
2. **퀴즈 풀이**: 10문제 차례대로 풀기
3. **결과 확인**:
   - 전체 점수 및 통계
   - 문제별 상세 답안 비교
   - 내가 입력한 답과 정답 비교
4. **히스토리 확인**: 메인 페이지에서 최근 테스트 결과 목록 확인
5. **재시험**: "다시 도전하기" 또는 메인으로 돌아가기

## 주요 특징

### 데이터 정확성
- session_id를 통한 정확한 결과 연결
- 각 테스트 세션의 독립적인 결과 저장

### UI/UX
- 직관적인 색상 구분 (정답/오답)
- 반응형 디자인
- 읽기 쉬운 테이블 형식
- 과목별 색상 테마 유지

### 성능
- 최근 10개만 표시하여 로딩 속도 최적화
- lazy loading을 통한 효율적인 쿼리

## 참고 사항

⚠️ **중요**: 마이그레이션 적용 시 기존 퀴즈 데이터가 재설정되었습니다.
- 기존 테스트 결과는 삭제됨
- 새로운 테스트부터 히스토리가 쌓임
- 어휘 퀴즈 및 스키마 퀴즈 문제는 재업로드 필요

## 완료 ✅

모든 기능이 정상적으로 작동합니다:
- ✅ 상세 답안 비교 페이지
- ✅ 테스트 히스토리 표시
- ✅ session_id 연결
- ✅ 데이터베이스 마이그레이션
- ✅ 서버 정상 실행

**서버**: http://localhost:5000
