"""Durable async fencing regressions; synthetic DB, no LLM/network."""
import importlib.util
from pathlib import Path
import pytest
from conftest import kernel
from test_essay_delivery import data, web, token, service


def queue(web, monkeypatch):
    import app.essays.routes as routes
    tasks = []
    class Deferred:
        def __init__(self, target, **kw): self.target = target
        def start(self): tasks.append(self.target)
    monkeypatch.setattr(routes.threading, 'Thread', Deferred)
    web.actor('regular')
    csrf = token(web.client.get('/essays/one/manual-correction'))
    return tasks, csrf


def cancel_transfer(web, csrf):
    with web.app.app_context():
        assert web.client.post('/essays/api/cancel/one', headers={'X-CSRFToken': csrf}).status_code == 200
        service().forward_essays(web.user('admin'), [web.essay()], web.user('makeup'),
            mode='correction', reason='cancelled generation transferred')
        web.db.session.commit()

def test_queued_cancelled_worker_cannot_run_after_transfer(web, monkeypatch):
    import app.essays.momoai_service as external
    tasks, csrf = queue(web, monkeypatch)
    calls = []
    class Recorder:
        def process_essay(self, *a): calls.append('process')
        def finalize_essay(self, *a): calls.append('finalize')
    monkeypatch.setattr(external, 'MOMOAIService', lambda *a: Recorder())
    assert web.client.post('/essays/one/start', data={'csrf_token': csrf}).status_code == 302
    cancel_transfer(web, csrf)
    tasks[0]()
    assert calls == []
    assert web.essay().status == 'failed'


def test_cancelled_generation_cannot_run_after_same_owner_restart(web, monkeypatch):
    import app.essays.momoai_service as external
    tasks, csrf = queue(web, monkeypatch)
    calls = []
    class Recorder:
        def process_essay(self, *a): calls.append('process')
        def finalize_essay(self, *a): calls.append('finalize')
    monkeypatch.setattr(external, 'MOMOAIService', lambda *a: Recorder())
    assert web.client.post('/essays/one/start', data={'csrf_token': csrf}).status_code == 302
    assert web.client.post('/essays/api/cancel/one', headers={'X-CSRFToken': csrf}).status_code == 200
    assert web.client.post('/essays/one/start', data={'csrf_token': csrf}).status_code == 302
    tasks[0]()
    assert calls == []
    tasks[1]()
    assert calls == ['process', 'finalize']
    tasks[1]()  # duplicate queue delivery must not execute the same generation again
    assert calls == ['process', 'finalize']



