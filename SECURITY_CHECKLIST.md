# GitHub 업로드 전 보안 체크리스트

## 🚨 절대 업로드 금지 파일들

### 1. 환경 변수 및 설정 파일
- ❌ `.env` - 모든 비밀 정보 포함
- ❌ `config.py` (하드코딩된 비밀키 포함 시)
- ❌ `instance/` 폴더 전체
- ❌ `*.db` - SQLite 데이터베이스 (실제 사용자 데이터)

### 2. 인증 관련
- ❌ API 키, Secret Key
- ❌ 데이터베이스 비밀번호
- ❌ JWT Secret
- ❌ OAuth 클라이언트 시크릿
- ❌ SMTP 비밀번호
- ❌ Gemini API 키

### 3. 사용자 데이터
- ❌ 업로드된 파일 (`uploads/`, `static/uploads/`)
- ❌ 로그 파일 (`*.log`)
- ❌ 세션 데이터
- ❌ 백업 파일 (`*.bak`, `*.backup`)

### 4. IDE 및 시스템 파일
- ❌ `.idea/` (PyCharm)
- ❌ `.vscode/` (VS Code)
- ❌ `__pycache__/`
- ❌ `*.pyc`, `*.pyo`
- ❌ `.DS_Store` (Mac)
- ❌ `Thumbs.db` (Windows)

---

## ✅ .gitignore 파일 생성

**파일:** `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Flask
instance/
.webassets-cache
*.db
*.sqlite
*.sqlite3

# 환경 변수
.env
.env.local
.env.*.local
.flaskenv

# 업로드 파일
uploads/
static/uploads/
static/essays/
static/profile_images/

# 로그
*.log
logs/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store
Thumbs.db

# 테스트
.pytest_cache/
.coverage
htmlcov/
.tox/

# 마이그레이션 (선택적)
# migrations/versions/*.py
# migrations/alembic.ini

# 기타
*.bak
*.backup
*.tmp
node_modules/
```

---

## 🔐 환경 변수 분리

### 1. config.py 수정

**Before (위험):**
```python
SECRET_KEY = 'my-secret-key-12345'
GEMINI_API_KEY = 'AIzaSyABC123...'
SQLALCHEMY_DATABASE_URI = 'sqlite:///momoai.db'
```

**After (안전):**
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 기본 설정
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # 데이터베이스
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'momoai.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini API
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # 파일 업로드
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # 이메일 (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # 푸시 알림
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # 프로덕션에서는 환경변수 필수
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set")

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

### 2. .env.example 파일 생성

**파일:** `.env.example`

```bash
# Flask 설정
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# 데이터베이스
DATABASE_URL=sqlite:///momoai.db

# Gemini API
GEMINI_API_KEY=your-gemini-api-key-here

# 이메일 설정 (선택)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# 푸시 알림 (PWA 구현 후)
VAPID_PRIVATE_KEY=your-vapid-private-key
VAPID_PUBLIC_KEY=your-vapid-public-key
```

**설명:** 이 파일은 GitHub에 업로드하고, 실제 값을 `.env` 파일에 넣어 사용

---

## 🔍 GitHub 업로드 전 스캔

### 1. 비밀 정보 스캔 도구

```bash
# git-secrets 설치 (Windows)
# https://github.com/awslabs/git-secrets

# 또는 gitleaks 사용
pip install gitleaks

# 스캔 실행
gitleaks detect --source . --verbose
```

### 2. 수동 체크

```bash
# .env 파일 확인
git status

# 하드코딩된 비밀 검색
grep -r "SECRET_KEY.*=" --include="*.py"
grep -r "API_KEY.*=" --include="*.py"
grep -r "password.*=" --include="*.py"
```

---

## 📝 README.md 작성

**파일:** `README.md`

