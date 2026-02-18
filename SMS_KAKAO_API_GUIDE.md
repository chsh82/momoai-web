# SMS 및 카카오톡 메시지 발송 API 연동 가이드

## 📋 개요

결제 내역 페이지에서 SMS 문자 및 카카오톡 메시지를 발송할 수 있는 기능이 구현되었습니다.
현재는 **시뮬레이션 모드**로 작동하며, 실제 메시지는 발송되지 않고 콘솔에만 출력됩니다.

실제 메시지를 발송하려면 아래 가이드를 따라 API를 연동해야 합니다.

---

## 🚀 현재 구현된 기능

### 1. UI 기능
- ✅ 결제 내역 테이블에 "메시지" 열 추가
- ✅ 각 결제 항목마다 "SMS", "카톡" 버튼 추가
- ✅ 버튼 클릭 시 메시지 작성 모달 표시
- ✅ 자동 메시지 템플릿 생성 (학생명, 수업명, 금액, 납부기한 등)
- ✅ 실시간 글자 수 카운트
- ✅ 발송 확인 절차

### 2. 백엔드 기능
- ✅ `/admin/api/payments/<payment_id>/message-info` - 결제 정보 조회 API
- ✅ `/admin/api/payments/<payment_id>/send-message` - 메시지 발송 API
- ✅ `send_sms_message()` 함수 (현재 시뮬레이션 모드)
- ✅ `send_kakao_message()` 함수 (현재 시뮬레이션 모드)

### 3. 메시지 템플릿
자동 생성되는 메시지 형식:
```
[MOMOAI 결제 안내]

학생: 홍길동
수업: 초3 프리미엄 월 16:00 - 김선생님
결제 유형: 월별 (4회)
결제 금액: 260,000원
할인: 52,000원
납부 기한: 2026-02-28
결제 방법: 카드

감사합니다.
```

---

## 📱 SMS API 연동 가이드

### 추천 SMS 서비스

#### 1. **알리고 (Aligo)** ⭐ 추천
- 웹사이트: https://smartsms.aligo.in/
- 특징: 저렴한 요금, 간단한 API, 한국어 지원 우수
- 가격: SMS 건당 15원~20원
- API 문서: https://smartsms.aligo.in/admin/api/spec.html

**연동 방법:**

1. **회원가입 및 API 키 발급**
   - 알리고 사이트 회원가입
   - [마이페이지] > [API 키 관리]에서 API 키 발급
   - 발신번호 등록 (본인인증 필요)

2. **환경 변수 설정**
   ```bash
   # Windows (CMD)
   set SMS_API_KEY=your_api_key_here
   set SMS_USER_ID=your_user_id_here
   set SMS_SENDER=02-1234-5678

   # Windows (PowerShell)
   $env:SMS_API_KEY="your_api_key_here"
   $env:SMS_USER_ID="your_user_id_here"
   $env:SMS_SENDER="02-1234-5678"

   # Linux/Mac
   export SMS_API_KEY=your_api_key_here
   export SMS_USER_ID=your_user_id_here
   export SMS_SENDER=02-1234-5678
   ```

3. **requirements.txt에 추가**
   ```
   requests>=2.28.0
   ```

4. **코드 수정** (`app/admin/routes.py`의 `send_sms_message` 함수)

   현재 코드:
   ```python
   def send_sms_message(phone, message):
       # 개발 모드: 콘솔에 출력만 하고 성공 반환
       print(f"[SMS 발송 시뮬레이션]")
       print(f"수신자: {phone}")
       print(f"내용:\n{message}")
       print("-" * 50)
       return True  # 개발 모드: 항상 성공 반환
   ```

   실제 API 연동 코드:
   ```python
   def send_sms_message(phone, message):
       """알리고 SMS API 연동"""
       import requests
       from flask import current_app

       api_key = current_app.config.get('SMS_API_KEY')
       user_id = current_app.config.get('SMS_USER_ID')
       sender = current_app.config.get('SMS_SENDER')

       if not api_key or not user_id or not sender:
           print("SMS API 설정이 필요합니다.")
           return False

       url = 'https://apis.aligo.in/send/'
       data = {
           'key': api_key,
           'user_id': user_id,
           'sender': sender,
           'receiver': phone,
           'msg': message,
           'msg_type': 'SMS',  # SMS: 단문(90자), LMS: 장문(2000자)
           'title': 'MOMOAI 결제 안내'  # LMS 사용 시 제목
       }

       try:
           response = requests.post(url, data=data, timeout=10)
           result = response.json()

           if result.get('result_code') == '1':
               print(f"✅ SMS 발송 성공: {phone}")
               return True
           else:
               print(f"❌ SMS 발송 실패: {result.get('message')}")
               return False
       except Exception as e:
           print(f"❌ SMS 발송 오류: {str(e)}")
           return False
   ```

