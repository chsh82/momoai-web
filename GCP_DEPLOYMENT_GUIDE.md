# MOMOAI v4.1.0 - GCP 배포 가이드

## 🌟 GCP (Google Cloud Platform) 배포

---

## 📋 목차
1. [GCP 계정 및 프로젝트 설정](#1-gcp-계정-및-프로젝트-설정)
2. [VM 인스턴스 생성](#2-vm-인스턴스-생성)
3. [초기 서버 설정](#3-초기-서버-설정)
4. [애플리케이션 배포](#4-애플리케이션-배포)
5. [DNS 및 SSL 설정](#5-dns-및-ssl-설정)
6. [모니터링 및 관리](#6-모니터링-및-관리)

---

## 1. GCP 계정 및 프로젝트 설정

### 1.1 계정 생성

**무료 크레딧: $300 (약 40만원, 90일)**

```
1. https://cloud.google.com 접속
2. "무료로 시작하기" 클릭
3. Google 계정으로 로그인
4. 국가: 대한민국
5. 결제 정보 등록 (크레딧 소진 후에만 청구)
6. $300 크레딧 자동 적용
```

### 1.2 프로젝트 생성

```
1. GCP Console 접속
2. 상단 프로젝트 선택 → "새 프로젝트"
3. 프로젝트 이름: momoai-project
4. 만들기
```

---

## 2. VM 인스턴스 생성

### 2.1 Compute Engine 활성화

```
왼쪽 메뉴 → Compute Engine → VM 인스턴스
→ "API 사용 설정" 클릭
```

### 2.2 인스턴스 만들기

**기본 설정:**
```
이름: momoai-production
리전: asia-northeast3 (서울)
영역: asia-northeast3-a
```

**머신 구성:**
```
시리즈: E2
머신 유형: e2-medium
  - vCPU: 2
  - 메모리: 4GB
  - 비용: ~$25/월 (무료 크레딧 사용)
```

**부팅 디스크:**
```
운영체제: Ubuntu
버전: Ubuntu 22.04 LTS
부팅 디스크 유형: 표준 영구 디스크
크기: 50GB
```

**방화벽:**
```
✅ HTTP 트래픽 허용
✅ HTTPS 트래픽 허용
```

**네트워킹 (고급):**
```
네트워크 인터페이스 → 외부 IPv4 주소
→ "고정 IP 주소 예약"
→ 이름: momoai-ip
→ 예약
```

### 2.3 방화벽 규칙 추가

```
VPC 네트워크 → 방화벽 → 방화벽 규칙 만들기
```

**SSH (tcp:22)**
```
이름: allow-ssh
소스 IP 범위: 0.0.0.0/0
프로토콜: tcp:22
```

**HTTP (tcp:80)**
```
이름: allow-http
소스 IP 범위: 0.0.0.0/0
프로토콜: tcp:80
```

**HTTPS (tcp:443)**
```
이름: allow-https
소스 IP 범위: 0.0.0.0/0
프로토콜: tcp:443
```

---

## 3. 초기 서버 설정

### 3.1 SSH 접속

**브라우저 SSH (권장):**
```
VM 인스턴스 목록 → momoai-production → SSH 버튼 클릭
```

### 3.2 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.3 타임존 설정

```bash
sudo timedatectl set-timezone Asia/Seoul
date  # 확인
```

### 3.4 호스트네임 설정

```bash
sudo hostnamectl set-hostname momoai
```

### 3.5 Python 3.11 설치

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version  # 확인
```

### 3.6 Node.js 20.x 설치

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version  # 확인
npm --version
```

### 3.7 Nginx 설치

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

### 3.8 PostgreSQL 설치

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql
```

### 3.9 사용자 생성

```bash
# momoai 사용자 생성
sudo adduser momoai
# 비밀번호 입력 및 정보 입력

# sudo 권한 부여
sudo usermod -aG sudo momoai

# 사용자 전환
sudo su - momoai
```

---

## 4. 애플리케이션 배포

### 4.1 코드 다운로드

```bash
cd /home/momoai
git clone https://github.com/your-username/momoai_web.git
cd momoai_web
```

### 4.2 가상환경 생성

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4.3 패키지 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-prod.txt
```

### 4.4 Node.js 패키지 및 CSS 빌드

```bash
npm install
npm run build:css
```

### 4.5 환경변수 설정

```bash
cp .env.production.example .env.production
nano .env.production
```

**필수 설정:**
```bash
SECRET_KEY=your-super-secret-key-minimum-32-characters
DATABASE_URL=postgresql://momoai_user:your_password@localhost:5432/momoai_db
ANTHROPIC_API_KEY=your-api-key
GEMINI_API_KEY=your-api-key
DOMAIN=momoai.kr
```

### 4.6 로그 디렉토리 생성

```bash
sudo mkdir -p /var/log/momoai
sudo chown momoai:momoai /var/log/momoai
```

### 4.7 데이터베이스 설정

```bash
# PostgreSQL 데이터베이스 생성
sudo -u postgres psql

# PostgreSQL에서:
CREATE DATABASE momoai_db;
CREATE USER momoai_user WITH PASSWORD 'your_strong_password';
ALTER ROLE momoai_user SET client_encoding TO 'utf8';
ALTER ROLE momoai_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE momoai_user SET timezone TO 'Asia/Seoul';
GRANT ALL PRIVILEGES ON DATABASE momoai_db TO momoai_user;
\q
```

### 4.8 데이터베이스 마이그레이션

```bash
cd /home/momoai/momoai_web
source venv/bin/activate
export FLASK_APP=run.py
export FLASK_ENV=production
flask db upgrade
```

### 4.9 Nginx 설정

```bash
# 설정 파일 복사
sudo cp nginx_momoai.conf /etc/nginx/sites-available/momoai

# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/momoai /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

### 4.10 Systemd 서비스 설정

```bash
# 서비스 파일 복사
sudo cp momoai.service /etc/systemd/system/

# 서비스 등록
sudo systemctl daemon-reload
sudo systemctl enable momoai
sudo systemctl start momoai

# 상태 확인
sudo systemctl status momoai
```

---

## 5. DNS 및 SSL 설정

### 5.1 고정 IP 확인

```
GCP Console → Compute Engine → VM 인스턴스
→ momoai-production → 외부 IP 복사
```

### 5.2 DNS 레코드 설정

**도메인 관리 페이지에서:**
```
Type: A
Name: @
Value: [GCP 고정 IP]
TTL: 3600

Type: A
Name: www
Value: [GCP 고정 IP]
TTL: 3600
```

### 5.3 DNS 전파 확인

```bash
nslookup momoai.kr
dig momoai.kr
```

### 5.4 SSL 인증서 발급

```bash
# Certbot 설치
sudo apt install -y certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d momoai.kr -d www.momoai.kr

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

---

## 6. 모니터링 및 관리

### 6.1 GCP Monitoring (Stackdriver)

```
GCP Console → Monitoring → Dashboards
→ VM 인스턴스 모니터링 대시보드 생성
```

**모니터링 항목:**
- CPU 사용률
- 메모리 사용률
- 디스크 I/O
- 네트워크 트래픽

### 6.2 로그 확인

```bash
# 애플리케이션 로그
sudo journalctl -u momoai -f

# Nginx 로그
sudo tail -f /var/log/nginx/momoai_access.log
sudo tail -f /var/log/nginx/momoai_error.log
```

### 6.3 백업 설정

**스냅샷 자동 생성:**
```
1. Compute Engine → 디스크
2. momoai-production 부팅 디스크 선택
3. "스냅샷 일정 만들기"
4. 일정: 매일 오전 3시
5. 보관 기간: 7일
```

**데이터베이스 백업:**
```bash
# crontab 편집
crontab -e

# 매일 오전 3시 백업
0 3 * * * /usr/bin/pg_dump -U momoai_user momoai_db > /home/momoai/backups/db_$(date +\%Y\%m\%d).sql
```

### 6.4 자동 재시작 설정

```bash
# 서버 재부팅 시 자동 시작 확인
sudo systemctl is-enabled momoai
sudo systemctl is-enabled nginx
sudo systemctl is-enabled postgresql
```

---

## 💰 예상 비용

### GCP 무료 크레딧
- **무료 크레딧**: $300 (약 40만원)
- **유효 기간**: 90일

### e2-medium 인스턴스
- **월 비용**: ~$25 (약 33,000원)
- **크레딧으로**: 약 12개월 무료
- **이후**: 월 33,000원

### 스토리지
- **50GB SSD**: ~$8/월 (약 10,000원)

### 총 예상 비용
- **처음 12개월**: 무료 (크레딧 사용)
- **이후**: 월 43,000원

---

## 🔧 GCP 특화 팁

### 1. 비용 알림 설정
```
결제 → 예산 및 알림 → 예산 만들기
→ $300 크레딧의 80% 사용 시 알림
```

### 2. 방화벽 태그 사용
```
VM 인스턴스 편집 → 네트워크 태그: momoai-web
방화벽 규칙 → 대상 태그: momoai-web
→ 태그가 있는 인스턴스에만 규칙 적용
```

### 3. Cloud SQL 사용 (고급)
```
PostgreSQL 대신 Cloud SQL for PostgreSQL 사용
→ 자동 백업, 고가용성, 관리 편의성
→ 추가 비용: ~$25/월
```

### 4. Cloud Storage 연동
```
업로드 파일을 Cloud Storage에 저장
→ 확장성, 백업, CDN 연동
```

---

## ✅ 배포 체크리스트

- [ ] GCP 계정 생성 및 $300 크레딧 확인
- [ ] VM 인스턴스 생성 (e2-medium, Seoul)
- [ ] 고정 IP 할당
- [ ] 방화벽 규칙 설정 (22, 80, 443)
- [ ] SSH 접속 성공
- [ ] Python 3.11 설치
- [ ] Node.js 20.x 설치
- [ ] Nginx 설치
- [ ] PostgreSQL 설치
- [ ] 코드 다운로드 및 설정
- [ ] DNS 레코드 설정
- [ ] SSL 인증서 발급
- [ ] 서비스 시작
- [ ] https://momoai.kr 접속 확인
- [ ] Lighthouse 테스트 (80점+)
- [ ] PWA 설치 테스트

---

## 🎉 배포 완료!

**다음 단계:**
1. https://momoai.kr 접속
2. PWA 설치 테스트
3. 모니터링 대시보드 설정
4. 정기 백업 확인

**축하합니다!** MOMOAI v4.1.0이 GCP에 성공적으로 배포되었습니다! 🚀

---

*최종 업데이트: 2026-02-18*
*플랫폼: Google Cloud Platform*
*도메인: momoai.kr*