```markdown
# MOMOAI v4.0 - 교육 관리 시스템

Flask 기반 통합 교육 관리 플랫폼

## 주요 기능
- 📝 AI 첨삭 시스템 (Gemini API)
- 📊 주간 평가 및 ACE 분기 평가
- 👥 학생/강사/학부모 포털
- 📚 교재 및 동영상 관리
- 🔔 실시간 알림 시스템
- 💳 수강료 관리

## 기술 스택
- Backend: Flask, SQLAlchemy, Flask-Login
- Frontend: Tailwind CSS, Alpine.js, Chart.js
- Database: SQLite (개발), PostgreSQL (프로덕션 권장)
- AI: Google Gemini API

## 설치 방법

### 1. 저장소 클론
\`\`\`bash
git clone https://github.com/yourusername/momoai.git
cd momoai
\`\`\`

### 2. 가상환경 생성
\`\`\`bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
\`\`\`

### 3. 의존성 설치
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. 환경 변수 설정
\`\`\`bash
cp .env.example .env
# .env 파일을 열어 실제 값 입력
\`\`\`

### 5. 데이터베이스 마이그레이션
\`\`\`bash
flask db upgrade
\`\`\`

### 6. 서버 실행
\`\`\`bash
python run.py
\`\`\`

브라우저에서 http://localhost:5000 접속

## 환경 변수

\`\`\`.env.example\`\`\` 파일 참고

필수 환경변수:
- \`SECRET_KEY\`: Flask 시크릿 키
- \`GEMINI_API_KEY\`: Google Gemini API 키

## 프로덕션 배포

### Heroku
\`\`\`bash
heroku create your-app-name
heroku addons:create heroku-postgresql:hobby-dev
heroku config:set SECRET_KEY=your-secret-key
heroku config:set GEMINI_API_KEY=your-api-key
git push heroku main
\`\`\`

### AWS EC2
별도 배포 가이드 참고: [DEPLOYMENT.md](DEPLOYMENT.md)

## 라이선스
MIT License

## 기여
이슈 및 PR 환영합니다!

## 문의
your-email@example.com
\`\`\`

---

## 🔒 추가 보안 조치

### 1. requirements.txt 업데이트

```bash
pip freeze > requirements.txt
```

**보안 패키지 추가:**
```bash
pip install flask-talisman  # HTTPS 강제, 보안 헤더
pip install flask-limiter   # Rate limiting
```

### 2. 보안 헤더 추가

**파일:** `app/__init__.py` (수정)

```python
from flask_talisman import Talisman

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 보안 헤더 (프로덕션만)
    if not app.config['DEBUG']:
        Talisman(app,
            force_https=True,
            strict_transport_security=True,
            content_security_policy={
                'default-src': "'self'",
                'script-src': ["'self'", "'unsafe-inline'", 'cdn.jsdelivr.net'],
                'style-src': ["'self'", "'unsafe-inline'", 'cdn.jsdelivr.net']
            }
        )

    # ... 나머지 초기화
```

### 3. 비밀번호 정책 강화

**파일:** `app/auth/routes.py` (수정)

```python
import re

def validate_password(password):
    """비밀번호 강도 검증"""
    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다."

    if not re.search(r'[A-Z]', password):
        return False, "대문자를 포함해야 합니다."

    if not re.search(r'[a-z]', password):
        return False, "소문자를 포함해야 합니다."

    if not re.search(r'[0-9]', password):
        return False, "숫자를 포함해야 합니다."

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "특수문자를 포함해야 합니다."

    return True, "OK"
```

### 4. SQL Injection 방지

✅ **현재 코드는 안전** (SQLAlchemy ORM 사용)

❌ **위험한 예:**
```python
# 절대 사용 금지
query = f"SELECT * FROM users WHERE email = '{email}'"
```

✅ **안전한 방법:**
```python
# 현재 사용 중 (안전)
user = User.query.filter_by(email=email).first()
```

### 5. XSS 방지

✅ **Jinja2 자동 이스케이프 활성화** (기본)

추가 검증:
```python
from markupsafe import escape