#### 2. **네이버 클라우드 플랫폼 SENS**
- 웹사이트: https://www.ncloud.com/product/applicationService/sens
- 특징: 안정적, 대량 발송에 유리
- 가격: SMS 건당 9원~15원

#### 3. **NHN Cloud SMS**
- 웹사이트: https://www.toast.com/kr/service/notification/sms
- 특징: 카카오 계열, 다양한 부가 서비스

---

## 💬 카카오톡 API 연동 가이드

### 카카오톡 비즈니스 메시지 종류

1. **알림톡 (Alimtalk)** ⭐ 추천
   - 카카오톡 채널을 통한 공식 메시지
   - 템플릿 사전 등록 필요
   - 높은 도달률, 신뢰도
   - 가격: 건당 6원~9원

2. **친구톡 (Friendtalk)**
   - 카카오톡 채널 친구에게만 발송
   - 자유 형식 메시지
   - 가격: 건당 15원~20원

### 연동 방법 (알리고 카카오톡 API 사용)

#### 1. **카카오톡 채널 개설**
1. 카카오톡 채널 관리자센터 접속: https://center-pf.kakao.com/
2. 새 채널 만들기 (예: "MOMOAI 학원")
3. 채널 정보 입력 및 승인 대기

#### 2. **알림톡 템플릿 등록**
1. 알리고 카카오톡 서비스 신청: https://kakaoapi.aligo.in/
2. 템플릿 등록 (예시):
   ```
   템플릿명: 결제안내
   템플릿 코드: payment_notice

   내용:
   [MOMOAI 결제 안내]

   학생: #{student_name}
   수업: #{course_name}
   결제 유형: #{payment_type}
   결제 금액: #{amount}원
   납부 기한: #{due_date}
   결제 방법: #{payment_method}

   감사합니다.
   ```

3. 카카오 심사 승인 대기 (1~3일)

#### 3. **환경 변수 설정**
```bash
set KAKAO_API_KEY=your_kakao_api_key
set KAKAO_USER_ID=your_user_id
set KAKAO_SENDER_KEY=your_sender_key
```

#### 4. **코드 수정** (`app/admin/routes.py`의 `send_kakao_message` 함수)

```python
def send_kakao_message(phone, message):
    """알리고 카카오톡 알림톡 API 연동"""
    import requests
    from flask import current_app

    api_key = current_app.config.get('KAKAO_API_KEY')
    user_id = current_app.config.get('KAKAO_USER_ID')
    sender_key = current_app.config.get('KAKAO_SENDER_KEY')

    if not api_key or not user_id or not sender_key:
        print("카카오톡 API 설정이 필요합니다.")
        return False

    # 템플릿 사용 시 (알림톡)
    url = 'https://kakaoapi.aligo.in/akv10/alimtalk/send/'

    # 메시지에서 데이터 파싱 (간단한 예시)
    # 실제로는 payment 객체에서 직접 데이터를 가져오는 것이 더 좋습니다
    data = {
        'apikey': api_key,
        'userid': user_id,
        'senderkey': sender_key,
        'tpl_code': 'payment_notice',  # 등록한 템플릿 코드
        'sender': '02-1234-5678',  # 발신번호
        'receiver_1': phone,
        'subject_1': 'MOMOAI 결제 안내',
        'message_1': message,
        # 템플릿 변수가 있다면:
        # 'student_name_1': student_name,
        # 'course_name_1': course_name,
        # 'amount_1': amount,
        # ...
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        result = response.json()

        if result.get('code') == '0':
            print(f"✅ 카카오톡 발송 성공: {phone}")
            return True
        else:
            print(f"❌ 카카오톡 발송 실패: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 카카오톡 발송 오류: {str(e)}")
        return False
```

---

## 🔧 테스트 방법

### 1. 시뮬레이션 모드 테스트 (현재 상태)
1. 결제 내역 페이지 접속: http://localhost:5000/admin/payments
2. 임의의 결제 항목에서 "SMS" 또는 "카톡" 버튼 클릭
3. 메시지 내용 확인 및 수정
4. "발송하기" 클릭
5. 콘솔 창에서 발송 시뮬레이션 로그 확인

### 2. 실제 API 테스트
1. API 키 발급 및 환경 변수 설정
2. 코드 수정 (위의 가이드 참고)
3. 서버 재시작: `python run.py`
4. 본인 전화번호로 테스트 발송
5. 메시지 수신 확인

### 3. 주의사항
- ⚠️ **발신번호 등록**: 본인 명의의 전화번호만 발신번호로 사용 가능
- ⚠️ **광고성 메시지**: "(광고)" 표기 및 수신거부 방법 명시 필요
- ⚠️ **개인정보 보호**: 학생/학부모 전화번호는 동의 하에만 사용
- ⚠️ **비용 관리**: 잔액 부족 시 발송 실패할 수 있으므로 충전 필요
- ⚠️ **발송 시간**: 야간(21:00~08:00) 발송 자제

