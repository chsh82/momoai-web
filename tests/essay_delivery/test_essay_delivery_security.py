"""Security regression matrix through real routes and disposable ORM storage."""
import os
assert os.environ.get('MOMOAI_TEST_MODE') == '1'
import pytest
from conftest import kernel
from test_essay_delivery import data, web, service, token


def test_makeup_eligibility_and_explicit_choice_fail_closed(data):
    from app.models import Course, CourseEnrollment, CourseSession
    from datetime import datetime
    svc = service()
    e = data.essay()
    for session, teacher in [(None,None),('unknown',None),('session-regular','regular'),('session-makeup','stranger')]:
        with pytest.raises(ValueError):
            svc.assign_submission(e,data.student(),mode='makeup',session_id=session,teacher_id=teacher)
        assert (e.user_id,e.course_id,e.session_id) == ('regular','regular',None)
    lesson = data.db.session.get(CourseSession,'session-makeup')
    course = data.db.session.get(Course,'makeup')
    enrollment = data.db.session.get(CourseEnrollment,'e-makeup')
    for obj, field, invalid in [(lesson,'status','cancelled'),(course,'status','cancelled'),
            (course,'is_terminated',True),(enrollment,'status','dropped'),
            (enrollment,'enrolled_at',datetime(2026,6,1)),
            (enrollment,'completed_at',datetime(2026,4,1)),(data.user('makeup'),'is_active',False)]:
        original = getattr(obj,field); setattr(obj,field,invalid); data.db.session.commit()
        assert svc.makeup_choices(data.student()) == [], (field,invalid)
        with pytest.raises(ValueError): svc.assign_submission(e,data.student(),mode='makeup',session_id=lesson.session_id)
        setattr(obj,field,original); data.db.session.commit()
    enrollment.status = 'completed'; course.status='completed'; data.db.session.commit()
    assert len(svc.makeup_choices(data.student())) == 1


@pytest.mark.parametrize('uid,path',[('pupil','/student/essays/new'),('parent','/parent/essays/submit')])
def test_regular_submission_preserved_and_forged_ids_write_nothing(web,uid,path):
    from app.models import Essay,Notification
    web.actor(uid); csrf=token(web.client.get(path))
    base=dict(student_id='s',title='regular HTTP',content='keep',essay_type='basic',csrf_token=csrf)
    before=Essay.query.count()
    for patch in [dict(submission_mode='makeup',makeup_session_id='missing'),
            dict(submission_mode='makeup',makeup_session_id='session-makeup',makeup_teacher_id='regular'),
            dict(teacher_id='stranger'),dict(submission_mode='forged')]:
        assert web.client.post(path,data=dict(base,**patch)).status_code == 400
        assert Essay.query.count() == before
        assert Notification.query.count() == 0
        assert web.deliveries == []
    assert web.client.post(path,data=dict(base,teacher_id='regular')).status_code == 302
    e=Essay.query.filter_by(title='regular HTTP').one()
    assert e.user_id == 'regular' and e.course_id != 'makeup'


def test_parent_relationship_on_get_and_post(web):
    from app.models import Essay
    web.actor('parent'); csrf=token(web.client.get('/parent/essays/submit'))
    assert web.client.get('/parent/essays/submit?student_id=other').status_code == 403
    before=Essay.query.count()
    response=web.client.post('/parent/essays/submit',data=dict(student_id='other',title='forged',content='forged',
        essay_type='basic',submission_mode='makeup',makeup_session_id='session-makeup',csrf_token=csrf))
    assert response.status_code in (302,403)
    assert Essay.query.count() == before


def forward(web, mode='reference', teacher='reader'):
    web.actor('admin'); csrf=token(web.client.get('/essays/forward?essay_id=one'))
    assert web.client.post('/essays/forward',data=dict(essay_id='one',teacher_id=teacher,mode=mode,
        reason='synthetic forwarding',csrf_token=csrf)).status_code == 302
    return csrf


