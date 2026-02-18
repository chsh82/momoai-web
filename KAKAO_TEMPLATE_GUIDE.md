# 카카오톡 알림톡 템플릿 가이드 (앱 없이 웹 링크 사용)

## 📱 현재 상황

- ✅ 웹사이트: 있음
- ❌ 안드로이드 앱: 없음
- ❌ iOS 앱: 없음

**결론: 웹 링크만으로 충분히 작동 가능합니다!**

---

## 🎯 추천 방법: 웹 링크 사용

앱이 없어도 카카오톡 알림톡에서 웹 링크를 사용하면 모바일 브라우저로 결제 페이지가 열립니다.

### 장점
- ✅ 즉시 사용 가능
- ✅ 앱 개발 불필요
- ✅ 모든 기기에서 작동 (안드로이드, iOS, PC)
- ✅ 나중에 앱 출시 시 앱링크 추가 가능

### 작동 방식
1. 사용자가 카카오톡 메시지의 "결제하기" 버튼 클릭
2. 모바일 브라우저가 자동으로 열림
3. 결제 페이지로 이동
4. 결제 진행

---

## 📋 카카오톡 알림톡 템플릿 예시

### 템플릿 1: 결제 안내 메시지

**템플릿 정보**
- 템플릿 코드: `payment_notice`
- 템플릿명: 결제 안내
- 카테고리: 정보성 메시지

**메시지 내용**
```
[MOMOAI 결제 안내]

학생: #{student_name}
수업: #{course_name}
결제 유형: #{payment_period}
결제 금액: #{amount}원
납부 기한: #{due_date}

아래 버튼을 눌러 결제해주세요.
감사합니다.
```

**버튼 설정**
```
버튼 1:
- 버튼명: 결제하기
- 버튼 타입: 웹링크 (WL)
- PC 웹링크: #{payment_url}
- 모바일 웹링크: #{payment_url}
```

**변수 목록**
```
#{student_name} - 학생 이름 (예: 홍길동)
#{course_name} - 수업명 (예: 초3 프리미엄 월 16:00)
#{payment_period} - 결제 주기 (예: 월별 (4회))
#{amount} - 결제 금액 (예: 260,000)
#{due_date} - 납부 기한 (예: 2026-02-28)
#{payment_url} - 결제 페이지 URL (예: https://momoai.com/parent/payments/123)
```

---

### 템플릿 2: 결제 완료 확인

**템플릿 정보**
- 템플릿 코드: `payment_completed`
- 템플릿명: 결제 완료
- 카테고리: 거래 완료

**메시지 내용**
```
[MOMOAI 결제 완료]

학생: #{student_name}
결제 금액: #{amount}원
결제 방법: #{payment_method}
결제 일시: #{paid_at}

결제가 완료되었습니다.
감사합니다.
```

**버튼 설정**
```
버튼 1:
- 버튼명: 영수증 보기
- 버튼 타입: 웹링크 (WL)
- PC 웹링크: #{receipt_url}
- 모바일 웹링크: #{receipt_url}
```

---

### 템플릿 3: 결제 기한 임박

**메시지 내용**
```
[MOMOAI 결제 기한 안내]

학생: #{student_name}
결제 금액: #{amount}원
납부 기한: #{due_date}

결제 기한이 #{days_left}일 남았습니다.
기한 내 결제 부탁드립니다.
```

**버튼 설정**
```
버튼 1:
- 버튼명: 결제하기
- 버튼 타입: 웹링크 (WL)
- PC 웹링크: #{payment_url}
- 모바일 웹링크: #{payment_url}
```

---

## 🔗 결제 페이지 URL 생성 방법

### 1. 부모 포털 결제 상세 페이지

현재 시스템에 결제 상세 페이지가 있다면:

```python
# payment_id로 URL 생성
payment_url = f"https://yourdomain.com/parent/payments/{payment_id}"

# 또는 Flask url_for 사용 (외부 URL)
from flask import url_for
payment_url = url_for('parent.payment_detail', payment_id=payment_id, _external=True)
```

### 2. 결제 상세 페이지가 없다면 생성 필요

`app/parent_portal/routes.py`에 추가:

```python
@parent_bp.route('/payments/<payment_id>')
@login_required
@requires_role('parent', 'admin')
def payment_detail(payment_id):
    """결제 상세 페이지"""
    payment = Payment.query.get_or_404(payment_id)

    # 본인 자녀의 결제인지 확인
    if not current_user.is_admin:
        parent_students = ParentStudent.query.filter_by(
            parent_id=current_user.user_id,
            is_active=True
        ).all()
        student_ids = [ps.student_id for ps in parent_students]

        if payment.student_id not in student_ids:
            flash('권한이 없습니다.', 'error')
            return redirect(url_for('parent.index'))

    return render_template('parent/payment_detail.html', payment=payment)
```