def real_service(monkeypatch):
    # web fixture replaces external constructors, but exercise the actual service body.
    path = Path(__file__).resolve().parents[2] / 'app/essays/momoai_service.py'
    spec = importlib.util.spec_from_file_location('real_fenced_momoai', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MOMOAIService.__new__(module.MOMOAIService)


def test_inflight_cancel_transfer_discards_actual_service_result(web, monkeypatch):
    import app.essays.momoai_service as external
    from app.models import EssayVersion, EssayResult
    tasks, csrf = queue(web, monkeypatch)
    svc = real_service(monkeypatch)
    Path(web.app.config['HTML_FOLDER']).mkdir(parents=True, exist_ok=True)
    reached = []
    def delayed_analysis(**kw):
        reached.append(True)
        cancel_transfer(web, csrf)
        return '<html>stale result</html>'
    monkeypatch.setattr(svc, 'analyze_essay_standard', delayed_analysis)
    monkeypatch.setattr(external, 'MOMOAIService', lambda *a: svc)
    response = web.client.post('/essays/one/start', data={'csrf_token': csrf})
    assert response.status_code == 302, response.get_data(as_text=True)
    tasks[0]()
    assert reached == [True]
    web.db.session.expire_all()
    assert web.essay().status == 'failed'
    assert not web.essay().is_finalized
    assert EssayVersion.query.count() == EssayResult.query.count() == 0
    assert not list(Path(web.app.config['HTML_FOLDER']).glob('*.html'))


def test_cancel_invalidates_prepared_regeneration_and_note(web, monkeypatch):
    from app.models.essay import EssayCorrectionJob
    tasks, csrf = queue(web, monkeypatch)
    assert web.client.post('/essays/one/regenerate', data={
        'csrf_token': csrf, 'revision_note': 'durable note'}).status_code == 302
    job = web.db.session.get(EssayCorrectionJob, 'one')
    assert job.state == 'prepared' and job.revision_note == 'durable note'
    cancel_transfer(web, csrf)
    web.db.session.expire_all()
    assert job.state == 'cancelled' and job.revision_note is None
    # Current owner also cannot dispatch a predecessor's cancelled request.
    web.actor('makeup')
    csrf = token(web.client.get('/essays/one/manual-correction'))
    assert web.client.post('/essays/api/regenerate/one', headers={'X-CSRFToken': csrf}).status_code == 409
    assert tasks == []


def test_regenerate_dispatch_is_durable_single_use(web, monkeypatch):
    from app.models.essay import EssayCorrectionJob
    tasks, csrf = queue(web, monkeypatch)
    assert web.client.post('/essays/one/regenerate', data={
        'csrf_token': csrf, 'revision_note': 'survives session reload'}).status_code == 302
    web.db.session.remove()
    from flask import g
    g.pop('_login_user', None)
    assert web.client.post('/essays/api/regenerate/one', headers={'X-CSRFToken': csrf}).status_code == 200
    assert len(tasks) == 1
    assert web.db.session.get(EssayCorrectionJob, 'one').revision_note is None
    web.db.session.remove()
    from flask import g
    g.pop('_login_user', None)
    assert web.client.post('/essays/api/regenerate/one', headers={'X-CSRFToken': csrf}).status_code == 409
    assert len(tasks) == 1


def seed_result(web):
    from app.models import EssayVersion, EssayResult
    e = web.essay()
    v = EssayVersion(essay_id='one', version_number=1, html_content='old result', html_path='old.html')
    web.db.session.add(v)
    web.db.session.flush()
    r = EssayResult(essay_id='one', version_id=v.version_id, html_path='old.html', total_score=42)
    web.db.session.add(r)
    e.status = 'completed'; e.is_finalized = True
    web.db.session.commit()
    return v.version_id


@pytest.mark.parametrize('provider', ['claude', 'gemini'])
def test_inflight_regeneration_cancel_preserves_existing_result(web, monkeypatch, provider):
    import sys
    tasks, csrf = queue(web, monkeypatch)
    old_version = seed_result(web)
    web.essay().api_provider = provider
    web.db.session.commit()
    if provider == 'claude':
        svc = real_service(monkeypatch)
        external = sys.modules['app.essays.momoai_service']
    else:
        from types import ModuleType
        # SDK import is irrelevant: actual generation boundary below is replaced.
        monkeypatch.setitem(sys.modules, 'google.generativeai', ModuleType('google.generativeai'))
        spec = importlib.util.spec_from_file_location('real_fenced_gemini',
            Path(__file__).resolve().parents[2] / 'app/essays/gemini_correction_service.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        svc = mod.GeminiCorrectionService.__new__(mod.GeminiCorrectionService)
        import app.essays.gemini_correction_service as external
        monkeypatch.setattr(svc, '_load_system_prompt', lambda *a: 'synthetic prompt')
    reached = []
    def delayed(*a, **kw):
        reached.append(True)
        cancel_transfer(web, csrf)
        return '<html>obsolete replacement</html>'
    monkeypatch.setattr(svc, 'analyze_essay_standard' if provider == 'claude' else '_call_gemini', delayed)
    monkeypatch.setattr(external, 'MOMOAIService' if provider == 'claude' else 'GeminiCorrectionService', lambda *a: svc)
    assert web.client.post('/essays/one/regenerate', data={
        'csrf_token': csrf, 'revision_note': 'regenerate'}).status_code == 302
    assert web.client.post('/essays/api/regenerate/one', headers={'X-CSRFToken': csrf}).status_code == 200
    tasks[0]()
    assert reached == [True]
    web.db.session.expire_all()
    e = web.essay()
    assert (e.status, e.current_version, e.is_finalized) == ('failed', 1, True)
    assert (e.result.version_id, e.result.html_path, e.result.total_score) == (old_version, 'old.html', 42)
    assert len(e.versions) == 1


def test_inflight_thread_releases_writer_and_cannot_publish_after_cancel(web, monkeypatch):
    import threading
    import app.essays.momoai_service as external
    real_thread = threading.Thread
    tasks, csrf = queue(web, monkeypatch)
    svc = real_service(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    failures = []
    def delayed(**kw):
        entered.set()
        assert release.wait(30), 'test failed to release synthetic inference'
        return '<html>cancelled while in flight</html>'
    monkeypatch.setattr(svc, 'analyze_essay_standard', delayed)
    monkeypatch.setattr(external, 'MOMOAIService', lambda *a: svc)
    assert web.client.post('/essays/one/start', data={'csrf_token': csrf}).status_code == 302
    def run():
        try: tasks[0]()
        except BaseException as exc: failures.append(exc)
    worker = real_thread(target=run)
    worker.start()
    try:
        assert entered.wait(10)
        # Cancellation + ownership transfer must finish BEFORE inference is released.
        cancel_transfer(web, csrf)
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive() and failures == []
    web.db.session.expire_all()
    assert web.essay().status == 'failed'
    assert web.essay().versions == []
    assert not web.essay().is_finalized
