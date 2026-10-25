"""Bounded concurrent execution of readonly jobs; result order follows input."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from .budget import Budget
from .sandbox import run
@dataclass(frozen=True)
class Job:
    id: str
    argv: tuple[str,...]
    readonly: tuple[str,...]=()
    budget: Budget=Budget()
    def __post_init__(self):
        if not self.id or not self.argv or type(self.argv) is not tuple:raise ValueError('Invalid job')
        if any(type(v) is not str for v in (*self.argv,*self.readonly)):raise TypeError('String paths required')
@dataclass(frozen=True)
class BatchLimits:
    workers: int=4
    jobs: int=64
    reserved_cpu_seconds: int=120
    concurrent_memory_bytes: int=2*1024**3
    def __post_init__(self):
        if not 1<=self.workers<=8 or not 1<=self.jobs<=64:raise ValueError('Invalid concurrency limits')
        if self.reserved_cpu_seconds<1 or self.concurrent_memory_bytes<32*1024**2:raise ValueError('Invalid resource reservation')
def execute(jobs,limits=BatchLimits()):
    sequence=[]
    for job in jobs:
        if len(sequence)>=limits.jobs:raise ValueError('Job count budget exceeded')
        if type(job) is not Job:raise TypeError('Job required')
        sequence.append(job)
    if len({j.id for j in sequence})!=len(sequence):raise ValueError('Duplicate job id')
    if sum(j.budget.cpu_seconds for j in sequence)>limits.reserved_cpu_seconds:raise ValueError('CPU reservation exceeded')
    memory=sorted((j.budget.memory_bytes for j in sequence),reverse=True)
    if sum(memory[:limits.workers])>limits.concurrent_memory_bytes:raise ValueError('Memory reservation exceeded')
    def one(job):
        return job.id,run(job.argv,readonly=job.readonly,budget=job.budget)
    with ThreadPoolExecutor(max_workers=limits.workers) as pool:return tuple(pool.map(one,sequence))


def execute_reproducible(jobs,limits=BatchLimits(),repetitions=2):
    """Require identical completed outputs over requested repetitions.

    Separate processes and readonly mounts prevent cross-job writable-memory
    sharing. This does not prove arbitrary programs deterministic on all runs.
    """
    if type(repetitions) is not int or not 2<=repetitions<=8:raise ValueError('Invalid reproducibility repetition budget')
    jobs=tuple(jobs)
    if sum(job.budget.cpu_seconds for job in jobs)*repetitions>limits.reserved_cpu_seconds:raise ValueError('Repeated jobs exceed total CPU reservation')
    reference=None;records=[]
    for _ in range(repetitions):
        outcomes=execute(jobs,limits)
        values=tuple((id,outcome.returncode,outcome.stdout,outcome.stderr,outcome.termination) for id,outcome in outcomes)
        if reference is not None and values!=reference:raise ValueError('Job outputs are not reproducible')
        reference=values;records.append(outcomes)
    return tuple(records)