# 사용자 입력 표시 시
safe_input = escape(user_input)
```

### 6. CSRF 보호

**이미 구현됨:** Flask-WTF 사용 중

확인:
```html
<!-- 모든 폼에 포함 -->
<form method="POST">
    {{ form.hidden_tag() }}  <!-- CSRF 토큰 -->
    ...
</form>
```

---

## 📤 GitHub 업로드 절차

### 1. 로컬에서 .env 백업
```bash
# .env 파일을 안전한 곳에 백업 (GitHub에는 절대 업로드 금지)
cp .env .env.backup
```

### 2. .gitignore 확인
```bash
# .gitignore가 제대로 작동하는지 확인
git status

# .env나 .db 파일이 보이면 안 됨!
```

### 3. Git 초기화 (처음만)
```bash
git init
git add .
git commit -m "Initial commit: MOMOAI v4.0"
```

### 4. GitHub 저장소 생성
- https://github.com/new 접속
- Repository name: `momoai` 또는 원하는 이름
- **Private** 선택 (처음엔 비공개 권장)
- README, .gitignore 체크 해제 (로컬에 있음)

### 5. 원격 저장소 연결
```bash
git remote add origin https://github.com/yourusername/momoai.git
git branch -M main
git push -u origin main
```

### 6. GitHub Actions (CI/CD) 설정 (선택)

**파일:** `.github/workflows/tests.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run tests
      env:
        SECRET_KEY: test-secret-key
        GEMINI_API_KEY: test-api-key
      run: |
        python -m pytest tests/
```

---

## ⚠️ 만약 실수로 비밀 정보를 업로드했다면?

### 1. 즉시 조치
```bash
# 커밋 취소 (아직 push 안 했다면)
git reset HEAD~1

# 이미 push 했다면 강제 덮어쓰기
git reset --hard HEAD~1
git push -f origin main
```

### 2. 비밀 정보 교체
- SECRET_KEY 재생성
- API 키 폐기 후 재발급
- 데이터베이스 비밀번호 변경

### 3. Git 히스토리에서 완전 삭제
```bash
# BFG Repo-Cleaner 사용
# https://rtyley.github.io/bfg-repo-cleaner/

java -jar bfg.jar --delete-files .env
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push -f
```

---

## 📋 최종 체크리스트

업로드 전 확인:

- [ ] `.gitignore` 파일 생성 완료
- [ ] `.env` 파일이 Git에 포함되지 않음 확인
- [ ] `config.py`에서 하드코딩된 비밀 제거
- [ ] `.env.example` 파일 생성 (템플릿)
- [ ] `README.md` 작성 (설치 방법 포함)
- [ ] `requirements.txt` 업데이트
- [ ] `*.db`, `*.sqlite` 파일 제외 확인
- [ ] `uploads/` 폴더 제외 확인
- [ ] API 키 환경변수로 분리
- [ ] 보안 스캔 실행 (gitleaks 등)
- [ ] 비밀번호 정책 확인
- [ ] CSRF 보호 활성화 확인
- [ ] GitHub에서 Private 저장소로 시작

---

## 🌐 프로덕션 배포 시 추가 고려사항

1. **HTTPS 필수** (PWA, 푸시 알림 필수)
2. **데이터베이스**: SQLite → PostgreSQL/MySQL 전환
3. **파일 스토리지**: 로컬 → AWS S3/Cloudflare R2
4. **세션 관리**: 파일 → Redis
5. **로그 관리**: Sentry, CloudWatch
6. **백업 자동화**: 일일 DB 백업
7. **모니터링**: Uptime monitoring
8. **CDN**: Cloudflare
9. **Rate Limiting**: Flask-Limiter
10. **환경변수**: AWS Secrets Manager, Heroku Config Vars

---

## 참고 자료

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask.palletsprojects.com/en/2.3.x/security/)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
