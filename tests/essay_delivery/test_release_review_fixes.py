"""Behavioral release-blocker regressions; synthetic SQL and real route hooks only."""
from pathlib import Path
import pytest
from conftest import kernel
from test_essay_delivery import data, web, token, service


@pytest.mark.parametrize('kind', ['attachment', 'ocr'])
def test_indirect_mutation_rechecks_owner_after_between_hook_transfer(web, monkeypatch, kind):
    from app.models import OCRHistory
    from app.models.essay import EssayGuideAttachment
    svc = service()
    source = Path(web.app.config['UPLOAD_FOLDER']) / 'private-guide.txt'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('preserve private guide', encoding='utf-8')
    attachment = EssayGuideAttachment(attachment_id='guide', essay_id='one',
        original_filename=source.name, stored_filename=source.name,
        file_path=str(source), file_type='image')
    record = OCRHistory(user_id='regular', essay_id='one', original_filename='ocr.png',
        image_path='synthetic.png', extracted_text='stale OCR')
    web.db.session.add_all([attachment, record])
    web.db.session.commit()
    ocr_id = record.ocr_id
    web.actor('regular')
    csrf = token(web.client.get('/essays/one/manual-correction'))
    original_validate = svc.validate_submission_csrf
    transferred = []
    def transfer_after_first_acl():
        original_validate()
        # This hook runs after the initial ACL check but before the mutex/recheck.
        assert svc.can_correct(web.user('regular'), web.essay())
        svc.forward_essays(web.user('admin'), [web.essay()], web.user('makeup'),
            mode='correction', reason='between-hook synthetic ownership transfer')
        web.db.session.commit()
        transferred.append(True)
    monkeypatch.setattr(svc, 'validate_submission_csrf', transfer_after_first_acl)
    url = '/essays/guide-attachment/guide' if kind == 'attachment' else f'/essays/ocr/{ocr_id}/add-to-essay'
    response = web.client.open(url, method='DELETE' if kind == 'attachment' else 'POST',
        json={'text': 'must not append'}, headers={'X-CSRFToken': csrf})
    assert transferred == [True]
    assert response.status_code == 403, response.get_data(as_text=True)
    web.db.session.expire_all()
    assert web.db.session.get(EssayGuideAttachment, 'guide') is not None
    assert source.read_text(encoding='utf-8') == 'preserve private guide'
    assert web.essay().original_text == 'preserve original'
    assert not svc.can_correct(web.user('regular'), web.essay())


@pytest.mark.parametrize('course_id', [None, 'regular', 'makeup'])
def test_teacher_picker_never_discloses_out_of_scope_essay_metadata(web, course_id):
    from app.models.essay import EssayResult, EssayVersion
    version = EssayVersion(essay_id='one', version_number=1, html_content='private result')
    web.db.session.add(version)
    web.db.session.flush()
    web.db.session.add(EssayResult(essay_id='one', version_id=version.version_id,
        total_score=88, final_grade='A'))
    web.db.session.commit()
    params = {'student_id': 's'}
    if course_id:
        params['course_id'] = course_id
    for uid in ['stranger', 'makeup']:
        web.actor(uid)
        response = web.client.get('/teacher/api/student-essays', query_string=params)
        assert response.status_code == 200
        assert response.get_json() == {'essays': []}, 'picker leaked IDs, metadata or scores'
    web.actor('regular')
    response = web.client.get('/teacher/api/student-essays', query_string={'student_id': 's'})
    assert {e['essay_id'] for e in response.get_json()['essays']} == {'one', 'two'}
    assert next(e for e in response.get_json()['essays'] if e['essay_id'] == 'one')['total_score'] == 88


@pytest.mark.parametrize('inference_fails', [False, True])
def test_reset_fences_inflight_real_service_writes_errors_and_finalization(web, monkeypatch, inference_fails):
    from test_correction_jobs import queue, real_service
    from app.models import EssayVersion, EssayResult
    from app.models.essay import EssayCorrectionJob
    import app.essays.momoai_service as external
    from sqlalchemy import text
    web.db.session.execute(text('ALTER TABLE essays ADD COLUMN error_message TEXT'))
    web.db.session.commit()
    tasks, csrf = queue(web, monkeypatch)
    svc = real_service(monkeypatch)
    output = Path(web.app.config['HTML_FOLDER'])
    output.mkdir(parents=True, exist_ok=True)
    reached = []
    def delayed_analysis(**kw):
        reached.append(True)
        # Independent request session while the real service is in inference.
        with web.app.app_context():
            response = web.client.post('/essays/one/reset', headers={'X-CSRFToken': csrf})
            assert response.status_code == 200, response.get_data(as_text=True)
        if inference_fails:
            raise RuntimeError('obsolete inference error after reset')
        return '<html>obsolete inference result after reset</html>'
    monkeypatch.setattr(svc, 'analyze_essay_standard', delayed_analysis)
    monkeypatch.setattr(external, 'MOMOAIService', lambda *a: svc)
    assert web.client.post('/essays/one/start', data={'csrf_token': csrf}).status_code == 302
    tasks[0]()
    assert reached == [True]
    web.db.session.expire_all()
    essay = web.essay()
    assert essay.status == 'draft'
    assert not essay.is_finalized and essay.finalized_at is None and essay.completed_at is None
    assert web.db.session.execute(text("SELECT error_message FROM essays WHERE essay_id='one'")).scalar() is None
    assert essay.original_text == 'preserve original'
    assert EssayVersion.query.count() == EssayResult.query.count() == 0
    assert not list(output.glob('*.html'))
    assert web.db.session.get(EssayCorrectionJob, 'one').state == 'cancelled'
