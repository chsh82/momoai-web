"""Redirect inherited screenshot/PDF outputs without changing their assertions."""
import os
from pathlib import Path
import pytest

def pytest_collection_modifyitems(items):
    """Redirect module-scoped fixture writers before any fixture can execute."""
    for module in {item.module for item in items}:
        if hasattr(module,'OUT'):
            module.OUT=Path(os.environ['RESULT_LIBRARY_EVIDENCE'])/module.__name__.replace('.','-')
            module.OUT.mkdir(parents=True,exist_ok=True)
        if hasattr(module,'SCRATCH'):
            module.SCRATCH=Path(os.environ['TMPDIR'])/('inherited-'+module.__name__.replace('.','-'))
            module.SCRATCH.mkdir(parents=True,exist_ok=True)


@pytest.fixture(autouse=True)
def task_owned_artifacts(request,monkeypatch):
    module=request.module
    if hasattr(module,'OUT'):
        out=Path(os.environ['RESULT_LIBRARY_EVIDENCE'])/module.__name__.replace('.','-')
        out.mkdir(parents=True,exist_ok=True)
        monkeypatch.setattr(module,'OUT',out)
