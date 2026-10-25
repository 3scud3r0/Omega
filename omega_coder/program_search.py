"""Equal candidate budgets for enumerative, evolutionary and model proposals."""
import random,time
from dataclasses import dataclass
@dataclass(frozen=True)
class SearchBudget:
    candidates: int=128
    seconds: float=30
    seed: int=0
    def __post_init__(self):
        if not 1<=self.candidates<=100000 or not 0<self.seconds<=3600:raise ValueError('Invalid search budget')
def compare(methods,verifier,budget=SearchBudget()):
    results={}
    for name,method in sorted(methods.items()):
        start=time.monotonic();attempts=0;solution=None
        for candidate in method(random.Random(budget.seed)):
            if attempts>=budget.candidates or time.monotonic()-start>=budget.seconds:break
            attempts+=1
            if verifier(candidate) is True:solution=candidate;break
        results[name]={'attempts':attempts,'seconds':time.monotonic()-start,'solution':solution,'seed':budget.seed}
    return results
