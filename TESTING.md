# 🧪 MOMOAI v3.3.0 테스트 가이드

## 테스트 체크리스트

### ✅ Phase 1: 설치 및 환경 설정
- [ ] Python 패키지 설치 완료 (`pip install -r requirements.txt`)
- [ ] Playwright 설치 완료 (`playwright install chromium`)
- [ ] API 키 환경변수 설정 완료
- [ ] 서버 정상 시작 (`python app.py`)
- [ ] 브라우저에서 http://localhost:5000 접속 확인

### ✅ Phase 2: UI 테스트
- [ ] 메인 페이지 로딩 확인
- [ ] "단일 첨삭" 탭 전환 작동
- [ ] "일괄 첨삭" 탭 전환 작동
- [ ] 폼 입력 필드 정상 표시
- [ ] 반응형 디자인 확인 (브라우저 크기 조절)

### ✅ Phase 3: 단일 첨삭 기능 테스트
- [ ] 빈 필드 제출 시 에러 메시지
- [ ] 올바른 데이터 제출 시 로딩 오버레이 표시
- [ ] 첨삭 완료 후 결과 페이지로 리디렉션
- [ ] HTML 리포트 정상 표시
- [ ] HTML 다운로드 버튼 작동
- [ ] PDF 생성 버튼 작동
- [ ] PDF 다운로드 버튼 작동

### ✅ Phase 4: 일괄 첨삭 기능 테스트
- [ ] 파일 업로드 드래그 앤 드롭 작동
- [ ] 파일 선택 버튼 작동
- [ ] 잘못된 파일 형식 업로드 시 에러
- [ ] 필수 열 누락 시 에러 메시지
- [ ] 올바른 파일 업로드 시 진행 상황 페이지로 이동
- [ ] 실시간 진행률 업데이트 확인
- [ ] 현재 처리 중인 학생 표시 확인
- [ ] 완료된 학생 목록 업데이트 확인
- [ ] 완료 후 완료 페이지로 자동 이동
- [ ] 개별 HTML/PDF 다운로드 버튼 작동

### ✅ Phase 5: API 테스트

#### 단일 첨삭 API
```bash
curl -X POST http://localhost:5000/api/review \
  -H "Content-Type: application/json" \
  -d '{
    "student_name": "홍길동",
    "grade": "초등",
    "essay_text": "오늘은 날씨가 좋다. 친구들과 놀았다."
  }'
```
- [ ] 응답에 `task_id` 포함
- [ ] 상태가 `processing`

#### 작업 상태 조회
```bash
curl http://localhost:5000/api/task_status/<task_id>
```
- [ ] 작업 상태 조회 가능
- [ ] 완료 시 `completed` 반환

### ✅ Phase 6: 파일 시스템 테스트
- [ ] HTML 파일이 `outputs/html/` 폴더에 저장됨
- [ ] PDF 파일이 `outputs/pdf/` 폴더에 저장됨
- [ ] 파일명에 학생명, 학년, 타임스탬프 포함
- [ ] 파일 다운로드 시 올바른 파일명

### ✅ Phase 7: 에러 핸들링 테스트
- [ ] API 키 미설정 시 서버 시작 실패
- [ ] 잘못된 task_id 조회 시 404 에러
- [ ] 존재하지 않는 파일 다운로드 시 404 에러
- [ ] 네트워크 오류 시 사용자 친화적 에러 메시지

### ✅ Phase 8: 성능 테스트
- [ ] 단일 첨삭 소요 시간 측정 (1-2분 예상)
- [ ] 10명 일괄 첨삭 소요 시간 측정
- [ ] 동시 접속 테스트 (2-3명)
- [ ] 메모리 사용량 확인

### ✅ Phase 9: 브라우저 호환성 테스트
- [ ] Chrome 정상 작동
- [ ] Firefox 정상 작동
- [ ] Edge 정상 작동
- [ ] Safari 정상 작동 (Mac)

### ✅ Phase 10: PDF 품질 테스트
- [ ] 레이아웃이 HTML과 동일
- [ ] 차트 이미지 정상 표시
- [ ] 페이지 분할 적절 (3-4페이지)
- [ ] 인쇄 시 가독성 확인

## 테스트 시나리오

### 시나리오 1: 단일 첨삭 전체 플로우
1. 메인 페이지 접속
2. "단일 첨삭" 탭 선택
3. 학생 정보 입력:
   - 이름: "테스트학생"
   - 학년: "중등"
   - 논술문: 짧은 테스트 논술문 (3-4문장)
4. "첨삭하기" 버튼 클릭
5. 로딩 확인
6. 결과 페이지 확인
7. HTML 다운로드
8. PDF 생성
9. PDF 다운로드

### 시나리오 2: 일괄 첨삭 전체 플로우
1. 메인 페이지 접속
2. "일괄 첨삭" 탭 선택
3. 샘플 엑셀 파일 준비 (3명의 학생)
4. 파일 업로드
5. 진행 상황 페이지에서 실시간 모니터링
6. 완료 페이지 확인
7. 각 학생별 HTML 다운로드
8. 각 학생별 PDF 생성 및 다운로드

### 시나리오 3: 에러 복구 테스트
1. 잘못된 파일 업로드 시도
2. 에러 메시지 확인
3. 올바른 파일로 재시도
4. 정상 처리 확인

## 자동화 테스트 스크립트

### 단일 첨삭 API 테스트 (Python)
```python
import requests
import time

# 1. 첨삭 요청
response = requests.post('http://localhost:5000/api/review', json={
    'student_name': '테스트학생',
    'grade': '초등',
    'essay_text': '오늘은 날씨가 좋다. 친구들과 놀았다. 즐거운 하루였다.'
})

task_id = response.json()['task_id']
print(f"Task ID: {task_id}")

# 2. 상태 확인 (폴링)
while True:
    status_response = requests.get(f'http://localhost:5000/api/task_status/{task_id}')
    status = status_response.json()['status']
    print(f"Status: {status}")

    if status == 'completed':
        print("✅ 첨삭 완료!")
        break
    elif status == 'failed':
        print("❌ 첨삭 실패!")
        break

    time.sleep(5)
```

## 알려진 이슈 및 해결 방법

### Issue 1: Playwright 설치 오류
```
Error: Executable doesn't exist
```
**해결:** `playwright install chromium` 실행

### Issue 2: API 키 인식 안 됨
```
ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
```
**해결:** 터미널 재시작 후 다시 시도

### Issue 3: 파일 업로드 실패
```
지원하지 않는 파일 형식입니다.
```
**해결:** `.xlsx` 또는 `.csv` 파일인지 확인

### Issue 4: PDF 생성 실패
```
PDF 생성 중 오류가 발생했습니다.
```
**해결:** Chromium이 설치되었는지 확인

## 성능 벤치마크

### 목표 성능
- 단일 첨삭: 60-120초
- 일괄 첨삭 (10명): 10-20분
- PDF 생성: 5-10초
- 페이지 로딩: 1초 이내

### 측정 방법
```python
import time

start = time.time()
# ... 작업 수행 ...
end = time.time()

print(f"소요 시간: {end - start:.2f}초")
```

## 테스트 완료 체크

- [ ] 모든 Phase 테스트 완료
- [ ] 모든 시나리오 테스트 완료
- [ ] 알려진 이슈 해결 확인
- [ ] 성능 벤치마크 달성
- [ ] 문서화 완료

## 다음 단계

테스트가 완료되면:
1. 버그 리포트 작성
2. 개선 사항 정리
3. 사용자 가이드 업데이트
4. 배포 준비
