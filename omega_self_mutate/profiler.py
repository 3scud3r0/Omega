from collections import Counter
from pathlib import Path
import time


def profile_ir(source):
    from omega_selfhost.driver import compile_ir
    start=time.perf_counter_ns();ir=compile_ir(Path(source));elapsed=time.perf_counter_ns()-start
    counts=Counter(n['op'] for n in ir['nos'])
    return {'format':'omega-ir-profile-1','nodes':len(ir['nos']),'operations':dict(sorted(counts.items())),
            'hotspots':counts.most_common(),'compile_ns':elapsed,'metric':'observed IR frequency and compilation duration; not a hardware latency proof'}


def profile_native(source,*,iterations=5):
    """Measure the generated binary separately from proof verification time."""
    import json,statistics,tempfile
    from omega_selfhost.driver import build,verify_result
    from omega_platform.sandbox import run
    from omega_platform.budget import Budget
    if type(iterations) is not int or not 1<=iterations<=100:raise ValueError('Bounded profiler repetitions required')
    profile=profile_ir(source)
    with tempfile.TemporaryDirectory(prefix='omega-ir-profile-') as temporary:
        binary=Path(temporary)/'program';build(source,binary)
        outcomes=[];durations=[]
        for _ in range(iterations):
            outcome=run([binary],budget=Budget(),check=True)
            outcomes.append(json.loads(outcome.stdout));durations.append(outcome.wall_seconds)
        if any(result!=outcomes[0] for result in outcomes):raise ValueError('Non-deterministic profiled execution')
        admission=verify_result(outcomes[0])
    return {**profile,'native_seconds':durations,'native_median_seconds':statistics.median(durations),
            'native_min_seconds':min(durations),'native_admission':admission,
            'timing_scope':'observed process plus namespace supervision; excludes Lean admission, not per-op attribution or a speed theorem'}
