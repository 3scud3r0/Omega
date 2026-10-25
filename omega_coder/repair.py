"""Bounded propose/check repair. Existing failing checks cannot be removed."""
from dataclasses import dataclass
@dataclass(frozen=True)
class RepairOutcome:
    accepted: bool
    candidate: object
    attempts: tuple
class RepairLoop:
    def __init__(self,propose,isolated_check,required_checks):self.propose=propose;self.check=isolated_check;self.required=frozenset(required_checks)
    def run(self,candidate,diagnostic,max_attempts=8):
        if not 1<=max_attempts<=64:raise ValueError('Invalid repair budget')
        history=[]
        for index in range(max_attempts):
            report=self.check(candidate)
            if not self.required<=set(report):raise ValueError('Repair removed required checks')
            passed=all(report[name] is True for name in self.required)
            history.append({'attempt':index,'checks':report,'accepted':passed})
            if passed:return RepairOutcome(True,candidate,tuple(history))
            candidate=self.propose(candidate,diagnostic,report)
        return RepairOutcome(False,candidate,tuple(history))
