"""OM-067: executable checks; source delivery, not a recorded pass."""
from pathlib import Path
from omega_coder.worktrees import Worktree
from omega_platform.sandbox import trusted
from omega_platform.budget import BUILD_BUDGET

def test_worktree_edits_and_cleanup_do_not_change_stable_checkout(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    def git(*args):return trusted(['git','-c','core.hooksPath=/dev/null','-C',repo,*args],budget=BUILD_BUDGET,check=True).stdout.strip()
    git('init');(repo/'a.txt').write_text('stable');git('add','a.txt')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
    with Worktree(repo,tmp_path/'candidate',git('rev-parse','HEAD')) as tree:
        (tree.path/'a.txt').write_text('candidate')
        assert 'candidate' in tree.diff() and (repo/'a.txt').read_text()=='stable'
    assert not (tmp_path/'candidate').exists() and (repo/'a.txt').read_text()=='stable'
