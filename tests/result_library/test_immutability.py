"""Pin immutable material to the discovered member-release baseline, never moving HEAD."""
import hashlib,json,subprocess
from pathlib import Path
from conftest import ROOT
BASELINE='f95a7c78ab042acc7a2a5fe0c317b84f493d8216'
OUT=ROOT/'reports/result-library-20261121'

def baseline(path):
    """Reconstruct only required baseline seams from the hash-pinned independent receipt."""
    fixture=ROOT/'tests/result_library/fixtures/approved-immutable-baselines.json'
    raw=fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='f97d29c97ec9e3a54d1bb8e57ca8652db41705fdb1e6e4a95b60460fdf236ff1'
    ledger=json.loads(raw);assert ledger['baseline_commit']==BASELINE
    if path=='templates/base.html':
        return (ROOT/'tests/result_library/fixtures/upstream-base.html').read_bytes().replace(b'\r\n',b'\n')
    # For normalized protected sources the ledger retains the independently verified SHA.
    current=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
    if path!='app/interest_quest/protected/index.html':
        assert hashlib.sha256(current).hexdigest()==ledger['hashes'][path]['normalized_baseline_sha256'],path
    else:
        text=current.decode('utf8')
        for name,marker in [('canonical_form','const FORM='),('artwork','const STORY_ASSETS=')]:
            assert digest(decoded(text,marker))==ledger['hashes'][name]['baseline_sha256']
        scorer=text.split('(function(root){',1)[1].split("})(typeof globalThis!=='undefined'?globalThis:this);",1)[0]
        assert hashlib.sha256(scorer.encode()).hexdigest()==ledger['hashes']['scorer']['baseline_sha256']
    return current

def decoded(text,marker):
    return json.JSONDecoder().raw_decode(text.split(marker,1)[1])[0]

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def test_canonical_questions_scorer_and_artwork_match_fixed_baseline():
    rel='app/interest_quest/protected/index.html'
    old=baseline(rel).decode('utf8');new=(ROOT/rel).read_text(encoding='utf8')
    hashes={}
    for name,marker in [('canonical_form','const FORM='),('artwork','const STORY_ASSETS=')]:
        before=decoded(old,marker);after=decoded(new,marker)
        assert after==before
        hashes[name]=dict(baseline_sha256=digest(before),candidate_sha256=digest(after))
    start='(function(root){';end="})(typeof globalThis!=='undefined'?globalThis:this);"
    scorer=lambda text:text.split(start,1)[1].split(end,1)[0]
    assert scorer(old)==scorer(new)
    hashes['scorer']=dict(baseline_sha256=hashlib.sha256(scorer(old).encode()).hexdigest(),candidate_sha256=hashlib.sha256(scorer(new).encode()).hexdigest())
    protected=['app/interest_quest/backend.py','app/interest_quest/store.py','app/interest_quest/access.py',
               'app/interest_quest/protected/momotown-v02.js','app/interest_quest/protected/momotown-v02.json',
               'app/interest_quest/protected/story-v3.js','app/interest_quest/protected/story-v4-content.json']
    for path in protected:
        before=baseline(path);after=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        assert after==before,path
        hashes[path]=dict(normalized_baseline_sha256=hashlib.sha256(before).hexdigest(),normalized_candidate_sha256=hashlib.sha256(after).hexdigest(),raw_candidate_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'immutable-baselines.json').write_text(json.dumps(dict(baseline_commit=BASELINE,hashes=hashes),indent=2),encoding='utf8')


def test_shared_shell_change_is_exact_narrow_overlay():
    from scripts.result_library_shell_overlay import overlay
    from scripts.result_library_upstream_shell import overlay_upstream
    old=baseline('templates/base.html')
    assert hashlib.sha256(old).hexdigest()=='f88beb0d57e1c2c441abd40c02b801516543fc2a861d4e6f1156b4520b5cf535'
    actual=(ROOT/'templates/base.html').read_bytes().replace(b'\r\n',b'\n')
    assert overlay_upstream(old)==actual
    source=ROOT/'reports/result-library-20261121/integration/base-live-snapshot.html'
    candidate=source.with_name('base-live-candidate.html')
    assert overlay(source.read_bytes())==candidate.read_bytes()
