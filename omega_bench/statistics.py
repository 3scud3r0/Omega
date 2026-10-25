import collections,statistics
from omega_evolution.statistics import paired_interval,holm
def report(records):
    records=tuple(records)
    statuses=collections.Counter(r['status'] for r in records)
    timings=[r['seconds'] for r in records]
    return {'cases':len(records),'statuses':dict(statuses),'median_seconds':statistics.median(timings) if timings else None,
            'failures':tuple(r for r in records if r['status']!='correct')}
def paired_versions(before,after,seed=0):
    if [r['id'] for r in before]!=[r['id'] for r in after]:raise ValueError('Version comparison cases do not match')
    return paired_interval([int(r['status']=='correct') for r in before],[int(r['status']=='correct') for r in after],seed=seed)
