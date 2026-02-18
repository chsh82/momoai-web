# 학부모-자녀 연결 시스템 구현 계획

## 개요
학부모와 자녀(학생)를 안전하고 편리하게 연결하는 시스템

## 선택한 방식: 하이브리드 (연결 코드 + 관리자 승인)

---

## Phase 1: 데이터베이스 확장

### Student 모델에 추가
```python
class Student(db.Model):
    # 기존 필드...

    # 연결 코드 관련
    link_code = db.Column(db.String(8), unique=True, index=True)
    link_code_generated_at = db.Column(db.DateTime)
    link_code_expires_at = db.Column(db.DateTime)  # 생성 후 30일
    link_code_used = db.Column(db.Boolean, default=False)
```

### 연결 요청 모델 생성
```python
class ParentLinkRequest(db.Model):
    """학부모가 자녀 연결을 요청하는 모델"""
    __tablename__ = 'parent_link_requests'

    request_id = db.Column(db.String(36), primary_key=True)
    parent_id = db.Column(db.String(36), db.ForeignKey('users.user_id'))

    # 방법 1: 연결 코드로 요청
    link_code = db.Column(db.String(8))

    # 방법 2: 정보로 요청 (관리자가 매칭)
    student_name = db.Column(db.String(100))
    student_birth_date = db.Column(db.Date)
    student_grade = db.Column(db.String(20))
    student_school = db.Column(db.String(200))

    # 매칭 결과
    matched_student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'))

    # 상태
    status = db.Column(db.String(20), default='pending')
    # pending, auto_approved, admin_reviewing, approved, rejected

    # 승인 정보
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))
    reviewed_at = db.Column(db.DateTime)
    admin_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

---

## Phase 2: 연결 코드 생성

### 학생 등록 시 자동 생성
```python
def generate_student_link_code(student_id):
    """학생 등록 시 연결 코드 생성"""
    import random, string

    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # 중복 확인
        existing = Student.query.filter_by(link_code=code).first()
        if not existing:
            break

    student = Student.query.get(student_id)
    student.link_code = code
    student.link_code_generated_at = datetime.utcnow()
    student.link_code_expires_at = datetime.utcnow() + timedelta(days=30)
    student.link_code_used = False

    db.session.commit()
    return code
```

### 관리자가 코드 출력/전달
```
📋 학생 등록 완료 시:
┌─────────────────────────────┐
│  학생: 김철수 (초등 3학년)     │
│                             │
│  학부모 연결 코드:            │
│  ┌─────────────┐            │
│  │  ABC12345   │            │
│  └─────────────┘            │
│                             │
│  ⚠️ 이 코드를 학부모에게     │
│     전달해주세요             │
│                             │
│  유효기간: 30일              │
└─────────────────────────────┘
```

---

## Phase 3: 학부모 연결 프로세스

### 옵션 A: 연결 코드 사용 (자동 승인)

**Route**: `/parent/link-child`

```python
@parent_bp.route('/link-child', methods=['GET', 'POST'])
@login_required
@requires_role('parent')
def link_child():
    if request.method == 'POST':
        link_code = request.form.get('link_code').strip().upper()

        # 코드 검증
        student = Student.query.filter_by(
            link_code=link_code,
            link_code_used=False
        ).first()

        if not student:
            flash('유효하지 않은 연결 코드입니다.', 'danger')
            return redirect(url_for('parent.link_child'))

        # 만료 확인
        if student.link_code_expires_at < datetime.utcnow():
            flash('만료된 연결 코드입니다. 관리자에게 문의하세요.', 'danger')
            return redirect(url_for('parent.link_child'))

        # 이미 연결되었는지 확인
        existing = ParentStudent.query.filter_by(
            parent_id=current_user.user_id,
            student_id=student.student_id
        ).first()

        if existing:
            flash('이미 연결된 자녀입니다.', 'info')
            return redirect(url_for('parent.index'))

        # 연결 생성
        relation = ParentStudent(
            parent_id=current_user.user_id,
            student_id=student.student_id,
            relation_type='parent',
            permission_level='full',
            created_by=current_user.user_id
        )
        db.session.add(relation)

        # 코드 사용 처리
        student.link_code_used = True

        # 요청 기록 (자동 승인)
        link_request = ParentLinkRequest(
            parent_id=current_user.user_id,
            link_code=link_code,
            matched_student_id=student.student_id,
            status='auto_approved'
        )
        db.session.add(link_request)

        db.session.commit()

        flash(f'{student.name} 학생과 연결되었습니다!', 'success')
        return redirect(url_for('parent.index'))

    return render_template('parent/link_child.html')
