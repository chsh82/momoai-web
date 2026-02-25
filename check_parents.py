from app import create_app
from app.models import db, User
from werkzeug.security import generate_password_hash
import uuid

app = create_app()
with app.app_context():
    parents = User.query.filter_by(role='parent').all()
    print(f'학부모 계정 수: {len(parents)}')
    for p in parents[:5]:
        print(f'  이메일: {p.email} | 이름: {p.name} | 활성: {p.is_active}')

    # 테스트 학부모 계정이 없으면 생성
    test_parent = User.query.filter_by(email='parent@test.com').first()
    if not test_parent:
        test_parent = User(
            user_id=str(uuid.uuid4()),
            email='parent@test.com',
            password_hash=generate_password_hash('test1234'),
            name='테스트 학부모',
            role='parent',
            role_level=4,
            is_active=True
        )
        db.session.add(test_parent)
        db.session.commit()
        print('\n테스트 학부모 계정 생성됨:')
        print('  이메일: parent@test.com')
        print('  비밀번호: test1234')
    else:
        print(f'\n기존 테스트 계정 있음: {test_parent.email}')
        print('  비밀번호: test1234 (기존에 설정한 비밀번호 사용)')
