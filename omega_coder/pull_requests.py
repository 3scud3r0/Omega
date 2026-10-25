"""Explicitly authorized PR publication; never merges a pull request."""
from dataclasses import dataclass
import re,tempfile
from pathlib import Path
from omega_platform.sandbox import trusted
from omega_platform.budget import BUILD_BUDGET
@dataclass(frozen=True)
class PullRequest:
    repository: str
    branch: str
    title: str
    body: str
    base: str='main'
    def __post_init__(self):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+',self.repository) or not re.fullmatch(r'[\w./-]+',self.branch):raise ValueError('Invalid PR identity')
        if not self.title or len(self.body)>100000:raise ValueError('Invalid review content')
def publish(request,*,capability,verifier,principal,approval,approval_gate):
    verifier.require(capability,principal,'github.pr.create')
    approval_gate.consume(request.__dict__,approval,principal)
    with tempfile.TemporaryDirectory(prefix='omega-pr-') as tmp:
        path=Path(tmp)/'body.md';path.write_text(request.body)
        result=trusted(['gh','pr','create','--draft','--repo',request.repository,'--base',request.base,
                        '--head',request.branch,'--title',request.title,'--body-file',path],budget=BUILD_BUDGET,check=True)
    return result.stdout.strip()
