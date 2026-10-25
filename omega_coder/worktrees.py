"""Disposable detached worktrees. Git metadata is never writable by candidates."""
import re,shutil
from pathlib import Path
from omega_platform.sandbox import trusted,run
from omega_platform.budget import BUILD_BUDGET,Budget
class Worktree:
    def __init__(self,repository,destination,commit):
        if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Full existing commit SHA required')
        self.repository=Path(repository).resolve(strict=True);self.path=Path(destination).absolute();self.commit=commit;self.created=False
    def _git(self,*args):
        return trusted(['git','-c','core.hooksPath=/dev/null','-C',self.repository,*args],budget=BUILD_BUDGET,check=True)
    def create(self):
        if self.path.exists():raise FileExistsError(self.path)
        self._git('worktree','add','--detach',str(self.path),self.commit);self.created=True;return self
    def execute(self,argv,*,readonly=(),budget=Budget()):
        if not self.created:raise ValueError('Worktree is not active')
        return run(argv,cwd=self.path,writable=[self.path],readonly=[self.path/'.git',*readonly],budget=budget)
    def diff(self):return self._git('-C',str(self.path),'diff','--no-ext-diff','--binary').stdout
    def close(self):
        if self.created:self._git('worktree','remove','--force',str(self.path));self.created=False
    def __enter__(self):return self.create()
    def __exit__(self,*exc):self.close()
