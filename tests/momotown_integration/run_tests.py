"""Run isolated backend/Chromium checks with the invoking interpreter.

No dependency on another worktree's reports or production application factory.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'reports/momotown-v02-review/backend'
OUT.mkdir(parents=True, exist_ok=True)
label = sys.argv[1] if len(sys.argv)>1 else 'full-backend-and-chromium'
if not label or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in label):
    raise SystemExit('Use an alphanumeric, dash or underscore evidence label')
args = sys.argv[2:] or ['tests/momotown_backend', 'tests/momotown_integration']
# Explicit Windows paths: host TMPDIR can point outside the approved scratch.
scratch = Path.home()/'AppData/Local/hermes/profiles/momo/cache/scratch/momotown-v02-review'/label
scratch.parent.mkdir(parents=True, exist_ok=True)
command = [sys.executable, '-m', 'pytest', *args, '-q', '--basetemp='+str(scratch), '--junitxml='+str(OUT/(label+'.xml'))]
pythonpath = os.pathsep.join(filter(None, [str(ROOT), os.environ.get('PYTHONPATH', '')]))
env = dict(os.environ, PYTHONPATH=pythonpath, TMPDIR=str(scratch.parent), TEMP=str(scratch.parent), TMP=str(scratch.parent))
result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
(OUT/(label+'.log')).write_text(result.stdout+result.stderr, encoding='utf-8')
(OUT/(label+'-environment.json')).write_text(json.dumps(dict(python_executable=sys.executable, PYTHONPATH=env['PYTHONPATH'], command=command, isolation='loopback-only Flask fixture, real blueprint/backend/store, temporary SQLite, no production factory'), indent=2), encoding='utf-8')
print(result.stdout+result.stderr)
sys.exit(result.returncode)