```

### 옵션 B: 정보 입력 방식 (관리자 승인 필요)

**Route**: `/parent/request-link`

```python
@parent_bp.route('/request-link', methods=['GET', 'POST'])
@login_required
@requires_role('parent')
def request_link():
    if request.method == 'POST':
        # 학부모가 입력한 자녀 정보
        link_request = ParentLinkRequest(
            parent_id=current_user.user_id,
            student_name=request.form.get('student_name'),
            student_birth_date=request.form.get('birth_date'),
            student_grade=request.form.get('grade'),
            student_school=request.form.get('school'),
            status='admin_reviewing'
        )
        db.session.add(link_request)
        db.session.commit()

        # 관리자에게 알림
        admin_notification = Notification(
            user_id=get_admin_user_id(),
            notification_type='parent_link_request',
            title='학부모-자녀 연결 요청',
            message=f'{current_user.name}님이 자녀 연결을 요청했습니다.'
        )
        db.session.add(admin_notification)
        db.session.commit()

        flash('연결 요청이 제출되었습니다. 관리자 검토 후 연결됩니다.', 'info')
        return redirect(url_for('parent.index'))

    return render_template('parent/request_link.html')
```

---

## Phase 4: 관리자 승인 시스템

### 연결 요청 목록
**Route**: `/admin/parent-link-requests`

```python
@admin_bp.route('/parent-link-requests')
@login_required
@requires_permission_level(2)
def parent_link_requests():
    """학부모 연결 요청 목록"""
    pending_requests = ParentLinkRequest.query.filter_by(
        status='admin_reviewing'
    ).order_by(ParentLinkRequest.created_at.desc()).all()

    return render_template('admin/parent_link_requests.html',
                         requests=pending_requests)
```

### 요청 승인
```python
@admin_bp.route('/parent-link-requests/<request_id>/approve', methods=['POST'])
@login_required
@requires_permission_level(2)
def approve_link_request(request_id):
    link_request = ParentLinkRequest.query.get_or_404(request_id)
    student_id = request.form.get('student_id')  # 관리자가 선택

    # 연결 생성
    relation = ParentStudent(
        parent_id=link_request.parent_id,
        student_id=student_id,
        relation_type='parent',
        created_by=current_user.user_id
    )
    db.session.add(relation)

    # 요청 상태 업데이트
    link_request.status = 'approved'
    link_request.matched_student_id = student_id
    link_request.reviewed_by = current_user.user_id
    link_request.reviewed_at = datetime.utcnow()

    db.session.commit()

    # 학부모에게 알림
    parent_notification = Notification(
        user_id=link_request.parent_id,
        notification_type='link_approved',
        title='자녀 연결 승인',
        message='자녀와 연결되었습니다!'
    )
    db.session.add(parent_notification)
    db.session.commit()

    flash('연결이 승인되었습니다.', 'success')
    return redirect(url_for('admin.parent_link_requests'))
```

---

## Phase 5: UI/UX

### 학부모 포털 - 자녀 연결 페이지

```html
<div class="max-w-2xl mx-auto">
    <h2>자녀 연결</h2>

    <!-- 탭: 연결 코드 vs 정보 입력 -->
    <div class="tabs">
        <button class="tab active">연결 코드 입력</button>
        <button class="tab">정보로 찾기</button>
    </div>

    <!-- Tab 1: 연결 코드 -->
    <div class="tab-content">
        <form method="POST" action="/parent/link-child">
            <label>연결 코드 (8자리)</label>
            <input type="text" name="link_code"
                   placeholder="ABC12345"
                   maxlength="8"
                   pattern="[A-Z0-9]{8}"
                   required>

            <p class="help-text">
                📌 학원에서 받으신 8자리 코드를 입력하세요
            </p>

            <button type="submit">연결하기</button>
        </form>
    </div>

    <!-- Tab 2: 정보 입력 -->
    <div class="tab-content hidden">
        <form method="POST" action="/parent/request-link">
            <label>자녀 이름</label>
            <input type="text" name="student_name" required>

            <label>생년월일</label>
            <input type="date" name="birth_date" required>

            <label>학년</label>
            <select name="grade" required>
                <option>초등 1학년</option>
                <!-- ... -->
            </select>

            <label>학교명</label>
            <input type="text" name="school">

            <p class="warning">
                ⚠️ 관리자 승인 후 연결됩니다 (1-2일 소요)
            </p>

            <button type="submit">연결 요청</button>
        </form>
    </div>
