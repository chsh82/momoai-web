import importlib.util,os,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('guard',ROOT/'scripts/verify_reset_deploy.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
os.environ['PATH']='C:/Users/aproa/AppData/Local/hermes/tools/git-2.53.0+3-win32-x64/mingw64/bin'+os.pathsep+os.environ['PATH'] if os.name=='nt' else os.environ['PATH']
@pytest.fixture
def repo(tmp_path):
    def git(*args):return subprocess.check_output(['git',*args],cwd=tmp_path).decode().strip()
    git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');git('config','core.autocrlf','false')
    (tmp_path/'file.py').write_bytes(b'old\n');(tmp_path/'.gitignore').write_bytes(b'ignored.py\n');git('add','.');git('commit','-m','base');old=git('rev-parse','HEAD')
    (tmp_path/'file.py').write_bytes(b'new\n');(tmp_path/'new.py').write_bytes(b'added\n');(tmp_path/'ignored.py').write_bytes(b'approved\n');git('add','.');git('add','-f','ignored.py');git('commit','-m','target');new=git('rev-parse','HEAD');git('checkout','--detach',old)
    return tmp_path,git,old,new

def test_clean_guard_is_read_only(repo):
    root,git,old,new=repo;before=git('status','--porcelain');assert guard.verify(root,new)['status']=='safe_to_reset';assert git('status','--porcelain')==before;assert git('rev-parse','HEAD')==old;assert (root/'file.py').read_bytes()==b'old\n'
@pytest.mark.parametrize('kind',['dirty','collision','ignored_collision','staged','deleted'])
def test_guard_blocks_source_loss(repo,kind):
    root,git,old,new=repo
    if kind=='dirty':(root/'file.py').write_bytes(b'live overlay\n')
    if kind=='collision':(root/'new.py').write_bytes(b'other owner\n')
    if kind=='ignored_collision':(root/'ignored.py').write_bytes(b'ignored owner\n')
    if kind=='deleted':(root/'file.py').unlink()
    if kind=='staged':(root/'file.py').write_bytes(b'staged\n');git('add','file.py')
    before=git('status','--porcelain');
    with pytest.raises(RuntimeError):guard.verify(root,new)
    assert git('status','--porcelain')==before and git('rev-parse','HEAD')==old
@pytest.mark.parametrize('name,data',[('file.py',b'new\n'),('new.py',b'added\n'),('ignored.py',b'approved\n')])
def test_exact_already_live_bytes_can_be_adopted(repo,name,data):
    root,git,old,new=repo;(root/name).write_bytes(data);assert guard.verify(root,new)['adopted_exact_live_paths']==[name];assert (root/name).read_bytes()==data

@pytest.mark.parametrize('flag',['--assume-unchanged','--skip-worktree'])
@pytest.mark.parametrize('live_bytes',[b'hidden live overlay\n',b'new\n',b'old\n'])
def test_guard_rejects_hidden_index_flags_without_mutation(repo,flag,live_bytes):
    root,git,old,new=repo
    git('update-index',flag,'file.py')
    (root/'file.py').write_bytes(live_bytes)
    # Real Git hides even divergent live bytes from the guard's ordinary diff.
    assert git('diff','--name-only','HEAD','--')==''
    before_index=(root/'.git/index').read_bytes()
    before_flags=git('ls-files','-v')
    with pytest.raises(RuntimeError,match='index flags'):
        guard.verify(root,new)
    assert (root/'.git/index').read_bytes()==before_index
    assert git('ls-files','-v')==before_flags
    assert git('rev-parse','HEAD')==old
    assert (root/'file.py').read_bytes()==live_bytes


def test_guard_blocks_unpublished_live_commit(repo):
    root,git,old,new=repo;(root/'local.py').write_bytes(b'already deployed\n');git('add','local.py');git('commit','-m','unpublished live');head=git('rev-parse','HEAD')
    with pytest.raises(RuntimeError,match='Unpublished/divergent'):guard.verify(root,new)
    assert git('rev-parse','HEAD')==head

@pytest.mark.parametrize('ignored',[False,True])
def test_guard_rejects_untracked_file_blocking_new_directory(repo,ignored):
    root,git,old,new=repo
    git('checkout','--detach',new)
    (root/'new_directory/nested').mkdir(parents=True)
    (root/'new_directory/nested/child.py').write_bytes(b'new tracked child\n')
    git('add','new_directory');git('commit','-m','nested target');nested=git('rev-parse','HEAD')
    git('checkout','--detach',old);(root/'new_directory').write_bytes(b'untracked file must survive\n')
    if ignored:
        (root/'.git/info/exclude').write_bytes(b'/new_directory\n')
        assert git('check-ignore','new_directory')=='new_directory'
        assert git('ls-files','--others','--exclude-standard')==''
    before_index=(root/'.git/index').read_bytes()
    with pytest.raises(RuntimeError,match='Live parent paths'):
        guard.verify(root,nested)
    assert (root/'new_directory').read_bytes()==b'untracked file must survive\n'
    assert (root/'.git/index').read_bytes()==before_index
    assert git('rev-parse','HEAD')==old


def test_guard_rejects_actual_ancestor_directory_symlink(repo):
    root,git,old,new=repo
    git('checkout','--detach',new)
    (root/'new_directory/nested').mkdir(parents=True)
    (root/'new_directory/nested/child.py').write_bytes(b'approved child\n')
    git('add','new_directory');git('commit','-m','symlink ancestor target');nested=git('rev-parse','HEAD')
    git('checkout','--detach',old)
    destination=root/'private_target'
    (destination/'nested').mkdir(parents=True)
    (destination/'nested/child.py').write_bytes(b'approved child\n')
    try:
        (root/'new_directory').symlink_to(destination,target_is_directory=True)
    except OSError as exc:
        if os.name=='nt' and exc.winerror in (1314,50):
            pytest.skip('Windows directory symlinks unavailable without system changes: '+str(exc))
        raise
    assert (root/'new_directory').is_symlink()
    before_index=(root/'.git/index').read_bytes()
    with pytest.raises(RuntimeError,match='Live parent paths'):
        guard.verify(root,nested)
    assert (root/'new_directory').is_symlink()
    assert (root/'new_directory').readlink()==destination
    assert (destination/'nested/child.py').read_bytes()==b'approved child\n'
    assert (root/'.git/index').read_bytes()==before_index
    assert git('rev-parse','HEAD')==old


def test_workflow_checks_before_build_and_before_reset():
    source=(ROOT/'.github/workflows/deploy.yml').read_text(encoding='utf-8')
    assert source.count('python3 "$STAGE_DIR/scripts/verify_reset_deploy.py"')==2
    assert source.index('verify_reset_deploy.py')<source.index('npm ci --silent')
    assert source.rindex('verify_reset_deploy.py')<source.index('git reset --hard "$TARGET_COMMIT"')
