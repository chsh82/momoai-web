# 🤖 MOMOAI v3.3.0 웹 버전 - 프로젝트 개요

## 📌 프로젝트 정보

- **프로젝트명**: MOMOAI v3.3.0 Web Edition
- **버전**: 3.3.0
- **개발 완료일**: 2026-02-05
- **라이선스**: Proprietary
- **상태**: ✅ Production Ready

## 🎯 프로젝트 목적

기존 CLI 기반 MOMOAI 논술 첨삭 시스템을 웹 애플리케이션으로 전환하여:
1. 사용자 접근성 향상
2. 일괄 처리 기능 제공
3. 실시간 진행 상황 모니터링
4. REST API를 통한 자동화 지원

## 📁 프로젝트 구조

```
momoai_web/
├── 📄 Core Python Files
│   ├── app.py                      # Flask 메인 애플리케이션 (334줄)
│   ├── momoai_core.py              # MOMOAI 핵심 로직 (70줄)
│   ├── batch_processor.py          # 일괄 처리 모듈 (134줄)
│   ├── pdf_generator.py            # PDF 변환 모듈 (52줄)
│   ├── database.py                 # SQLite 관리 (219줄)
│   └── config.py                   # 설정 파일 (23줄)
│
├── 🌐 Frontend Files
│   ├── templates/                  # HTML 템플릿 (6개)
│   │   ├── base.html               # 기본 레이아웃
│   │   ├── index.html              # 메인 페이지 (단일/일괄 탭)
│   │   ├── processing.html         # 처리 중
│   │   ├── result.html             # 단일 결과
│   │   ├── batch_progress.html     # 일괄 진행
│   │   └── batch_complete.html     # 일괄 완료
│   └── static/
│       └── css/
│           └── style.css           # 커스텀 CSS
│
├── 📚 Documentation
│   ├── README.md                   # 프로젝트 개요 및 사용법
│   ├── QUICKSTART.md               # 빠른 시작 가이드
│   ├── TESTING.md                  # 테스트 가이드
│   ├── DEPLOYMENT.md               # 배포 가이드
│   ├── IMPLEMENTATION_SUMMARY.md   # 구현 요약
│   ├── PROJECT_OVERVIEW.md         # 본 문서
│   └── sample_template.md          # 일괄 첨삭 템플릿
│
├── 🔧 Configuration
│   ├── requirements.txt            # Python 의존성
│   ├── .gitignore                  # Git 제외 파일
│   ├── install.bat                 # 설치 스크립트 (Windows)
│   └── start.bat                   # 시작 스크립트 (Windows)
│
└── 📦 Data Directories
    ├── outputs/
    │   ├── html/                   # HTML 출력 폴더
    │   └── pdf/                    # PDF 출력 폴더
    ├── uploads/                    # 임시 업로드 폴더
    └── tasks.db                    # SQLite 데이터베이스 (자동 생성)
```

## 🔧 기술 스택

### Backend
| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.11+ | 프로그래밍 언어 |
| Flask | 3.0+ | 웹 프레임워크 |
| Anthropic SDK | 0.40+ | Claude API 클라이언트 |
| Pandas | 2.0+ | 데이터 처리 |
| Playwright | 1.40+ | PDF 변환 |
| SQLite | 3 | 데이터베이스 |

### Frontend
| 기술 | 용도 |
|------|------|
| Tailwind CSS | UI 스타일링 (CDN) |
| Vanilla JavaScript | 클라이언트 로직 |
| Fetch API | 비동기 통신 |

## 📊 주요 기능

### 1. 단일 첨삭 모드
```mermaid
graph LR
    A[사용자 입력] --> B[API 호출]
    B --> C[백그라운드 처리]
    C --> D[HTML 생성]
    D --> E[결과 표시]
    E --> F[PDF 생성]
    F --> G[다운로드]
```

**특징:**
- 실시간 로딩 애니메이션
- HTML 자동 저장
- 원클릭 PDF 생성
- 브라우저 내 리포트 미리보기

### 2. 일괄 첨삭 모드
```mermaid
graph LR
    A[파일 업로드] --> B[데이터 파싱]
    B --> C[검증]
    C --> D[백그라운드 처리]
    D --> E[실시간 진행률]
    E --> F[완료 페이지]
    F --> G[개별 다운로드]
```

**특징:**
- 엑셀/CSV 파일 지원
- 실시간 진행 상황 (2초 폴링)
- 현재 처리 중인 학생 표시
- 개별 에러 핸들링
- 완료 목록 자동 업데이트

### 3. REST API
```
POST   /api/review                          # 단일 첨삭
POST   /api/batch_review                    # 일괄 첨삭
GET    /api/task_status/<task_id>           # 작업 상태
GET    /api/batch_status/<batch_id>         # 일괄 상태
POST   /api/generate_pdf/<task_id>          # PDF 생성
POST   /api/generate_batch_pdf/<batch_id>/<index>  # 일괄 PDF
GET    /api/download/<filename>             # 파일 다운로드
```

