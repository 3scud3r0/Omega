import resource,time
from dataclasses import dataclass
@dataclass(frozen=True)
class Snapshot:
    monotonic: float
    cpu_seconds: float
    peak_rss_kib: int
    energy_joules: float|None
    gpu_memory_bytes: int|None
def snapshot(energy_reader=None,gpu_reader=None):
    self_usage=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu=self_usage.ru_utime+self_usage.ru_stime+children.ru_utime+children.ru_stime
    return Snapshot(time.monotonic(),cpu,self_usage.ru_maxrss,energy_reader() if energy_reader else None,gpu_reader() if gpu_reader else None)
def difference(before,after,correct):
    wall=after.monotonic-before.monotonic;cpu=after.cpu_seconds-before.cpu_seconds
    energy=after.energy_joules-before.energy_joules if before.energy_joules is not None and after.energy_joules is not None else None
    return {'wall_seconds':wall,'cpu_seconds':cpu,'process_peak_rss_kib':after.peak_rss_kib,'energy_joules':energy,
            'seconds_per_correct':wall/correct if correct else None,'energy_per_correct':energy/correct if energy is not None and correct else None,
            'scope':'process and terminated children CPU; peak RSS is process-wide'}
