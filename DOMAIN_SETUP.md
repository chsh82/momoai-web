# MOMOAI.KR 도메인 설정 가이드

## 🌐 도메인 정보
- **주 도메인**: momoai.kr
- **서브도메인**: www.momoai.kr
- **프로토콜**: HTTPS (SSL 필수)

---

## 📋 DNS 설정 체크리스트

도메인 등록 업체(가비아, 카페24, AWS Route 53 등)에서 다음 DNS 레코드를 설정하세요:

### A 레코드 (필수)
```
Type: A
Name: @
Value: [서버 IP 주소]
TTL: 3600
```

### A 레코드 (www 서브도메인)
```
Type: A
Name: www
Value: [서버 IP 주소]
TTL: 3600
```

### 대안: CNAME 레코드
```
Type: CNAME
Name: www
Value: momoai.kr
TTL: 3600
```

---

## 🔧 서버 설정 확인

### 1. Nginx 설정
`/etc/nginx/sites-available/momoai` 파일에서 확인:

```nginx
server_name momoai.kr www.momoai.kr;
```

### 2. SSL 인증서 경로
```nginx
ssl_certificate /etc/letsencrypt/live/momoai.kr/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/momoai.kr/privkey.pem;
```

### 3. 환경변수
`.env.production` 파일:

```bash
DOMAIN=momoai.kr
ALLOWED_HOSTS=momoai.kr,www.momoai.kr
```

---

## 🔐 SSL 인증서 발급

### Let's Encrypt (무료, 자동 갱신)

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d momoai.kr -d www.momoai.kr

# 자동 갱신 테스트
sudo certbot renew --dry-run
```

**인증서 위치:**
- 인증서: `/etc/letsencrypt/live/momoai.kr/fullchain.pem`
- 개인키: `/etc/letsencrypt/live/momoai.kr/privkey.pem`
- 체인: `/etc/letsencrypt/live/momoai.kr/chain.pem`

**유효기간:** 90일 (자동 갱신)

---

## ✅ DNS 전파 확인

DNS 설정 후 전파되는 데 시간이 걸립니다:
- **빠름**: 10분 ~ 1시간
- **평균**: 2 ~ 4시간
- **최대**: 24 ~ 48시간

### 확인 방법

**1. 명령어로 확인:**
```bash
# A 레코드 확인
nslookup momoai.kr
dig momoai.kr

# www 확인
nslookup www.momoai.kr
dig www.momoai.kr
```

**2. 온라인 도구:**
- https://dnschecker.org
- https://mxtoolbox.com/DNSLookup.aspx
- https://www.whatsmydns.net

---

## 🚀 배포 후 최종 확인

### 1. HTTP → HTTPS 리디렉션
```bash
curl -I http://momoai.kr
# Location: https://momoai.kr 확인
```

### 2. HTTPS 작동 확인
```bash
curl -I https://momoai.kr
# HTTP/2 200 확인
```

### 3. SSL 인증서 확인
```bash
openssl s_client -connect momoai.kr:443 -servername momoai.kr
# Verify return code: 0 (ok) 확인
```

### 4. 브라우저 테스트
1. https://momoai.kr 접속
2. 주소창에 자물쇠 🔒 아이콘 확인
3. 인증서 정보 확인 (Let's Encrypt)

---

## 📊 성능 테스트

### Lighthouse 테스트
```
1. Chrome DevTools (F12)
2. Lighthouse 탭
3. 도메인: https://momoai.kr
4. Performance + PWA 체크
5. Analyze
```

**목표 점수:**
- Performance: 80+
- PWA: 90+
- Accessibility: 100
- Best Practices: 90+

### SSL Labs 테스트
- https://www.ssllabs.com/ssltest/
- 도메인 입력: momoai.kr
- 목표 등급: A 또는 A+

---

## 🔧 문제 해결

### DNS가 전파되지 않는 경우
1. TTL 값 확인 (3600 이하 권장)
2. DNS 레코드 재설정
3. 로컬 DNS 캐시 삭제:
   ```bash
   # Linux
   sudo systemd-resolve --flush-caches

   # macOS
   sudo dscacheutil -flushcache

   # Windows
   ipconfig /flushdns
   ```

### SSL 인증서 발급 실패
1. DNS가 올바르게 설정되었는지 확인
2. 포트 80, 443이 열려있는지 확인:
   ```bash
   sudo ufw status
   sudo netstat -tulpn | grep :80
   sudo netstat -tulpn | grep :443
   ```
3. Nginx가 실행 중인지 확인:
   ```bash
   sudo systemctl status nginx
   ```

### www 서브도메인이 작동하지 않는 경우
1. DNS CNAME 레코드 확인
2. Nginx server_name에 www.momoai.kr 포함 확인
3. SSL 인증서에 www.momoai.kr 포함 확인

---

## 📝 체크리스트

배포 전 확인사항:

- [ ] DNS A 레코드 설정 (momoai.kr)
- [ ] DNS A 또는 CNAME 레코드 설정 (www.momoai.kr)
- [ ] DNS 전파 완료 확인
- [ ] Nginx 설정 파일 업데이트
- [ ] Let's Encrypt SSL 인증서 발급
- [ ] HTTPS 작동 확인
- [ ] HTTP → HTTPS 리디렉션 확인
- [ ] PWA 설치 배너 테스트
- [ ] Service Worker 등록 확인
- [ ] Lighthouse 테스트 (80점 이상)

---

## 🎯 최종 목표

✅ **https://momoai.kr** 접속 시:
- 자물쇠 아이콘 표시
- PWA 설치 배너 출현
- Performance 80점 이상
- 오프라인 모드 작동

**축하합니다!** 도메인 설정이 완료되었습니다! 🚀

---

*최종 업데이트: 2026-02-18*
*도메인: momoai.kr*
