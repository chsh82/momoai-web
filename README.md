# 🤖 MOMOAI v3.3.0 웹 버전

AI 기반 논술 자동 첨삭 시스템의 웹 애플리케이션 버전입니다.

## 📋 개요

MOMOAI는 Claude Opus 4.5를 활용하여 학생들의 논술문을 18개 핵심 지표로 분석하고 전문적인 첨삭을 제공하는 시스템입니다.

### 주요 기능

- **단일 첨삭 모드**: 학생 정보와 논술문 입력 → HTML 리포트 생성 → PDF 다운로드
- **일괄 첨삭 모드**: 엑셀/CSV 파일 업로드 → 실시간 진행 상황 표시 → 개별 파일 다운로드
- **자동 HTML 저장**: 모든 첨삭 결과를 HTML 형식으로 자동 저장
- **PDF 생성**: 버튼 클릭으로 HTML을 PDF로 변환
- **REST API**: 외부 자동화 도구와 연동 가능

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
cd momoai_web
pip install -r requirements.txt
playwright install chromium
```

### 2. 환경변수 설정

**Windows:**
```bash
setx ANTHROPIC_API_KEY "your_api_key_here"
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

### 3. 애플리케이션 실행

```bash
python app.py
```

### 4. 브라우저 접속

```
http://localhost:5000
```

## 📁 프로젝트 구조

```
momoai_web/
├── app.py                      # Flask 메인 애플리케이션
├── momoai_core.py              # MOMOAI 핵심 로직
├── batch_processor.py          # 일괄 처리 모듈
├── pdf_generator.py            # PDF 변환 모듈
├── database.py                 # SQLite 작업 관리
├── config.py                   # 설정 파일
├── requirements.txt            # 패키지 의존성
├── tasks.db                    # SQLite 데이터베이스
├── templates/                  # HTML 템플릿
│   ├── base.html
│   ├── index.html
│   ├── processing.html
│   ├── result.html
│   ├── batch_progress.html
│   └── batch_complete.html
├── static/                     # 정적 파일
│   └── css/
│       └── style.css
├── outputs/                    # 출력 파일
│   ├── html/                   # HTML 파일
│   └── pdf/                    # PDF 파일
└── uploads/                    # 임시 업로드 폴더
```

## 📊 일괄 첨삭 파일 형식

### 엑셀 (.xlsx) / CSV (.csv)

필수 열:
- `학생명`: 학생 이름
- `학년`: "초등", "중등", "고등" 중 하나
- `논술문`: 첨삭할 논술문 내용

### 예시

| 학생명 | 학년 | 논술문 |
|--------|------|--------|
| 홍길동 | 초등 | 오늘은 날씨가 좋다... |
| 이영희 | 중등 | 환경 보호는 중요하다... |
| 박민수 | 고등 | 기술 발전과 윤리... |

## 🔧 API 문서

### 1. 단일 첨삭 API

**엔드포인트:** `POST /api/review`

**요청 본문:**
```json
{
  "student_name": "홍길동",
  "grade": "초등",
  "essay_text": "논술문 내용..."
}
```

**응답:**
```json
{
  "task_id": "uuid",
  "status": "processing"
}
```

### 2. 일괄 첨삭 API

**엔드포인트:** `POST /api/batch_review`

**요청:** `multipart/form-data` (파일 업로드)

**응답:**
```json
{
  "batch_id": "uuid",
  "total": 10,
  "status": "processing"
}
```

### 3. 작업 상태 조회

**엔드포인트:** `GET /api/task_status/<task_id>`

**응답:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "student_name": "홍길동",
  "grade": "초등"
}
```

### 4. 일괄 작업 상태 조회

**엔드포인트:** `GET /api/batch_status/<batch_id>`

**응답:**
```json
{
  "batch_id": "uuid",
  "status": "processing",
  "total": 10,
  "current": 5,
  "current_student": "이영희",
  "progress": 50.0,
  "completed": [...]
}
```

### 5. PDF 생성

**엔드포인트:** `POST /api/generate_pdf/<task_id>`

**응답:**
```json
{
  "pdf_path": "/path/to/pdf",
  "pdf_filename": "filename.pdf",
  "status": "success"
}
```

### 6. 파일 다운로드

**엔드포인트:** `GET /api/download/<filename>`

**응답:** 파일 다운로드

## 🎨 화면 구성

### 메인 페이지
- 단일 첨삭 탭: 학생 정보 입력 폼
- 일괄 첨삭 탭: 파일 업로드 폼

### 첨삭 결과 페이지
- HTML 리포트 표시
- HTML/PDF 다운로드 버튼

### 일괄 첨삭 진행 상황
- 실시간 진행률 표시
- 현재 처리 중인 학생 표시
- 완료된 학생 목록 및 다운로드 버튼

### 일괄 첨삭 완료 페이지
- 전체 학생 목록
- 개별 HTML/PDF 다운로드 버튼

## 🔒 보안

### 파일 업로드 보안
- 확장자 화이트리스트: `.xlsx`, `.csv`만 허용
- 파일 크기 제한: 16MB
- 파일명 Sanitization 적용

### API 키 관리
- 환경변수로만 관리
- 코드에 하드코딩 금지
- `.gitignore`에 `.env` 추가 권장

### 출력 파일 보호
- UUID 기반 파일명 생성
- 경로 traversal 방지

## ⚙️ 설정 (config.py)

```python
# MOMOAI 규칙 문서 경로
MOMOAI_DOC_PATH = Path(r"C:\Users\aproa\Downloads\MOMOAI_v3_3_0_final (20260112).md")

# 업로드 제한
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'xlsx', 'csv'}
```

## 🐛 문제 해결

### API 키 오류
```
ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
```
→ 환경변수를 올바르게 설정했는지 확인하세요.

### Playwright 오류
```
Executable doesn't exist at ...
```
→ `playwright install chromium` 명령어를 실행하세요.

### 파일 업로드 오류
```
필수 열이 누락되었습니다: ...
```
→ 엑셀/CSV 파일에 `학생명`, `학년`, `논술문` 열이 있는지 확인하세요.

## 📝 개발 노트

### 기술 스택
- **백엔드**: Flask 3.0+
- **프론트엔드**: HTML + Tailwind CSS + Vanilla JavaScript
- **AI 모델**: Claude Opus 4.5
- **PDF 변환**: Playwright (Chromium)
- **데이터베이스**: SQLite
- **일괄 처리**: Python threading

### 성능 최적화
- 백그라운드 스레드로 비동기 처리
- SQLite로 작업 상태 관리
- 2초 간격 폴링으로 실시간 업데이트

### 향후 개선 사항
- [ ] 사용자 인증 시스템
- [ ] 작업 취소 기능
- [ ] 이메일 알림
- [ ] 통계 대시보드
- [ ] 다중 파일 다운로드 (ZIP)

## 📄 라이선스

© 2026 MOMOAI. All rights reserved.

## 🤝 기여

버그 리포트 및 기능 제안은 이슈로 등록해주세요.

## 📞 지원

문의사항이 있으시면 개발자에게 연락해주세요.
