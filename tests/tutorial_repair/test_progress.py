import pytest
from conftest import complete, Student, PointEvent, TutorialCourseReward


@pytest.mark.parametrize('track,total', [('elem',4), ('mid',9)])
def test_final_lesson_resumes_holes_then_course_done_and_replay(tutorial, track, total):
    app, db, client, Progress = tutorial
    data = complete(client, track=track, course='course2', index=total).get_json()
    assert data['course_done_count'] == 1 and data['course_total'] == total
    assert data['next_lesson_url'].endswith(f'{track}-course2-l1')
    for index in range(1, total):
        data = complete(client, track=track, course='course2', index=index).get_json()
    assert data['course_completed'] is True
    assert data['next_lesson_url'] is None
    # Unlock course2 for the card check without altering the content or gate policy.
    for index in range(1,5):
        complete(client, track=track, index=index)
    html = client.get(f'/tutorial/{track}/').get_data(as_text=True)
    assert f'{total}/{total}' in html
    assert f'href="/tutorial/{track}/course2/{track}-course2-l1"' in html
    assert '완료 · 다시 풀기' in html


def test_duplicate_completion_does_not_inflate_rewards_or_progress(tutorial):
    app, db, client, Progress = tutorial
    db.session.add(Student(student_id='synthetic-student', user_id='pupil'))
    db.session.commit()
    for index in range(1,5):
        data = complete(client, index=index).get_json()
        if index < 4:
            assert data['points'] == 0
    assert data['points'] == 100
    assert data['points_awarded'] is True
    for _ in range(3):
        repeated = complete(client, index=4).get_json()
        assert repeated['course_done_count'] == 4
        assert repeated['points'] == 0
    assert TutorialCourseReward.query.count() == 1
    assert PointEvent.query.count() == 1
    assert sum(event.points for event in PointEvent.query.all()) == 100
    assert Progress.query.count() == 4


def test_save_failure_rolls_back_and_retry_saves(tutorial, monkeypatch):
    app, db, client, Progress = tutorial
    original = db.session.commit
    def fail():
        raise RuntimeError('synthetic failure')
    monkeypatch.setattr(db.session, 'commit', fail)
    response = complete(client)
    assert response.status_code == 500
    assert response.get_json().get('saved') is False
    assert Progress.query.count() == 0
    monkeypatch.setattr(db.session, 'commit', original)
    assert complete(client).get_json()['saved'] is True
    assert Progress.query.count() == 1


@pytest.mark.parametrize('track', ['elem','mid'])
def test_resume_ignores_unknown_ids_and_other_user(tutorial, track):
    app, db, client, Progress = tutorial
    db.session.add_all([
        Progress(user_id='pupil',track=track,course='course1',lesson_id='obsolete',status='done'),
        Progress(user_id='pupil',track=track,course='course1',lesson_id=f'{track}-course1-l1',status='done'),
        Progress(user_id='other',track=track,course='course1',lesson_id=f'{track}-course1-l2',status='done'),
    ])
    db.session.commit()
    html = client.get(f'/tutorial/{track}/').get_data(as_text=True)
    assert '1/4' in html
    assert f'href="/tutorial/{track}/course1/{track}-course1-l2"' in html
    assert f'href="/tutorial/{track}/course2/' not in html


def test_cross_user_writes_and_readback_are_isolated(tutorial):
    app, db, client, Progress = tutorial
    assert complete(client).get_json()['course_done_count'] == 1
    with client.session_transaction() as s:
        s['_user_id'] = 'other'
    data = complete(client, index=2).get_json()
    assert data['course_done_count'] == 1
    assert data['next_lesson_url'].endswith('elem-course1-l1')
    assert Progress.query.filter_by(user_id='other',status='done').count() == 1
    assert Progress.query.filter_by(user_id='pupil',status='done').count() == 1
    with client.session_transaction() as s:
        s['_user_id'] = 'pupil'
    html = client.get('/tutorial/elem/').get_data(as_text=True)
    assert 'href="/tutorial/elem/course1/elem-course1-l2"' in html


def test_admin_can_preview_locked_courses_without_persistence(tutorial):
    app, db, client, Progress = tutorial
    with client.session_transaction() as s:
        s['_user_id'] = 'admin'
    html = client.get('/tutorial/elem/').get_data(as_text=True)
    for code in ('course1','course2','course3'):
        assert f'href="/tutorial/elem/{code}/elem-{code}-l1"' in html
    assert complete(client).get_json()['skipped'] is True
    assert Progress.query.count() == 0


def test_anonymous_cannot_save_but_can_view(tutorial):
    app, db, client, Progress = tutorial
    with client.session_transaction() as s:
        s.clear()
    assert complete(client).status_code == 401
    assert client.get('/tutorial/elem/course1/elem-course1-l1').status_code == 200
    assert Progress.query.count() == 0



@pytest.mark.parametrize('bad', [
    {'lesson_id':'elem-course2-l1'}, {'lesson_id':'mid-course1-l1'},
    {'lesson_id':'missing'}, {'track':'../elem'}, {'course':'missing'},
])
def test_invalid_content_is_rejected_before_persistence(tutorial, bad):
    app, db, client, Progress = tutorial
    payload = dict(track='elem', course='course1', lesson_id='elem-course1-l1', score=1, total=1)
    payload.update(bad)
    assert client.post('/tutorial/api/complete', json=payload).status_code == 400
    assert Progress.query.count() == 0


@pytest.mark.parametrize('uid', ['admin','parent','teacher'])
def test_skipped_roles_explicitly_do_not_save(tutorial, uid):
    app, db, client, Progress = tutorial
    with client.session_transaction() as s:
        s['_user_id'] = uid
    data = complete(client).get_json()
    assert data.get('saved') is False
    assert data['skipped'] is True
    assert not data.get('next_lesson_url')
    assert Progress.query.count() == 0



def test_completion_acknowledges_save_and_recommends_first_missing(tutorial):
    app, db, client, Progress = tutorial
    response = complete(client)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get('saved') is True
    assert data['course_done_count'] == 1
    assert data['course_total'] == 4
    assert data['course_completed'] is False
    assert data['next_lesson_url'] == '/tutorial/elem/course1/elem-course1-l2'
    assert data['courses_url'] == '/tutorial/elem/#courses'
    assert Progress.query.filter_by(user_id='pupil',status='done').count() == 1
