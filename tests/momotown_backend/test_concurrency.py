"""Real SQLite contention regressions; synchronization never depends on sleeps."""
from concurrent.futures import ThreadPoolExecutor

from test_backend import BASE, identify, payload, post, web
from app.interest_quest import store


def test_attempt_get_reads_committed_snapshot_during_presentation_write(web):
    app, client, _ = web
    created = post(client, '/attempts', payload()).get_json()
    path = BASE + '/attempts/' + created['attempt_id']
    with app.app_context(), store.connection() as writer:
        writer.execute('INSERT INTO presentations VALUES (?,?,?,?,?)',
                       (created['attempt_id'], created['analysis_revision'],
                        created['presented_villages'][0], 'intro', store.now()))
        # The transaction really has an uncommitted write and retains its lock
        # until the GET completes. A timeout/retry cannot make this test pass.
        assert writer.in_transaction
        with ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(client.get, path).result(timeout=5)
        assert response.status_code == 200
        assert response.get_json() == created
    restored = client.get(path)
    assert restored.status_code == 200
    assert restored.get_json()['presentations'] == [
        dict(domain_id=created['presented_villages'][0], shown_sections=['intro'])]


def test_admin_lookup_reads_committed_cohort_during_attempt_write(web):
    app, client, _ = web
    created = post(client, '/attempts', payload()).get_json()
    identify(client, 'admin')
    with app.app_context(), store.connection() as writer:
        writer.execute('UPDATE attempts SET origin=? WHERE attempt_id=?',
                       ('ADMIN_PREVIEW', created['attempt_id']))
        with ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(client.get, BASE + '/feedback.json').result(timeout=5)
        assert response.status_code == 200
        assert response.get_json()['summary']['attempts'] == 1
        assert response.get_json()['rows'][0]['attempt_id'] == created['attempt_id']
    assert client.get(BASE + '/feedback.json').get_json()['summary']['attempts'] == 0


def test_contending_write_stays_bounded_and_does_not_partially_acknowledge(web):
    app, client, _ = web
    created = post(client, '/attempts', payload()).get_json()
    path = '/attempts/' + created['attempt_id']
    body = dict(analysis_revision=created['analysis_revision'],
                domain_id=created['presented_villages'][0], sections=['intro', 'study'])
    with app.app_context(), store.connection() as writer:
        writer.execute('UPDATE attempts SET snapshot=snapshot WHERE attempt_id=?',
                       (created['attempt_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            response = pool.submit(post, client, path + '/presentation', body).result(timeout=5)
        assert response.status_code == 503
        assert writer.execute('SELECT COUNT(*) FROM presentations').fetchone()[0] == 0
    assert client.get(BASE + path).get_json()['presentations'] == []
    assert post(client, path + '/presentation', body).status_code == 200
    assert client.get(BASE + path).get_json()['presentations'] == [
        dict(domain_id=body['domain_id'], shown_sections=['intro', 'study'])]
