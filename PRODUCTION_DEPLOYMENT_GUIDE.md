# MOMOAI v4.1.0 프로덕션 배포 가이드

## 📋 목차
1. [서버 준비](#1-서버-준비)
2. [필수 소프트웨어 설치](#2-필수-소프트웨어-설치)
3. [애플리케이션 설정](#3-애플리케이션-설정)
4. [데이터베이스 설정](#4-데이터베이스-설정)
5. [Nginx 설정](#5-nginx-설정)
6. [SSL/HTTPS 설정](#6-sslhttps-설정)
7. [서비스 시작](#7-서비스-시작)
8. [배포 자동화](#8-배포-자동화)
9. [모니터링 & 유지보수](#9-모니터링--유지보수)

---

## 1. 서버 준비

### 1.1 권장 사양
- **OS**: Ubuntu 22.04 LTS 이상
- **CPU**: 2 코어 이상
- **RAM**: 4GB 이상 (권장 8GB)
- **디스크**: 50GB 이상 SSD
- **도메인**: HTTPS를 위한 도메인 필요

### 1.2 초기 서버 설정

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 방화벽 설정
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# 사용자 생성
sudo adduser momoai
sudo usermod -aG sudo momoai
su - momoai
```

---

## 2. 필수 소프트웨어 설치

### 2.1 Python 3.11+

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

### 2.2 Node.js (CSS 빌드용)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version  # v20.x 확인
npm --version
```

### 2.3 Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 2.4 PostgreSQL (권장 데이터베이스)

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

---

## 3. 애플리케이션 설정

### 3.1 코드 다운로드

```bash
cd /home/momoai
git clone https://github.com/yourusername/momoai_web.git
cd momoai_web
```

### 3.2 가상환경 생성

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3.3 Python 패키지 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-prod.txt
```

### 3.4 Node.js 패키지 설치 & CSS 빌드

```bash
npm install
npm run build:css
```

### 3.5 환경변수 설정

```bash
# 템플릿 복사
cp .env.production.example .env.production

# 환경변수 편집
nano .env.production
```

**필수 설정:**
```bash
SECRET_KEY=your-super-secret-key-minimum-32-characters
DATABASE_URL=postgresql://momoai_user:your_password@localhost:5432/momoai_db
ANTHROPIC_API_KEY=your-api-key
GEMINI_API_KEY=your-api-key
```

### 3.6 로그 디렉토리 생성

```bash
sudo mkdir -p /var/log/momoai
sudo chown momoai:momoai /var/log/momoai
sudo chmod 755 /var/log/momoai
```

---

## 4. 데이터베이스 설정

### 4.1 PostgreSQL 데이터베이스 생성

```bash
sudo -u postgres psql
```

```sql
-- PostgreSQL에서 실행
CREATE DATABASE momoai_db;
CREATE USER momoai_user WITH PASSWORD 'your_strong_password';
ALTER ROLE momoai_user SET client_encoding TO 'utf8';
ALTER ROLE momoai_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE momoai_user SET timezone TO 'Asia/Seoul';
GRANT ALL PRIVILEGES ON DATABASE momoai_db TO momoai_user;
\q
```

### 4.2 데이터베이스 마이그레이션

```bash
cd /home/momoai/momoai_web
source venv/bin/activate
export FLASK_APP=run.py
export FLASK_ENV=production

# 마이그레이션 실행
flask db upgrade
```

### 4.3 초기 데이터 생성 (선택)

```bash
# 관리자 계정 생성 스크립트 실행 (있다면)
python create_admin.py
```

---

## 5. Nginx 설정

### 5.1 설정 파일 복사

```bash
sudo cp nginx_momoai.conf /etc/nginx/sites-available/momoai
```

### 5.2 도메인 수정

```bash
sudo nano /etc/nginx/sites-available/momoai
```

**변경할 내용:**
- `momoai.kr` (이미 설정됨)
- `/home/momoai/momoai_web` → 실제 경로 (필요시 수정)

### 5.3 심볼릭 링크 생성

```bash
sudo ln -s /etc/nginx/sites-available/momoai /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # 기본 사이트 제거
```

### 5.4 설정 테스트 & 재시작

```bash
sudo nginx -t
sudo systemctl restart nginx
```

---

## 6. SSL/HTTPS 설정

### 6.1 Certbot 설치

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 6.2 SSL 인증서 발급

```bash
sudo certbot --nginx -d momoai.kr -d www.momoai.kr
```

**대화형 프롬프트:**
- 이메일 입력
- 약관 동의
- HTTP → HTTPS 리디렉션: Yes

### 6.3 자동 갱신 설정

```bash
# 테스트
sudo certbot renew --dry-run

# Cron 자동 갱신 (이미 설정되어 있음)
sudo systemctl status certbot.timer
```

---

## 7. 서비스 시작

### 7.1 Systemd 서비스 설치

```bash
sudo cp momoai.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 7.2 서비스 시작 & 활성화

```bash
sudo systemctl enable momoai
sudo systemctl start momoai
```

### 7.3 상태 확인

```bash
sudo systemctl status momoai
```

**예상 출력:**
```
● momoai.service - MOMOAI v4.1.0 - AI Essay Correction System
   Loaded: loaded (/etc/systemd/system/momoai.service; enabled)
   Active: active (running)
```

### 7.4 로그 확인

```bash
# 실시간 로그
sudo journalctl -u momoai -f

# 최근 50줄
sudo journalctl -u momoai -n 50
```

---

## 8. 배포 자동화

### 8.1 배포 스크립트 권한 설정

```bash
chmod +x deploy.sh
```

### 8.2 배포 실행

```bash
./deploy.sh
```

**스크립트 동작:**
1. Git Pull (코드 업데이트)
2. 가상환경 활성화
3. 패키지 업데이트
4. CSS 빌드
5. DB 마이그레이션
6. 파일 권한 설정
7. 서비스 재시작
8. 상태 확인

---

## 9. 모니터링 & 유지보수

### 9.1 서비스 관리 명령어

```bash
# 상태 확인
sudo systemctl status momoai

# 시작
sudo systemctl start momoai

# 정지
sudo systemctl stop momoai

# 재시작
sudo systemctl restart momoai

# 재로드 (다운타임 없음)
sudo systemctl reload momoai

# 로그 확인
sudo journalctl -u momoai -f
```

### 9.2 Nginx 관리

```bash
# 설정 테스트
sudo nginx -t

# 재시작
sudo systemctl restart nginx

# 로그 확인
sudo tail -f /var/log/nginx/momoai_access.log
sudo tail -f /var/log/nginx/momoai_error.log
```

### 9.3 데이터베이스 백업

```bash
# PostgreSQL 백업
sudo -u postgres pg_dump momoai_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 복원
sudo -u postgres psql momoai_db < backup_20260218_120000.sql
```

### 9.4 디스크 사용량 확인

```bash
df -h
du -sh /home/momoai/momoai_web/*
```

### 9.5 프로세스 확인

```bash
# Gunicorn 프로세스
ps aux | grep gunicorn

# 메모리 사용량
free -h

# CPU 사용량
top
```

---

## 🔧 문제 해결 (Troubleshooting)

### 서비스가 시작되지 않는 경우

```bash
# 로그 확인
sudo journalctl -u momoai -n 100 --no-pager

# 설정 파일 확인
cat /etc/systemd/system/momoai.service

# 환경변수 확인
sudo -u momoai cat /home/momoai/momoai_web/.env.production
```

### Nginx 502 Bad Gateway

```bash
# Gunicorn이 실행 중인지 확인
sudo systemctl status momoai

# 포트 리스닝 확인
sudo netstat -tulpn | grep 8000

# Nginx 에러 로그
sudo tail -f /var/log/nginx/momoai_error.log
```

### 데이터베이스 연결 오류

```bash
# PostgreSQL 상태 확인
sudo systemctl status postgresql

# 연결 테스트
psql -U momoai_user -d momoai_db -h localhost
```

### CSS가 로드되지 않는 경우

```bash
# CSS 재빌드
cd /home/momoai/momoai_web
npm run build:css

# 파일 권한 확인
ls -la static/css/

# Nginx 캐시 삭제
sudo rm -rf /var/cache/nginx/*
sudo systemctl restart nginx
```

---

## 📊 성능 최적화 체크리스트

배포 후 다음을 확인하세요:

- [ ] **Lighthouse 테스트** (Performance 80+)
- [ ] **PWA 설치 가능** (설치 배너 표시)
- [ ] **HTTPS 작동** (자물쇠 아이콘)
- [ ] **Gzip 압축 활성화** (Response Headers 확인)
- [ ] **정적 파일 캐싱** (Cache-Control 헤더)
- [ ] **Service Worker 등록** (F12 → Application)
- [ ] **오프라인 모드 작동** (Network → Offline)

---

## 🚨 보안 체크리스트

- [ ] **방화벽 설정** (22, 80, 443 포트만 오픈)
- [ ] **SSH 키 인증** (비밀번호 로그인 비활성화)
- [ ] **강력한 비밀번호** (SECRET_KEY, DB 비밀번호)
- [ ] **환경변수 보호** (.env.production 권한 600)
- [ ] **정기 업데이트** (보안 패치 적용)
- [ ] **로그 모니터링** (비정상 접근 탐지)
- [ ] **백업 설정** (매일 자동 백업)

---

## 📞 지원

문제가 발생하면 다음 로그를 확인하세요:

1. **애플리케이션 로그**
   ```bash
   sudo journalctl -u momoai -n 100
   ```

2. **Nginx 로그**
   ```bash
   sudo tail -f /var/log/nginx/momoai_error.log
   ```

3. **Gunicorn 로그**
   ```bash
   sudo tail -f /var/log/momoai/error.log
   ```

---

## 🎉 배포 완료!

**다음 단계:**
1. 브라우저에서 https://momoai.kr 접속
2. Lighthouse 테스트 실행
3. PWA 설치 테스트
4. 모바일 기기에서 확인
5. 모니터링 설정

**축하합니다!** MOMOAI v4.1.0이 성공적으로 배포되었습니다! 🚀

---

*최종 업데이트: 2026-02-18*
*버전: v4.1.0 (PWA Optimized)*