def test_reference_rejects_every_mutation_including_ocr_and_teacher_assign(web):
    from app.models import OCRHistory
    record=OCRHistory(user_id='reader',original_filename='synthetic.png',image_path='synthetic.png',essay_id='one',extracted_text='OCR')
    web.db.session.add(record); web.db.session.commit()
    forward(web)
    web.actor('reader')
    endpoints=[('POST','/essays/one/regenerate'),('POST','/essays/api/cancel/one'),
        ('POST','/essays/api/regenerate/one'),('POST','/essays/one/finalize'),
        ('GET','/essays/one/manual-correction'),('POST','/essays/one/manual-correction'),
        ('POST','/essays/one/start'),('GET','/essays/ocr/one/from_essay'),
        ('PATCH','/essays/one/update-original-text'),('PATCH','/essays/one/update-essay-type'),
        ('POST','/essays/one/reset'),('DELETE','/essays/one/delete'),
        ('POST',f'/essays/ocr/{record.ocr_id}/add-to-essay'),
        ('POST','/teacher/api/essay/one/assign-session')]
    for method,url in endpoints:
        r=web.client.open(url,method=method,json={'text':'forged','session_id':None})
        assert r.status_code == 403,(method,url,r.status_code)
    assert web.essay().original_text == 'preserve original'
    assert web.essay().user_id == 'regular'


def test_invalid_forward_and_duplicates_never_notify_or_partially_grant(web):
    from app.models import Notification
    from app.models.essay import EssayTeacherGrant
    web.actor('admin'); csrf=token(web.client.get('/essays/forward?essay_id=one'))
    base=dict(essay_id='one',teacher_id='reader',mode='reference',reason='synthetic',csrf_token=csrf)
    for patch,code in [(dict(teacher_id='missing'),400),(dict(teacher_id='parent'),400),
            (dict(reason='  '),400),(dict(mode='all-students'),400),
            (dict(essay_id=['one','missing']),404),(dict(csrf_token='forged'),400),
            (dict(csrf_token=''),400)]:
        assert web.client.post('/essays/forward',data=dict(base,**patch)).status_code == code
        assert EssayTeacherGrant.query.count() == 0 and Notification.query.count() == 0
    assert web.client.post('/essays/forward',data=base).status_code == 302
    assert web.client.post('/essays/forward',data=base).status_code == 302
    assert EssayTeacherGrant.query.count() == 1 and Notification.query.count() == 1
    assert web.deliveries == []  # persistent in-app notification only
    grant=EssayTeacherGrant.query.one()
    for uid in ['reader','regular','makeup','pupil','parent','stranger']:
        web.actor(uid)
        assert web.client.get('/essays/forward?essay_id=one').status_code == 403
        assert web.client.post('/essays/forward',data=base).status_code == 403
        assert web.client.post('/essays/grants/'+grant.grant_id+'/revoke',data=base).status_code == 403
    assert EssayTeacherGrant.query.count() == 1 and Notification.query.count() == 1


def test_read_only_list_has_no_correction_cta(web):
    forward(web)
    web.actor('reader')
    page=web.client.get('/essays/')
    assert page.status_code == 200
    assert '/essays/one/start' not in page.get_data(as_text=True)
    assert '열람/참고 전용' in page.get_data(as_text=True)
    from bs4 import BeautifulSoup
    submission=web.client.get('/essays/one/view_submission')
    soup=BeautifulSoup(submission.data,'html.parser')
    assert not soup.select('button[onclick="openResetModal()"],button[onclick="toggleTextEditor()"],form#startCorrectionForm')
    assert '열람/참고 전용' in submission.get_data(as_text=True)


def test_revoked_teacher_cannot_read_linked_ocr_records(web):
    from app.models import OCRHistory
    from app.models.essay import EssayTeacherGrant
    csrf=forward(web,mode='correction',teacher='reader')
    record=OCRHistory(user_id='reader',original_filename='synthetic.png',image_path='synthetic.png',essay_id='one',extracted_text='SENSITIVE OCR')
    web.db.session.add(record); web.db.session.commit()
    grant=EssayTeacherGrant.query.one()
    assert web.client.post('/essays/grants/'+grant.grant_id+'/revoke',data=dict(csrf_token=csrf,reason='회수')).status_code == 302
    web.actor('reader')
    assert web.client.get(f'/essays/ocr/{record.ocr_id}/status').status_code == 403
    assert web.client.get(f'/essays/ocr/result/{record.ocr_id}').status_code == 403
    assert 'synthetic.png' not in web.client.get('/essays/ocr/history').get_data(as_text=True)
    assert 'synthetic.png' not in web.client.get('/essays/ocr').get_data(as_text=True)