템플릿 `templates/parent/payment_detail.html`:
```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold mb-6">결제 상세</h2>

    <div class="bg-white rounded-lg shadow p-6">
        <div class="mb-6">
            <h3 class="font-semibold text-lg mb-4">결제 정보</h3>
            <div class="space-y-2">
                <p><strong>학생:</strong> {{ payment.student.name }}</p>
                <p><strong>수업:</strong> {{ payment.course.course_name }}</p>
                <p><strong>금액:</strong> {{ "{:,}".format(payment.amount) }}원</p>
                <p><strong>납부 기한:</strong> {{ payment.due_date.strftime('%Y-%m-%d') }}</p>
                <p><strong>상태:</strong>
                    {% if payment.status == 'completed' %}
                    <span class="text-green-600">완료</span>
                    {% elif payment.status == 'pending' %}
                    <span class="text-yellow-600">대기</span>
                    {% endif %}
                </p>
            </div>
        </div>

        {% if payment.status == 'pending' %}
        <div class="border-t pt-6">
            <h3 class="font-semibold text-lg mb-4">결제 방법 선택</h3>
            <div class="space-y-3">
                <button class="w-full bg-yellow-400 hover:bg-yellow-500 text-gray-800 font-medium py-3 rounded-lg">
                    카카오페이로 결제
                </button>
                <button class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg">
                    신용카드 결제
                </button>
                <button class="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-3 rounded-lg">
                    계좌이체
                </button>
            </div>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

---

## 💻 카카오톡 발송 코드 구현

### 웹 링크 기반 알림톡 발송

`app/admin/routes.py`의 `send_kakao_message` 함수 수정:

```python
def send_kakao_message(phone, message, payment_id=None):
    """알리고 카카오톡 알림톡 발송 (웹 링크 사용)"""
    import requests
    from flask import current_app, url_for

    api_key = current_app.config.get('KAKAO_API_KEY')
    user_id = current_app.config.get('KAKAO_USER_ID')
    sender_key = current_app.config.get('KAKAO_SENDER_KEY')

    if not api_key or not user_id or not sender_key:
        print("⚠️ 카카오톡 API 설정이 필요합니다. 시뮬레이션 모드로 작동합니다.")
        print(f"[카카오톡 발송 시뮬레이션]")
        print(f"수신자: {phone}")
        print(f"내용:\n{message}")

        # payment_id가 있으면 결제 URL 생성 (시뮬레이션)
        if payment_id:
            payment_url = url_for('parent.payment_detail', payment_id=payment_id, _external=True)
            print(f"결제 URL: {payment_url}")

        print("-" * 50)
        return True

    # 결제 URL 생성
    payment_url = ""
    if payment_id:
        # 실제 도메인으로 변경 필요
        payment_url = f"https://yourdomain.com/parent/payments/{payment_id}"
        # 또는: url_for('parent.payment_detail', payment_id=payment_id, _external=True)

    # 알리고 카카오톡 API 호출
    url = 'https://kakaoapi.aligo.in/akv10/alimtalk/send/'

    # 결제 정보 가져오기 (message 파싱 대신 DB에서 직접)
    from app.models import Payment
    payment = Payment.query.get(payment_id) if payment_id else None

    if payment:
        data = {
            'apikey': api_key,
            'userid': user_id,
            'senderkey': sender_key,
            'tpl_code': 'payment_notice',  # 등록한 템플릿 코드
            'sender': '1688-8790',
            'receiver_1': phone,
            'subject_1': 'MOMOAI 결제 안내',
            'message_1': message,

            # 템플릿 변수
            'student_name_1': payment.student.name,
            'course_name_1': payment.course.course_name,
            'payment_period_1': '월별 (4회)' if payment.payment_period == 'monthly' else '분기별 (12회)',
            'amount_1': f"{payment.amount:,}",
            'due_date_1': payment.due_date.strftime('%Y-%m-%d') if payment.due_date else '',

            # 버튼 URL
            'button_1': json.dumps({
                'name': '결제하기',
                'type': 'WL',
                'url_mobile': payment_url,
                'url_pc': payment_url
            }, ensure_ascii=False)
        }
    else:
        # payment_id가 없으면 일반 메시지
        data = {
            'apikey': api_key,
            'userid': user_id,
            'senderkey': sender_key,
            'tpl_code': 'general_notice',
            'sender': '1688-8790',
            'receiver_1': phone,
            'subject_1': 'MOMOAI 안내',
            'message_1': message
        }

    try:
        print(f"💬 카카오톡 발송 중... (수신자: {phone})")
        response = requests.post(url, data=data, timeout=10)
        result = response.json()

        print(f"API 응답: {result}")

        if result.get('code') == '0':
            print(f"✅ 카카오톡 발송 성공: {phone}")
            return True
        else:
            error_msg = result.get('message', '알 수 없는 오류')
            print(f"❌ 카카오톡 발송 실패: {error_msg}")
            return False
    except Exception as e:
        print(f"❌ 카카오톡 발송 오류: {str(e)}")
        return False
