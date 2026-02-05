# 🚀 MOMOAI v3.3.0 배포 가이드

## 배포 옵션

### 1. 로컬 개발 환경 (현재)
- Flask 개발 서버 사용
- 단일 사용자, 테스트 목적

### 2. 프로덕션 환경
- WSGI 서버 (Gunicorn 또는 Waitress)
- 다중 사용자, 실제 서비스 목적

## 프로덕션 배포 가이드

### Option A: Gunicorn (Linux/Mac)

#### 1. Gunicorn 설치
```bash
pip install gunicorn
```

#### 2. 실행
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

**옵션 설명:**
- `-w 4`: 워커 프로세스 4개 (CPU 코어 수에 따라 조절)
- `-b 0.0.0.0:5000`: 모든 IP에서 5000 포트로 접속 허용
- `app:app`: app.py 파일의 app 객체

#### 3. 백그라운드 실행
```bash
nohup gunicorn -w 4 -b 0.0.0.0:5000 app:app &
```

### Option B: Waitress (Windows)

#### 1. Waitress 설치
```bash
pip install waitress
```

#### 2. serve.py 생성
```python
from waitress import serve
from app import app

if __name__ == '__main__':
    print("=" * 50)
    print("🤖 MOMOAI v3.3.0 프로덕션 서버")
    print("=" * 50)
    print("🌐 http://0.0.0.0:5000")
    print("=" * 50)
    serve(app, host='0.0.0.0', port=5000, threads=4)
```

#### 3. 실행
```bash
python serve.py
```

### Option C: Docker

#### 1. Dockerfile 생성
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application
COPY . .

# Set environment variable
ENV ANTHROPIC_API_KEY=""

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

#### 2. docker-compose.yml 생성
```yaml
version: '3.8'

services:
  momoai:
    build: .
    ports:
      - "5000:5000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./outputs:/app/outputs
      - ./uploads:/app/uploads
    restart: unless-stopped
```

#### 3. 실행
```bash
docker-compose up -d
```

## Nginx 리버스 프록시 설정

### 1. Nginx 설치
```bash
sudo apt install nginx
```

### 2. 설정 파일 생성 (`/etc/nginx/sites-available/momoai`)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 16M;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /path/to/momoai_web/static;
    }
}
```

### 3. 설정 활성화
```bash
sudo ln -s /etc/nginx/sites-available/momoai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## SSL/HTTPS 설정 (Let's Encrypt)

### 1. Certbot 설치
```bash
sudo apt install certbot python3-certbot-nginx
```

### 2. SSL 인증서 발급
```bash
sudo certbot --nginx -d your-domain.com
```

### 3. 자동 갱신 설정
```bash
sudo certbot renew --dry-run
```

## 시스템 서비스 등록 (Systemd)

### 1. 서비스 파일 생성 (`/etc/systemd/system/momoai.service`)
```ini
[Unit]
Description=MOMOAI Web Application
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/momoai_web
Environment="ANTHROPIC_API_KEY=your-api-key"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. 서비스 시작
```bash
sudo systemctl daemon-reload
sudo systemctl start momoai
sudo systemctl enable momoai
sudo systemctl status momoai
```

## 환경변수 관리

### .env 파일 생성
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
FLASK_ENV=production
SECRET_KEY=your-secret-key
```

### python-dotenv 사용
```python
# config.py 수정
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
```

## 보안 체크리스트

- [ ] API 키를 환경변수로 관리
- [ ] `.env` 파일을 `.gitignore`에 추가
- [ ] HTTPS 설정 (프로덕션 환경)
- [ ] 파일 업로드 크기 제한 설정
- [ ] CORS 정책 설정 (필요시)
- [ ] Rate limiting 설정 (필요시)
- [ ] 로그 파일 관리
- [ ] 정기 백업 설정

## 모니터링

### 로그 확인
```bash
# Systemd 로그
sudo journalctl -u momoai -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 디스크 사용량 모니터링
```bash
du -sh outputs/html outputs/pdf
```

### 프로세스 모니터링
```bash
ps aux | grep gunicorn
```

## 백업 및 복구

### 백업 대상
- `outputs/html/`: HTML 파일
- `outputs/pdf/`: PDF 파일
- `tasks.db`: 작업 데이터베이스
- `.env`: 환경변수 파일

### 백업 스크립트 예시
```bash
#!/bin/bash
BACKUP_DIR="/backup/momoai"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/momoai_$DATE.tar.gz \
    outputs/ \
    tasks.db \
    .env

# 7일 이상 된 백업 삭제
find $BACKUP_DIR -name "momoai_*.tar.gz" -mtime +7 -delete
```

## 성능 최적화

### 1. 워커 프로세스 수 조정
```bash
# CPU 코어 수의 2-4배 권장
gunicorn -w 8 -b 0.0.0.0:5000 app:app
```

### 2. 데이터베이스 최적화
```python
# database.py에 인덱스 추가
cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status)
''')
cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_tasks(status)
''')
```

### 3. 캐싱 설정 (Redis)
```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'redis'})
```

## 문제 해결

### 문제 1: 포트 이미 사용 중
```bash
# 포트 사용 확인
sudo lsof -i :5000

# 프로세스 종료
sudo kill -9 <PID>
```

### 문제 2: 권한 오류
```bash
# 폴더 권한 설정
sudo chown -R your-username:your-username /path/to/momoai_web
sudo chmod -R 755 /path/to/momoai_web
```

### 문제 3: 메모리 부족
```bash
# 스왑 메모리 추가 (Linux)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 스케일링 전략

### 수평 스케일링 (여러 서버)
- 로드 밸런서 (Nginx/HAProxy) 사용
- 공유 파일 시스템 (NFS/S3) 사용
- 중앙 데이터베이스 (PostgreSQL) 사용

### 수직 스케일링 (서버 성능 향상)
- CPU/RAM 증설
- SSD 사용
- 네트워크 대역폭 증가

## 클라우드 배포

### AWS EC2
1. EC2 인스턴스 생성 (Ubuntu 22.04)
2. 보안 그룹 설정 (포트 80, 443, 5000)
3. Elastic IP 할당
4. 위의 프로덕션 설정 적용

### Google Cloud Run
- Dockerfile 기반 배포
- 자동 스케일링
- HTTPS 자동 설정

### Heroku
```bash
# Procfile 생성
web: gunicorn app:app

# 배포
heroku create momoai
heroku config:set ANTHROPIC_API_KEY=your-key
git push heroku main
```

## 유지보수

### 정기 작업
- [ ] 로그 파일 정리 (주간)
- [ ] 디스크 사용량 확인 (주간)
- [ ] 백업 확인 (일간)
- [ ] 보안 업데이트 (월간)
- [ ] 의존성 패키지 업데이트 (월간)

### 업데이트 절차
1. 백업 수행
2. 새 버전 코드 다운로드
3. 의존성 업데이트 (`pip install -r requirements.txt`)
4. 데이터베이스 마이그레이션 (필요시)
5. 서비스 재시작
6. 테스트 수행

## 연락처

배포 관련 문의: [개발자 이메일]