---

## 📊 발송 내역 추적 (선택사항)

메시지 발송 내역을 데이터베이스에 기록하려면:

### 1. MessageLog 모델 생성

```python
# app/models/message_log.py
from datetime import datetime
import uuid
from app.models import db

class MessageLog(db.Model):
    """메시지 발송 내역"""
    __tablename__ = 'message_logs'

    log_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = db.Column(db.String(36), db.ForeignKey('payments.payment_id'), nullable=True)

    message_type = db.Column(db.String(20), nullable=False)  # sms, kakao
    recipient_phone = db.Column(db.String(20), nullable=False)
    recipient_name = db.Column(db.String(100), nullable=True)

    message_content = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    error_message = db.Column(db.Text, nullable=True)

    sent_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    # API 응답 정보
    api_response = db.Column(db.Text, nullable=True)
    cost = db.Column(db.Integer, default=0)  # 발송 비용 (원)

    # Relationships
    payment = db.relationship('Payment', backref='message_logs')
    sender = db.relationship('User', foreign_keys=[sent_by])
```

### 2. 발송 시 로그 기록

```python
# app/admin/routes.py의 send_payment_message 함수에 추가

if success:
    # 로그 기록
    message_log = MessageLog(
        payment_id=payment_id,
        message_type=message_type,
        recipient_phone=phone,
        recipient_name=payment.student.name,
        message_content=message,
        status='success',
        sent_by=current_user.user_id,
        cost=15 if message_type == 'sms' else 6  # 예상 비용
    )
    db.session.add(message_log)
    db.session.commit()
```

---

## 💰 예상 비용

### SMS (알리고 기준)
- 단문 SMS (90자 이내): 15원/건
- 장문 LMS (2000자 이내): 50원/건
- 월 1000건 발송 시: 약 15,000원

### 카카오톡 알림톡 (알리고 기준)
- 알림톡: 6~9원/건
- 친구톡: 15~20원/건
- 월 1000건 발송 시: 약 6,000~9,000원

### 추천 사용 시나리오
- **결제 안내**: 카카오톡 알림톡 (저렴하고 도달률 높음)
- **긴급 공지**: SMS (카카오톡 미설치자 대비)
- **마케팅**: 동의받은 경우에만 발송

---

## 🎯 구현 체크리스트

### 즉시 사용 가능 (API 연동 전)
- ✅ 결제 내역에서 메시지 발송 버튼 사용 가능
- ✅ 메시지 템플릿 자동 생성
- ✅ 시뮬레이션 모드로 메시지 내용 확인
- ✅ 콘솔에서 발송 내역 확인

### API 연동 후 가능
- ⬜ 실제 SMS 문자 발송
- ⬜ 실제 카카오톡 메시지 발송
- ⬜ 발송 성공/실패 알림
- ⬜ 발송 비용 추적

### 선택사항 (향후 추가 가능)
- ⬜ 발송 내역 데이터베이스 저장
- ⬜ 발송 내역 조회 페이지
- ⬜ 대량 발송 기능 (선택한 여러 결제 건 동시 발송)
- ⬜ 예약 발송 기능
- ⬜ 메시지 템플릿 관리 페이지

---

## 📞 지원

### 알리고 고객센터
- 전화: 1600-5044
- 이메일: help@aligo.in
- 카카오톡 상담: @알리고

### 참고 문서
- 알리고 SMS API: https://smartsms.aligo.in/admin/api/spec.html
- 알리고 카카오톡 API: https://kakaoapi.aligo.in/
- 카카오 비즈니스: https://business.kakao.com/

---

## 🔒 보안 주의사항

1. **API 키 관리**
   - API 키는 절대 코드에 직접 입력하지 마세요
   - 환경 변수 또는 .env 파일 사용 (Git에 포함하지 않음)
   - `.gitignore`에 `.env` 추가

2. **개인정보 보호**
   - 학생/학부모 전화번호는 동의 하에만 사용
   - 메시지 발송 내역에 민감 정보 저장 시 암호화 고려
   - 발송 전 수신 동의 확인

3. **남용 방지**
   - 하루 발송량 제한 설정 고려
   - 관리자만 발송 가능하도록 권한 제한 유지
   - 발송 내역 로그 보관

---

## 마무리

현재 메시지 발송 기능의 UI와 기본 구조는 모두 완성되었습니다.
위 가이드를 따라 SMS/카카오톡 API를 연동하면 실제 메시지 발송이 가능합니다.

질문이나 문제가 있으면 해당 API 서비스의 고객센터로 문의하세요!
