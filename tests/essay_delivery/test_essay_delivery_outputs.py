import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
from conftest import kernel
from test_essay_delivery import data, web, service, token
from test_essay_delivery_security import forward


def test_generic_output_download_has_same_per_essay_acl_and_blocks_traversal(web):
    from pathlib import Path
    from app.models.essay import EssayVersion
    assert hasattr(service(),'download_output'), 'generic output endpoint still bypasses essay ACL'
    root=Path(web.app.config['HTML_FOLDER']); root.mkdir(exist_ok=True)
    path=root/'one-report.html'; path.write_text('SYNTHETIC private output',encoding='utf-8')
    web.db.session.add(EssayVersion(essay_id='one',version_number=1,html_path=str(path),html_content='synthetic'))
    web.db.session.commit()
    web.actor('stranger')
    assert web.client.get('/api/download/one-report.html').status_code == 403
    forward(web)
    web.actor('reader')
    response=web.client.get('/api/download/one-report.html')
    assert response.status_code == 200 and response.data == b'SYNTHETIC private output'
    assert web.client.get('/api/download/../one-report.html').status_code in (400,404)
    assert web.client.get('/api/download/missing.html').status_code == 404
    web.actor('pupil')
    assert web.client.get('/api/download/one-report.html').status_code == 403
    e=web.essay(); e.status='completed'; e.is_finalized=True; web.db.session.commit()
    assert web.client.get('/api/download/one-report.html').status_code == 200
    web.actor('parent')
    assert web.client.get('/api/download/one-report.html').status_code == 200


def test_active_correction_replacement_is_unique_audited_and_preserves_essay(web):
    from app.models.essay import EssayTeacherGrant
    from app.models import Notification
    from app.services.essay_delivery import can_correct
    forward(web,mode='correction',teacher='reader')
    forward(web,mode='correction',teacher='makeup')
    grants=EssayTeacherGrant.query.order_by(EssayTeacherGrant.created_at).all()
    assert len(grants)==2
    assert grants[0].revoked_at and grants[0].revoked_by=='admin'
    assert '새 첨삭 담당 이전' in grants[0].revoke_reason
    assert grants[1].revoked_at is None
    assert not can_correct(web.user('reader'),web.essay())
    assert can_correct(web.user('makeup'),web.essay())
    assert web.essay().original_text=='preserve original' and web.essay().user_id=='regular'
    assert Notification.query.count()==2


def test_inactive_recipient_rejected_and_read_grant_does_not_bypass_deactivation(web):
    from app.models import Notification
    from app.models.essay import EssayTeacherGrant
    web.user('reader').is_active=False;web.db.session.commit()
    web.actor('admin'); csrf=token(web.client.get('/essays/forward?essay_id=one'))
    response=web.client.post('/essays/forward',data=dict(essay_id='one',teacher_id='reader',mode='reference',reason='test',csrf_token=csrf))
    assert response.status_code==400
    assert EssayTeacherGrant.query.count()==0 and Notification.query.count()==0
    web.user('reader').is_active=True;web.db.session.commit()
    forward(web)
    web.user('reader').is_active=False;web.db.session.commit()
    from app.services.essay_scope import original_access_query
    assert web.db.session.execute(original_access_query(web.user('reader'),'essay','one')).first() is None
