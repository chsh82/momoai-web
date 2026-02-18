# 스키마 퀴즈 주관식 전환 완료 ✅

## 개요
스키마 퀴즈를 객관식 형식에서 주관식 형식으로 전환하고, 초성 힌트 기능을 추가했습니다.

## 변경 사항

### 1. 한글 처리 유틸리티 생성
**파일**: `app/utils/korean_utils.py` (신규 생성)

#### 함수 목록:
- `get_chosung(text)`: 한글 텍스트에서 초성을 추출
  - 한글 유니코드 계산: `(ord(char) - 0xAC00) // (21 * 28)`
  - 영문자, 숫자, 특수문자는 그대로 유지
  - 예: "민주주의" → "ㅁㅈㅈㅇ"

- `normalize_answer(text)`: 답안 정규화
  - 공백 제거
  - 소문자 변환
  - 특수문자 제거 (점, 쉼표, 가운뎃점)
  - 예: "민주 주의." → "민주주의"

- `check_answer_similarity(student_answer, correct_answer, threshold=0.8)`: 답안 유사도 검사
  - 완전 일치 확인
  - 포함 관계 확인 (길이 차이 2글자 이내)
  - 유연한 정답 인정 시스템

### 2. 라우트 수정
**파일**: `app/student_portal/routes.py`

#### schema_quiz_take() 함수 (라인 2271-2332):
**변경 전**:
```python
# 선택지 파싱
try:
    options = json.loads(current_quiz.options)
except:
    options = [current_quiz.correct_answer, "오답1", "오답2", "오답3"]

# 선택지 섞기
random.shuffle(options)

return render_template(..., options=options, ...)
```

**변경 후**:
```python
from app.utils.korean_utils import get_chosung

# 초성 힌트 생성
chosung_hint = get_chosung(current_quiz.correct_answer)

return render_template(..., chosung_hint=chosung_hint, ...)
```

#### schema_quiz_submit() 함수 (라인 2335-2377):
**변경 전**:
```python
# 정답 확인
is_correct = (answer == quiz.correct_answer)
```

**변경 후**:
```python
from app.utils.korean_utils import check_answer_similarity

# 정답 확인 (유사도 검사)
is_correct = check_answer_similarity(answer, quiz.correct_answer)
```

### 3. 템플릿 수정
**파일**: `templates/student/schema_quiz/take.html`

#### 변경 내용:
1. **객관식 → 주관식 변환**:
   - 라디오 버튼 제거
   - 텍스트 입력 필드 추가
   - 플레이스홀더: "정의를 입력하세요"

2. **초성 힌트 표시**:
   ```html
   <!-- 초성 힌트 -->
   <div class="bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200 border-2 rounded-lg p-6 mb-6">
       <p class="text-sm text-amber-600 font-medium mb-2">💡 초성 힌트</p>
       <p class="text-2xl font-mono font-bold text-gray-800 tracking-wider">{{ chosung_hint }}</p>
   </div>
   ```

3. **JavaScript 수정**:
   - `change` 이벤트 → `input` 이벤트로 변경
   - 엔터키 제출 기능 추가
   - 입력창 자동 포커스
   - 제출 시 입력창 비활성화

4. **오답 표시 개선**:
   - 정답 표시 크기 증가 (text-sm → text-base)
   - 패딩 추가로 가독성 향상

## 기술적 세부사항

### 한글 초성 추출 원리
- 한글 유니코드 범위: '가'(0xAC00) ~ '힣'(0xD7A3)
- 구조: 초성(19개) × 중성(21개) × 종성(28개) = 11,172자
- 초성 인덱스 = (문자코드 - 0xAC00) ÷ (21 × 28)

### 답안 검사 로직
1. **1단계**: 정규화 (공백/특수문자 제거, 소문자 변환)
2. **2단계**: 완전 일치 확인
3. **3단계**: 포함 관계 확인 + 길이 차이 검사 (2글자 이내)

### UI/UX 개선
- 색상 테마 유지 (사회: amber, 과학: blue)
- 초성 힌트 강조 표시 (그라디언트 배경)
- 모노스페이스 폰트로 초성 가독성 향상
- 자동 포커스로 즉시 입력 가능
- 엔터키 제출로 편의성 향상

## 테스트 방법

1. 학생 포털 로그인
2. "스키마 퀴즈" 메뉴 클릭
3. 사회 또는 과학 선택
4. 주관식 입력창과 초성 힌트 확인
5. 답안 입력 후 제출
6. 유사도 검사 동작 확인

## 예시

**문제 (설명)**: "국민이 권력을 가지고 그 권력을 스스로 행사하는 제도"
**초성 힌트**: "ㅁㅈㅈㅇ"
**정답**: "민주주의"

**허용되는 답안**:
- "민주주의" ✅
- "민 주 주 의" ✅ (공백 무시)
- "민주주의." ✅ (특수문자 무시)

## 파일 목록

### 신규 생성:
- `app/utils/korean_utils.py`
- `SCHEMA_QUIZ_SHORT_ANSWER_UPDATE.md`

### 수정:
- `app/student_portal/routes.py`
- `templates/student/schema_quiz/take.html`

## 추가 수정 (2026-02-12)

### 문제 형식 변경
**기존**: 용어를 보여주고 정의를 입력
- 문제: "민주주의"
- 답안: "국민이 권력을 가지고..."

**변경**: 정의를 보여주고 용어를 입력
- 문제: "국민이 권력을 가지고..."
- 답안: "민주주의"
- 초성 힌트: "ㅁㅈㅈㅇ" (용어의 초성)

### 변경된 코드

#### routes.py:
```python
# 초성 힌트: quiz.correct_answer → quiz.term
chosung_hint = get_chosung(current_quiz.term)

# 정답 확인: quiz.correct_answer → quiz.term
is_correct = check_answer_similarity(answer, quiz.term)
```

#### take.html:
```html
<!-- 문제: quiz.term → quiz.correct_answer -->
<h3>{{ quiz.correct_answer }}</h3>

<!-- 입력창 플레이스홀더 변경 -->
<input placeholder="용어를 입력하세요">

<!-- 오답 시 표시: quiz.correct_answer → quiz.term -->
document.getElementById('correctAnswer').textContent = '{{ quiz.term }}';
```

## 완료 ✅

모든 변경사항이 적용되었으며, 서버가 정상적으로 실행 중입니다.
- URL: http://localhost:5000
- 디버그 모드: ON
- 문제 형식: 정의 → 용어 맞추기
