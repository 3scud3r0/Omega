"""Bounded readonly process batches with complete admission before dispatch."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from .budget import Budget
from .sandbox import run


@dataclass(frozen=True)
class Job:
    id: str
    argv: tuple[str, ...]
    readonly: tuple[str, ...] = ()
    budget: Budget = Budget()

    def __post_init__(self):
        if type(self.id) is not str or not 0 < len(self.id) <= 256 or any(ord(c) < 32 for c in self.id):
            raise ValueError('Invalid job identity')
        if type(self.argv) is not tuple or not 1 <= len(self.argv) <= 256:
            raise ValueError('Bounded argv tuple required')
        if type(self.readonly) is not tuple or len(self.readonly) > 64 or type(self.budget) is not Budget:
            raise ValueError('Readonly mounts and OS budget required')
        if any(type(v) is not str or not v or '\0' in v or len(v.encode('utf-8')) > 65536 for v in (*self.argv, *self.readonly)):
            raise ValueError('Bounded string arguments and paths required')
        if sum(len(v.encode('utf-8')) for v in (*self.argv, *self.readonly)) > 256 * 1024:
            raise ValueError('Argument byte budget exceeded')
        if not Path(self.argv[0]).is_absolute() or any(not Path(p).is_absolute() for p in self.readonly):
            raise ValueError('Absolute executable and mount paths required')
        if len(set(self.readonly)) != len(self.readonly):
            raise ValueError('Duplicate readonly mount')


@dataclass(frozen=True)
class BatchLimits:
    workers: int = 4
    jobs: int = 64
    reserved_cpu_seconds: int = 120
    concurrent_memory_bytes: int = 2 * 1024**3

    def __post_init__(self):
        if any(type(v) is not int for v in (self.workers, self.jobs, self.reserved_cpu_seconds, self.concurrent_memory_bytes)):
            raise TypeError('Integer batch limits required')
        if not 1 <= self.workers <= 8 or not 1 <= self.jobs <= 64:
            raise ValueError('Invalid concurrency limits')
        if not 1 <= self.reserved_cpu_seconds <= 64 * 3600 or not 32 * 1024**2 <= self.concurrent_memory_bytes <= 512 * 1024**3:
            raise ValueError('Invalid resource reservation')


def admit(jobs, limits=BatchLimits(), *, repetitions=1):
    """Materialize only a bounded batch; do not start any candidate here."""
    if type(limits) is not BatchLimits or type(repetitions) is not int or not 1 <= repetitions <= 8:
        raise ValueError('Invalid admission limits')
    sequence = []
    for job in jobs:
        if len(sequence) >= limits.jobs:
            raise ValueError('Job count budget exceeded')
        if type(job) is not Job:
            raise TypeError('Job required')
        sequence.append(job)
    if len({j.id for j in sequence}) != len(sequence):
        raise ValueError('Duplicate job id')
    if sum(j.budget.cpu_seconds for j in sequence) * repetitions > limits.reserved_cpu_seconds:
        raise ValueError('CPU reservation exceeded')
    memory = sorted((j.budget.memory_bytes for j in sequence), reverse=True)
    if sum(memory[:limits.workers]) > limits.concurrent_memory_bytes:
        raise ValueError('Memory reservation exceeded')
    return tuple(sequence)


def execute(jobs, limits=BatchLimits(), *, cancel_event=None):
    sequence = admit(jobs, limits)
    def one(job):
        return job.id, run(job.argv, readonly=job.readonly, budget=job.budget, cancel_event=cancel_event)
    with ThreadPoolExecutor(max_workers=limits.workers) as pool:
        return tuple(pool.map(one, sequence))


def execute_reproducible(jobs, limits=BatchLimits(), repetitions=2, *, cancel_event=None):
    """Compare completed outputs, without proving universal determinism."""
    if type(repetitions) is not int or not 2 <= repetitions <= 8:
        raise ValueError('Invalid reproducibility repetition budget')
    sequence = admit(jobs, limits, repetitions=repetitions)
    reference = None
    records = []
    for _ in range(repetitions):
        outcomes = execute(sequence, limits, cancel_event=cancel_event)
        if any(not outcome.ok for _, outcome in outcomes):
            raise ValueError('Reproducibility requires successful completed executions')
        values = tuple((id, outcome.returncode, outcome.stdout, outcome.stderr, outcome.termination) for id, outcome in outcomes)
        if reference is not None and values != reference:
            raise ValueError('Job outputs are not reproducible')
        reference = values
        records.append(outcomes)
    return tuple(records)