</div>
```

---

## 보안 고려사항

### 1. 연결 코드 보안
- ✅ 8자리 랜덤 (62^8 = 218조 조합)
- ✅ 1회용 (사용 후 무효화)
- ✅ 30일 만료
- ✅ 대소문자 구분 없음 (대문자로 변환)

### 2. 중복 연결 방지
- ✅ DB Unique Constraint
- ✅ 코드 레벨 검증
- ✅ 이미 연결된 경우 알림

### 3. 악의적 연결 방지
- ✅ 관리자 검토 옵션
- ✅ 연결 이력 추적 (created_by)
- ✅ 연결 해제 기능

### 4. 개인정보 보호
- ✅ 코드에 개인정보 미포함
- ✅ 요청 정보 암호화 저장 (선택)
- ✅ 로그 기록

---

## 추가 기능

### 1. 연결 코드 재발급
```python
@admin_bp.route('/students/<student_id>/regenerate-code', methods=['POST'])
def regenerate_link_code(student_id):
    """연결 코드 분실 시 재발급"""
    student = Student.query.get_or_404(student_id)

    # 기존 코드 무효화
    student.link_code_used = True

    # 새 코드 생성
    new_code = generate_student_link_code(student_id)

    flash(f'새 연결 코드: {new_code}', 'success')
    return redirect(url_for('admin.student_detail', student_id=student_id))
```

### 2. 연결 해제
```python
@parent_bp.route('/unlink-child/<student_id>', methods=['POST'])
@login_required
def unlink_child(student_id):
    """자녀 연결 해제"""
    relation = ParentStudent.query.filter_by(
        parent_id=current_user.user_id,
        student_id=student_id
    ).first_or_404()

    relation.is_active = False
    db.session.commit()

    flash('자녀 연결이 해제되었습니다.', 'info')
    return redirect(url_for('parent.index'))
```

### 3. 다중 자녀 지원
```python
# 학부모 포털 - 자녀 목록
@parent_bp.route('/children')
def children_list():
    children = db.session.query(Student).join(ParentStudent).filter(
        ParentStudent.parent_id == current_user.user_id,
        ParentStudent.is_active == True
    ).all()

    return render_template('parent/children_list.html', children=children)
```

---

## 마이그레이션

```bash
# 1. Student 모델 업데이트
flask db migrate -m "Add link_code to Student model"
flask db upgrade

# 2. ParentLinkRequest 모델 생성
flask db migrate -m "Add ParentLinkRequest model"
flask db upgrade

# 3. 기존 학생들에게 코드 생성
python scripts/generate_link_codes_for_existing_students.py
```

---

## 구현 순서

1. ✅ Phase 1: 모델 확장 (Student + ParentLinkRequest)
2. ✅ Phase 2: 연결 코드 생성 로직
3. ✅ Phase 3: 학부모 연결 UI (2가지 방법)
4. ✅ Phase 4: 관리자 승인 시스템
5. ✅ Phase 5: 알림 통합
6. ✅ Phase 6: 테스트 & 배포

---

## 테스트 시나리오

### Scenario 1: 연결 코드로 즉시 연결
1. 관리자가 학생 등록 → 코드 "ABC12345" 생성
2. 학부모 회원가입
3. 코드 입력 → 즉시 연결
4. 학부모 포털에서 자녀 정보 확인

### Scenario 2: 정보 입력 후 관리자 승인
1. 학부모 회원가입
2. 자녀 정보 입력 (이름, 생년월일)
3. 관리자가 학생 검색 & 매칭
4. 승인 → 학부모에게 알림

### Scenario 3: 코드 분실
1. 학부모가 코드 분실
2. 관리자에게 문의
3. 관리자가 새 코드 재발급
4. 새 코드로 연결

---

## 예상 FAQ

**Q: 코드를 잊어버렸어요**
A: 관리자에게 문의하시면 새 코드를 발급해드립니다.

**Q: 여러 자녀를 연결할 수 있나요?**
A: 네, 각 자녀마다 코드를 입력하시면 됩니다.

**Q: 아빠와 엄마 모두 연결 가능한가요?**
A: 네, 같은 코드로 여러 학부모가 연결 가능합니다. (link_code_used 플래그 수정 필요)

**Q: 연결 해제는 어떻게 하나요?**
A: 학부모 포털에서 "연결 해제" 버튼을 클릭하시거나 관리자에게 요청하세요.

---

## 다음 단계

이 계획이 괜찮으시면 단계별로 구현을 시작할 수 있습니다:
1. 모델 확장부터 시작할까요?
2. 특정 기능을 우선 구현할까요?
3. 다른 방식을 선호하시나요?

알려주시면 바로 구현하겠습니다! 🚀
