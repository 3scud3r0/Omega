"""Benchmark trusted solver adapters; candidate execution belongs in their sandbox.

Only public input is sent to a solver. Hidden answers remain in the verifier.
"""
from dataclasses import dataclass
import hashlib,json,time
@dataclass(frozen=True)
class BenchmarkBudget:
    cases: int=100
    seconds_per_case: float=30
    candidate_limit: int=32
    def __post_init__(self):
        if not 1<=self.cases<=10000 or not 0<self.seconds_per_case<=3600 or not 1<=self.candidate_limit<=10000:raise ValueError('Invalid benchmark budget')
def run(cases,solver,verifier,budget=BenchmarkBudget(),seed=0):
    records=[];seen=set()
    for index,case in enumerate(cases):
        if index>=budget.cases:break
        if case['id'] in seen:raise ValueError('Duplicate benchmark id')
        seen.add(case['id']);public={k:case[k] for k in ('id','domain','input')};started=time.perf_counter()
        try:
            candidate=solver(public,budget,seed+index);elapsed=time.perf_counter()-started
            result=verifier(case['id'],candidate)
            if type(result) is not bool:raise ValueError('Independent boolean oracle required')
            status='correct' if result else 'incorrect'
            if elapsed>budget.seconds_per_case:status='budget_exceeded'
            detail=None
        except Exception as exc:elapsed=time.perf_counter()-started;status='error';detail=type(exc).__name__
        records.append({'id':case['id'],'domain':case['domain'],'seed':seed+index,'seconds':elapsed,'status':status,'error_type':detail})
    correct=sum(r['status']=='correct' for r in records)
    return {'records':tuple(records),'correct':correct,'cases':len(records),'accuracy':correct/len(records) if records else None,
            'seconds_per_correct':sum(r['seconds'] for r in records)/correct if correct else None}
