"""Opt-in negative control: pytest -p tests.momotown_backend.legacy_writer_policy.

Run ONLY against test_concurrency.py. Emulate the old read-reserves-writer
policy without editing production files. The two read regressions must fail
with 503 while write contention remains bounded. Never enabled by default.
"""
import pytest


@pytest.fixture(autouse=True)
def legacy_read_reserves_writer(monkeypatch):
    from app.interest_quest import store
    original = store.connection

    def connection(*, write=True):
        return original(write=True)

    monkeypatch.setattr(store, 'connection', connection)
