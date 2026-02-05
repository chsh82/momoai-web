# 🚀 MOMOAI v3.3.0 웹 버전 빠른 시작 가이드

## 1️⃣ 설치 (최초 1회만)

### 1.1 의존성 설치
```bash
cd momoai_web
pip install -r requirements.txt
playwright install chromium
```

### 1.2 API 키 설정
```bash
# Windows
setx ANTHROPIC_API_KEY "sk-ant-api03-..."

# 새 터미널을 열어야 환경변수가 적용됩니다.
```

## 2️⃣ 실행

```bash
python app.py
```

브라우저에서 http://localhost:5000 접속

## 3️⃣ 사용법

### 단일 첨삭
1. "단일 첨삭" 탭 선택
2. 학생 이름, 학년, 논술문 입력
3. "첨삭하기" 버튼 클릭
4. 1-2분 대기 후 결과 확인
5. HTML/PDF 다운로드

### 일괄 첨삭
1. "일괄 첨삭" 탭 선택
2. 엑셀/CSV 파일 준비 (필수 열: 학생명, 학년, 논술문)
3. 파일 업로드
4. 실시간 진행 상황 확인
5. 완료 후 개별 다운로드

## 4️⃣ 파일 형식 예시

### 엑셀 (.xlsx)
| 학생명 | 학년 | 논술문 |
|--------|------|--------|
| 홍길동 | 초등 | 논술문 내용... |
| 이영희 | 중등 | 논술문 내용... |

### CSV (.csv)
```
학생명,학년,논술문
홍길동,초등,논술문 내용...
이영희,중등,논술문 내용...
```

## 5️⃣ 주의사항

✅ API 키가 올바르게 설정되었는지 확인
✅ 인터넷 연결 필요 (Claude API 호출)
✅ 학생당 1-2분 소요 (일괄 처리 시 시간 고려)
✅ 학년은 "초등", "중등", "고등" 중 하나만 입력

## 6️⃣ 문제 해결

### API 키 오류
```
ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
```
→ 터미널을 새로 열고 다시 실행하세요.

### Playwright 오류
```
Executable doesn't exist
```
→ `playwright install chromium` 실행하세요.

## 7️⃣ 출력 파일 위치

- **HTML**: `momoai_web/outputs/html/`
- **PDF**: `momoai_web/outputs/pdf/`

## 🎉 완료!

이제 MOMOAI를 사용할 준비가 되었습니다!
