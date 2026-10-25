"""Empirical calibration of binary predictions; no claim on unseen domains."""
import math
def metrics(probabilities,labels,bins=10):
    p=tuple(probabilities);y=tuple(labels)
    if not p or len(p)!=len(y) or not 1<=bins<=100:raise ValueError('Invalid calibration data')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p):raise ValueError('Invalid probability')
    if any(type(v) not in (int,bool) or v not in (0,1) for v in y):raise ValueError('Binary labels required')
    buckets=[[] for _ in range(bins)]
    for probability,label in zip(p,y):buckets[min(int(probability*bins),bins-1)].append((probability,label))
    ece=0;records=[]
    for bucket in buckets:
        if not bucket:records.append({'count':0});continue
        confidence=sum(a for a,b in bucket)/len(bucket);frequency=sum(b for a,b in bucket)/len(bucket)
        ece+=len(bucket)/len(p)*abs(confidence-frequency)
        records.append({'count':len(bucket),'confidence':confidence,'frequency':frequency})
    return {'brier':sum((a-b)**2 for a,b in zip(p,y))/len(p),'ece':ece,'bins':records,'samples':len(p)}