## 🗄️ 데이터베이스 스키마

### Tasks Table (단일 작업)
```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    student_name TEXT,
    grade TEXT,
    status TEXT,           -- 'processing', 'completed', 'failed'
    html_path TEXT,
    pdf_path TEXT,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Batch Tasks Table (일괄 작업)
```sql
CREATE TABLE batch_tasks (
    batch_id TEXT PRIMARY KEY,
    total INTEGER,
    current INTEGER,
    current_student TEXT,
    status TEXT,           -- 'processing', 'completed', 'failed'
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Batch Results Table (일괄 결과)
```sql
CREATE TABLE batch_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT,
    index_num INTEGER,
    student_name TEXT,
    grade TEXT,
    html_path TEXT,
    pdf_path TEXT,
    FOREIGN KEY (batch_id) REFERENCES batch_tasks(batch_id)
);
```

## 🔐 보안 구현

### 파일 업로드 보안
- ✅ 확장자 화이트리스트 (`.xlsx`, `.csv`)
- ✅ 파일 크기 제한 (16MB)
- ✅ 파일명 Sanitization
- ✅ 경로 Traversal 방지

### API 키 관리
- ✅ 환경변수 사용
- ✅ 코드 하드코딩 금지
- ✅ `.gitignore`에 `.env` 추가

### 데이터 보호
- ✅ UUID 기반 작업 ID
- ✅ 안전한 파일 경로 처리
- ✅ SQL Injection 방지 (Parameterized Queries)

## 📈 성능 특성

### 처리 시간
- **단일 첨삭**: 60-120초 (Claude API 응답 시간)
- **일괄 첨삭**: 학생당 60-120초
- **PDF 생성**: 5-10초
- **페이지 로딩**: 1초 이내

### 동시 처리
- Threading 기반 백그라운드 처리
- 다중 사용자 동시 접속 지원
- 백그라운드 작업 독립 실행

### 리소스 사용
- **메모리**: ~200MB (기본)
- **디스크**: HTML 파일당 ~100KB, PDF 파일당 ~500KB
- **네트워크**: Claude API 호출 시 필요

## 🚀 설치 및 실행

### 빠른 시작 (Windows)
```bash
# 1. 설치
install.bat

# 2. 시작
start.bat
```

### 수동 설치
```bash
# 1. 의존성 설치
pip install -r requirements.txt
playwright install chromium

# 2. API 키 설정
setx ANTHROPIC_API_KEY "your-api-key"

# 3. 서버 시작
python app.py
```

### 접속
```
http://localhost:5000
```

## 📖 문서 가이드

| 문서 | 대상 독자 | 내용 |
|------|-----------|------|
| README.md | 모든 사용자 | 프로젝트 개요, 설치, 사용법, API 문서 |
| QUICKSTART.md | 초보 사용자 | 빠른 시작 가이드 (5분 내 실행) |
| TESTING.md | 개발자/QA | 테스트 체크리스트, 시나리오, 자동화 |
| DEPLOYMENT.md | DevOps | 프로덕션 배포, 보안, 모니터링 |
| IMPLEMENTATION_SUMMARY.md | 개발자 | 구현 상세, 코드 구조, 성공 기준 |
| PROJECT_OVERVIEW.md | 관리자 | 프로젝트 전체 개요 (본 문서) |
| sample_template.md | 사용자 | 일괄 첨삭 파일 형식 예시 |

## 🔄 워크플로우

### 단일 첨삭 워크플로우
1. 사용자가 학생 정보와 논술문 입력
2. 프론트엔드가 `/api/review`에 POST 요청
3. Flask가 UUID 생성 및 DB에 작업 등록
4. 백그라운드 스레드에서 Claude API 호출
5. HTML 생성 및 `outputs/html/` 저장
6. DB 업데이트 (`status=completed`)
7. 사용자를 결과 페이지로 리디렉션
8. 사용자가 PDF 생성 버튼 클릭
9. Playwright로 HTML → PDF 변환
10. `outputs/pdf/`에 저장 및 다운로드 제공

### 일괄 첨삭 워크플로우
1. 사용자가 엑셀/CSV 파일 업로드
2. Flask가 파일 검증 및 파싱
3. UUID 생성 및 `batch_tasks` 테이블에 등록
4. 백그라운드 스레드에서 각 학생 순차 처리
5. 처리 중 DB 업데이트 (`current`, `current_student`)
6. 프론트엔드가 2초마다 `/api/batch_status` 폴링
7. 진행률 바 및 완료 목록 실시간 업데이트
8. 모든 학생 처리 완료 시 `status=completed`
9. 자동으로 완료 페이지로 리디렉션
10. 개별 HTML/PDF 다운로드 제공

## 🎨 UI/UX 특징

### 디자인 원칙
- **미니멀리즘**: 깔끔하고 직관적인 인터페이스
- **일관성**: Tailwind CSS 기반 통일된 스타일
- **반응성**: 다양한 화면 크기 지원
- **접근성**: 명확한 레이블 및 에러 메시지

### 색상 팔레트
- **주색상**: Blue (#3B82F6) - 신뢰감, 전문성
- **강조색**: Green (#10B981) - 성공, HTML
- **강조색**: Red (#EF4444) - 중요, PDF
- **배경**: Gray (#F9FAFB) - 중립, 읽기 편함

### 인터랙션
- 버튼 호버 효과 (Transform + Scale)
- 로딩 애니메이션 (Spinner)
- 진행률 바 (Smooth Transition)
- 탭 전환 (Instant Feedback)

## 🧪 테스트 전략

### 단위 테스트
- `momoai_core.py`: 논술문 분석 로직
- `batch_processor.py`: 데이터 파싱 및 처리
- `pdf_generator.py`: PDF 변환
- `database.py`: CRUD 함수

### 통합 테스트
- 단일 첨삭 전체 플로우
- 일괄 첨삭 전체 플로우
- REST API 엔드포인트

### 수동 테스트
- UI/UX 테스트
- 브라우저 호환성 (Chrome, Firefox, Edge, Safari)
- 인쇄 품질 확인

## 📦 배포 시나리오

### 시나리오 1: 로컬 개발 (현재)
```bash
python app.py
```
- Flask 개발 서버
- 단일 사용자
- 빠른 반복 개발

### 시나리오 2: 프로덕션 (Waitress)
```bash
pip install waitress
python serve.py
```
- Windows 친화적
- 다중 스레드
- 안정적인 성능

### 시나리오 3: 프로덕션 (Gunicorn + Nginx)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
- Linux 최적화
- 다중 워커
- Nginx 리버스 프록시
- SSL/HTTPS

### 시나리오 4: 컨테이너 (Docker)
```bash
docker-compose up -d
```
- 이식성
- 쉬운 배포
- 스케일링 용이

## 🐛 알려진 제한사항

### 기술적 제한
1. **동시 처리**: Threading으로 제한적 (Celery 권장 for scale)
2. **파일 크기**: 16MB 업로드 제한
3. **데이터베이스**: SQLite (PostgreSQL 권장 for production)

### 기능적 제한
1. **사용자 인증**: 현재 미구현
2. **작업 취소**: 백그라운드 작업 취소 불가
3. **이메일 알림**: 완료 시 알림 없음

### 성능 제한
1. **Claude API**: 응답 시간에 의존 (60-120초)
2. **순차 처리**: 일괄 첨삭 시 순차 처리
3. **메모리**: 대용량 일괄 처리 시 메모리 사용 증가

## 🔮 향후 로드맵

### v3.4.0 (Q2 2026)
- [ ] 사용자 인증 및 권한 관리
- [ ] 작업 취소 기능
- [ ] WebSocket 실시간 업데이트
- [ ] 다크 모드

### v3.5.0 (Q3 2026)
- [ ] 통계 대시보드
- [ ] 이메일 알림
- [ ] 다중 파일 ZIP 다운로드
- [ ] 모바일 앱 (React Native)

### v4.0.0 (Q4 2026)
- [ ] Celery + Redis 태스크 큐
- [ ] PostgreSQL 마이그레이션
- [ ] 클라우드 스토리지 (S3)
- [ ] 다국어 지원

## 📞 지원 및 연락처

### 개발자
- **이름**: [개발자 이름]
- **이메일**: [이메일 주소]
- **GitHub**: [GitHub URL]

### 버그 리포트
이슈 발견 시:
1. 재현 단계 기록
2. 스크린샷 첨부
3. 에러 메시지 복사
4. 개발자에게 전달

### 기능 제안
새 기능 제안 시:
1. 사용 사례 설명
2. 예상 효과 기술
3. 우선순위 제시

## 📄 라이선스

© 2026 MOMOAI. All rights reserved.

본 소프트웨어는 상업적 소프트웨어로, 무단 복제, 배포, 수정이 금지됩니다.

## 🙏 감사의 말

이 프로젝트는 다음 기술들을 사용합니다:
- **Anthropic Claude**: 최첨단 AI 언어 모델
- **Flask**: 파이썬 웹 프레임워크
- **Tailwind CSS**: 유틸리티 기반 CSS 프레임워크
- **Playwright**: 브라우저 자동화 라이브러리

---

**프로젝트 상태**: ✅ **Production Ready**

**최종 업데이트**: 2026-02-05
