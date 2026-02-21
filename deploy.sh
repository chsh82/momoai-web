#!/bin/bash
# MOMOAI v4.1.0 - 프로덕션 배포 스크립트
# 사용법: ./deploy.sh
# 권한: chmod +x deploy.sh

set -e  # 에러 발생 시 중단

echo "=================================="
echo "🚀 MOMOAI v4.1.0 배포 시작"
echo "=================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 설정
APP_DIR="/home/momoai/momoai_web"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="momoai"

# 1. Git Pull (코드 업데이트)
echo -e "\n${YELLOW}[1/8]${NC} Git 업데이트 중..."
cd $APP_DIR
git pull origin main

# 2. 가상환경 활성화
echo -e "\n${YELLOW}[2/8]${NC} 가상환경 활성화..."
source $VENV_DIR/bin/activate

# 3. 패키지 설치/업데이트
echo -e "\n${YELLOW}[3/8]${NC} Python 패키지 업데이트..."
pip install -r requirements.txt -r requirements-prod.txt --upgrade

# 4. CSS 빌드 (성능 최적화)
echo -e "\n${YELLOW}[4/8]${NC} CSS 빌드 중..."
npm run build:css

# 5. 데이터베이스 마이그레이션
echo -e "\n${YELLOW}[5/8]${NC} 데이터베이스 마이그레이션..."
export FLASK_APP=run.py
export FLASK_ENV=production
flask db upgrade

# 6. 정적 파일 권한 설정
echo -e "\n${YELLOW}[6/8]${NC} 파일 권한 설정..."
chmod -R 755 static
chmod -R 755 uploads

# 7. 서비스 재시작
echo -e "\n${YELLOW}[7/8]${NC} 서비스 재시작..."
sudo systemctl restart $SERVICE_NAME

# 8. 상태 확인
echo -e "\n${YELLOW}[8/8]${NC} 서비스 상태 확인..."
sleep 3
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✅ 배포 완료! 서비스가 정상 작동 중입니다.${NC}"
    sudo systemctl status $SERVICE_NAME --no-pager
else
    echo -e "${RED}❌ 서비스 시작 실패! 로그를 확인하세요:${NC}"
    echo "sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo -e "\n${GREEN}=================================="
echo "🎉 배포 성공!"
echo "==================================${NC}"
echo ""
echo "📊 상태 확인:"
echo "  sudo systemctl status $SERVICE_NAME"
echo ""
echo "📝 로그 확인:"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "🌐 웹사이트:"
echo "  https://momoai.kr"
echo ""