def test_owner_cannot_link_cancelled_lesson(web):
    from app.models import CourseSession
    web.db.session.get(CourseSession,'session-regular').status='cancelled'
    web.db.session.commit(); web.actor('regular')
    assert web.client.post('/teacher/api/essay/one/assign-session',json={'session_id':'session-regular'}).status_code == 400
    assert web.essay().session_id is None


def test_forward_preserves_all_original_data_and_shared_results_attachments_revoke(web):
    from app.models.essay import EssayVersion,EssayResult,CorrectionAttachment,EssayGuideAttachment,EssayTeacherGrant
    import sqlalchemy as sa
    from pathlib import Path
    upload=Path(web.app.config['UPLOAD_FOLDER']); upload.mkdir(exist_ok=True)
    source=upload/'only-this-essay.txt'; source.write_text('SYNTHETIC attachment',encoding='utf-8')
    e=web.essay(); e.attachment_filename='only-this-essay.txt'; e.attachment_path='only-this-essay.txt'
    e.status='completed'; e.is_finalized=True
    report=Path(web.app.config['HTML_FOLDER']); report.mkdir(exist_ok=True)
    report_file=report/'one-report.html'; report_file.write_text('<p>SYNTHETIC result</p>',encoding='utf-8')
    v=EssayVersion(version_id='version-one',essay_id='one',version_number=1,html_content='<p>SYNTHETIC result</p>',html_path=str(report_file))
    web.db.session.add(v); web.db.session.flush()
    web.db.session.add(EssayResult(essay_id='one',version_id=v.version_id,total_score=83,final_grade='A'))
    web.db.session.add(CorrectionAttachment(attachment_id='a-one',essay_id='one',original_filename='only-this-essay.txt',stored_filename='only-this-essay.txt',file_path=str(source),file_type='image'))
    web.db.session.add(EssayGuideAttachment(attachment_id='guide-one',essay_id='one',original_filename='private-guide.txt',stored_filename='private-guide.txt',file_path=str(source),file_type='image'))
    web.db.session.commit()
    names=['essays','essay_versions','essay_results','correction_attachments','essay_guide_attachments']
    before={n:web.db.session.execute(sa.select(web.t[n])).all() for n in names}
    csrf=forward(web)
    for n in names: assert web.db.session.execute(sa.select(web.t[n])).all() == before[n]
    assert source.read_text(encoding='utf-8') == 'SYNTHETIC attachment'
    grant=EssayTeacherGrant.query.one()
    web.actor('reader')
    for url in ['/essays/one/report-frame','/essays/one/version/1','/essays/one/view_submission',
            '/essays/download/one','/essays/correction-attachment/a-one','/essays/result/one']:
        response=web.client.get(url)
        assert response.status_code == 200,url
    assert web.client.delete('/essays/guide-attachment/guide-one').status_code == 403
    assert web.client.post('/essays/one/select-excellent').status_code == 403
    result=web.client.get('/essays/result/one').get_data(as_text=True)
    assert '열람/참고 전용' in result
    assert '<form method="POST"' not in result
    web.actor('admin'); csrf=token(web.client.get('/essays/forward?essay_id=one'))
    assert web.client.post('/essays/grants/'+grant.grant_id+'/revoke',data=dict(csrf_token=csrf,reason='회수')).status_code == 302
    web.actor('reader')
    assert web.client.get('/essays/one/report-frame').status_code == 403
    assert web.client.get('/essays/download/one').status_code != 200
    assert web.client.get('/essays/correction-attachment/a-one').status_code != 200
    for n in names: assert web.db.session.execute(sa.select(web.t[n])).all() == before[n]
