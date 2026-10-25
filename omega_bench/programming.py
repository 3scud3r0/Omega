"""Hidden acceptance suites stay on the verifier side of the benchmark boundary."""
from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class ProgrammingTask:
    id: str
    language: str
    requirement: str
    public_examples: tuple
    hidden_suite_digest: str
    def public(self):return {'id':self.id,'domain':'programming/'+self.language,'input':{'requirement':self.requirement,'examples':self.public_examples}}
class ProgrammingOracle:
    def __init__(self,tasks,isolated_runner):self.tasks={t.id:t for t in tasks};self.runner=isolated_runner
    def verify(self,id,candidate):
        task=self.tasks[id]
        result=self.runner(task.language,candidate,task.hidden_suite_digest)
        if result.get('suite_sha256')!=task.hidden_suite_digest:raise ValueError('Wrong hidden acceptance suite')
        return result.get('passed') is True and result.get('sandboxed') is True
