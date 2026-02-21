#!/bin/bash
# MOMOAI v4.1.0 - GCP 초기 서버 설정 스크립트
# 사용법:
#   1. GCP SSH 터미널에서 실행
#   2. curl -fsSL https://raw.githubusercontent.com/your-repo/momoai_web/main/gcp-setup.sh | bash

set -e

echo "=================================="
echo "🚀 MOMOAI GCP 서버 초기 설정"
echo "=================================="

# 1. 시스템 업데이트
echo ""
echo "📦 [1/10] 시스템 업데이트 중..."
sudo apt update
sudo apt upgrade -y

# 2. 타임존 설정
echo ""
echo "⏰ [2/10] 타임존 설정 (Asia/Seoul)..."
sudo timedatectl set-timezone Asia/Seoul

# 3. 호스트네임 설정
echo ""
echo "🏷️  [3/10] 호스트네임 설정..."
sudo hostnamectl set-hostname momoai

# 4. 기본 패키지 설치
echo ""
echo "📦 [4/10] 기본 패키지 설치 중..."
sudo apt install -y \
    git \
    curl \
    wget \
    vim \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release

# 5. Python 3.11 설치
echo ""
echo "🐍 [5/10] Python 3.11 설치 중..."
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Python 3.11을 기본으로 설정
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# 6. Node.js 20.x 설치
echo ""
echo "📦 [6/10] Node.js 20.x 설치 중..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 7. Nginx 설치
echo ""
echo "🌐 [7/10] Nginx 설치 중..."
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# 8. PostgreSQL 설치
echo ""
echo "🗄️  [8/10] PostgreSQL 설치 중..."
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 9. UFW 방화벽 설정
echo ""
echo "🔥 [9/10] 방화벽 설정 중..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 10. momoai 사용자 생성
echo ""
echo "👤 [10/10] momoai 사용자 생성 중..."
if ! id -u momoai > /dev/null 2>&1; then
    sudo adduser --disabled-password --gecos "" momoai
    sudo usermod -aG sudo momoai
    echo "momoai ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/momoai
    echo "✅ momoai 사용자 생성 완료"
else
    echo "ℹ️  momoai 사용자가 이미 존재합니다"
fi

# 설치 확인
echo ""
echo "=================================="
echo "✅ 설치 완료! 버전 확인:"
echo "=================================="
echo "Python: $(python3 --version)"
echo "Node.js: $(node --version)"
echo "npm: $(npm --version)"
echo "Nginx: $(nginx -v 2>&1)"
echo "PostgreSQL: $(sudo -u postgres psql --version)"
echo ""

echo "=================================="
echo "🎉 초기 설정 완료!"
echo "=================================="
echo ""
echo "📋 다음 단계:"
echo "1. momoai 사용자로 전환:"
echo "   sudo su - momoai"
echo ""
echo "2. 코드 다운로드:"
echo "   git clone https://github.com/your-username/momoai_web.git"
echo "   cd momoai_web"
echo ""
echo "3. 배포 진행:"
echo "   ./deploy.sh"
echo ""
