"""Task-owned append-only execution receipts; never boot production factory."""
from pathlib import Path
import json, os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/result-library-20261121'
OUT.mkdir(parents=True,exist_ok=True)
label=sys.argv[1]
if not label.replace('-','').replace('_','').isalnum(): raise SystemExit('invalid label')
if (OUT/(label+'.log')).exists(): raise SystemExit('Evidence label already exists')
scratch=Path('C:/Users/aproa/AppData/Local/hermes/profiles/momo/cache/scratch/result-library-20261121')
scratch.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,RESULT_LIBRARY_EVIDENCE=str(OUT/(label+'-assets')),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH=str(ROOT),TMPDIR=str(scratch),TEMP=str(scratch),TMP=str(scratch))
# Native Python child PATH needs native Git, not MSYS-only path conversion.
import hashlib, playwright
node_dir=Path(playwright.__file__).parent/'driver'
def source_hashes():
    paths=[p for p in (ROOT/'app/interest_quest').rglob('*') if p.is_file() and p.suffix in ('.py','.js','.css','.json','.html')]
    paths+=list((ROOT/'templates/interest_quest').glob('*.html'))
    paths += [ROOT/'templates/base.html',ROOT/'static/css/interest-reports.css',ROOT/'scripts/build_story_v3.py']
    return {str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
before=source_hashes()
import shutil
git=shutil.which('git')
if not git:
    candidates=list((Path.home()/'AppData/Local/hermes/tools').glob('git-*/mingw64/bin/git.exe'))
    git=str(candidates[-1]) if candidates else None
if not git:raise SystemExit('Native Git executable not found in invoking interpreter PATH or managed tools')
env['PATH']=str(Path(git).parent)+os.pathsep+str(node_dir)+os.pathsep+env['PATH']
subprocess.run([sys.executable,'-c',"import shutil,subprocess; assert shutil.which('git'); subprocess.run(['git','--version'],check=True)"],env=env,check=True,stdout=subprocess.DEVNULL)
args=sys.argv[2:] or ['tests/result_library']
command=[sys.executable,'-m','pytest',*args,'-q','--basetemp='+str(scratch/label),'--junitxml='+str(OUT/(label+'.xml'))]
result_path=OUT/(label+'.log')
with result_path.open('w',encoding='utf-8') as stream:
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
text=result_path.read_text(encoding='utf-8',errors='replace')
(OUT/(label+'-command.json')).write_text(json.dumps(dict(command=command,cwd=str(ROOT),returncode=result.returncode),indent=2),encoding='utf-8')
after=source_hashes()
(OUT/(label+'-sources.json')).write_text(json.dumps(dict(before=before,after=after,unchanged=before==after),indent=2),encoding='utf-8')
print(text)
if before!=after:raise SystemExit('Source bytes changed during run; evidence not accepted')
sys.exit(result.returncode)
