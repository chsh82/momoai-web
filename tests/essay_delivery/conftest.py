"""Standalone release tests: production models/blueprints, synthetic DB only.

The production app factory is intentionally NOT executed: it starts schedulers
and automatic DDL. No config/env files, real accounts, or external sockets.
"""
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
os.environ['MOMOAI_TEST_MODE'] = '1'
# Package-only bootstrap; all submodules are actual release sources.
package = ModuleType('app'); package.__path__ = [str(REPO / 'app')]
sys.modules['app'] = package
config = ModuleType('config')
class Config:
    ANTHROPIC_API_KEY = ''
    GEMINI_API_KEY = ''
config.Config = Config
sys.modules['config'] = config

@pytest.fixture
def kernel():
    from flask import Flask
    from app.models import db
    from sqlalchemy.orm import configure_mappers
    import sqlalchemy as sa
    root = Path(tempfile.mkdtemp(prefix='essay-release-', dir=os.environ['TMPDIR'])).resolve()
    app = Flask('app', root_path=str(REPO / 'app'), template_folder=str(REPO / 'templates'), static_folder=str(REPO / 'static'))
    app.config.update(TESTING=True, SECRET_KEY='synthetic-release-only', SQLALCHEMY_DATABASE_URI='sqlite:///' + (root / 'synthetic.sqlite').as_posix(), SQLALCHEMY_TRACK_MODIFICATIONS=False, WTF_CSRF_ENABLED=True, SERVER_NAME='localhost')
    for key in ('UPLOAD_FOLDER','OUTPUT_FOLDER','HTML_FOLDER','PDF_FOLDER','POST_FILES_FOLDER','POST_IMAGES_FOLDER','MATERIALS_FOLDER','CORRECTION_ATTACHMENTS_FOLDER','GUIDE_ATTACHMENTS_FOLDER'):
        app.config[key] = str(root / key.lower())
    db.init_app(app)
    with patch('socket.socket.connect', side_effect=AssertionError('external network forbidden')), app.app_context():
        configure_mappers()
        @sa.event.listens_for(db.engine, 'connect')
        def enforce(connection, record): connection.execute('PRAGMA foreign_keys=ON')
        yield app, db, root
        db.session.remove(); db.engine.dispose()