```

### 발송 API 수정

`send_payment_message` 함수에서 payment_id 전달:

```python
@admin_bp.route('/api/payments/<payment_id>/send-message', methods=['POST'])
@login_required
@requires_permission_level(2)
def send_payment_message(payment_id):
    """결제 메시지 발송 (SMS 또는 카카오톡)"""
    data = request.get_json()
    message_type = data.get('message_type')
    message = data.get('message')
    phone = data.get('phone')

    phone = phone.replace('-', '').replace(' ', '')

    try:
        if message_type == 'sms':
            success = send_sms_message(phone, message)
            type_name = 'SMS 문자'
        elif message_type == 'kakao':
            # payment_id 전달
            success = send_kakao_message(phone, message, payment_id=payment_id)
            type_name = '카카오톡 메시지'
        else:
            return jsonify({'success': False, 'message': '올바르지 않은 메시지 타입입니다.'}), 400

        if success:
            return jsonify({'success': True, 'message': f'{type_name}가 성공적으로 발송되었습니다.'})
        else:
            return jsonify({'success': False, 'message': f'{type_name} 발송에 실패했습니다.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'발송 중 오류: {str(e)}'}), 500
```

---

## 🚀 구현 순서

### 1단계: 템플릿 등록 (알리고 사이트)

1. 알리고 로그인
2. [카카오톡 > 알림톡 관리] 메뉴
3. [템플릿 등록] 클릭
4. 위의 템플릿 예시 입력
5. 심사 요청 (1~3일 소요)

### 2단계: 결제 상세 페이지 생성 (선택)

현재 결제 상세 페이지가 없다면:
- `parent/routes.py`에 라우트 추가
- 템플릿 생성
- 결제 버튼 추가 (카카오페이 등)

### 3단계: 카카오톡 API 설정

```python
# config.py에 추가
KAKAO_API_KEY = os.environ.get('KAKAO_API_KEY') or ''
KAKAO_USER_ID = os.environ.get('KAKAO_USER_ID') or 'aproacademy'
KAKAO_SENDER_KEY = os.environ.get('KAKAO_SENDER_KEY') or ''  # 심사 승인 후 발급
```

### 4단계: 코드 수정

- `send_kakao_message` 함수 업데이트
- `send_payment_message` API에 payment_id 전달
- 테스트

---

## 📱 나중에 앱 출시 시

앱을 만들게 되면 앱링크(딥링크)를 추가할 수 있습니다:

```
버튼 타입: 앱링크 (AL)

안드로이드:
- Package: com.momoai.app
- Scheme: momoai://payments/{payment_id}

iOS:
- Scheme: momoai://payments/{payment_id}

웹 링크 (폴백): https://yourdomain.com/parent/payments/{payment_id}
```

**작동 방식:**
1. 앱 설치됨 → 앱 실행
2. 앱 미설치 → 웹 브라우저 열림

---

## ❓ FAQ

### Q1: 도메인이 없는데요?
**A:** 개발 서버 주소 사용 가능:
- 로컬: `http://localhost:5000` (테스트용)
- ngrok 사용: `https://abc123.ngrok.io`
- 클라우드: AWS, Azure, Naver Cloud 등

### Q2: HTTPS가 필요한가요?
**A:** 카카오톡 버튼 링크는 HTTPS 권장:
- Let's Encrypt로 무료 SSL 인증서 발급
- 클라우드 서비스는 기본 제공

### Q3: 결제 모듈은?
**A:** 나중에 추가 가능:
- 카카오페이 API
- 토스페이먼츠
- NICE페이
- 현재는 "결제 요청" 상태만 표시

### Q4: 템플릿 심사 기준은?
**A:**
- 광고성 문구 금지
- 수신자 개인정보 포함 OK
- 변수명 명확히 표시
- 버튼은 최대 5개

---

## 🎯 결론

**현재 상황에서는 웹 링크만으로 충분합니다!**

1. ✅ 카카오톡 템플릿에 웹 링크 버튼 추가
2. ✅ 부모가 버튼 클릭 → 모바일 브라우저 열림
3. ✅ 결제 페이지에서 결제 진행
4. ✅ 나중에 앱 출시 시 앱링크 추가

앱이 없어도 전혀 문제없습니다! 🚀
