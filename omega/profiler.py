"""Timing measurements are separate from deterministic trace contents."""
from collections import Counter
import statistics,time
from .trace import evaluate
def profile(ir,state,*,repetitions=3):
    if type(repetitions) is not int or not 1<=repetitions<=100:raise ValueError('Invalid repetition budget')
    timings=[];reference=None
    for _ in range(repetitions):
        start=time.perf_counter();frames=evaluate(ir,state);timings.append(time.perf_counter()-start)
        result=tuple(f.to_dict() for f in frames)
        if reference is not None and result!=reference:raise ValueError('Nonreproducible trace')
        reference=result
    return {'repetitions':repetitions,'median_seconds':statistics.median(timings),
            'min_seconds':min(timings),'nodes':len(frames),'operators':dict(Counter(f.operator for f in frames)),
            'scope':'pure graph evaluation; host reference interpreter'}
