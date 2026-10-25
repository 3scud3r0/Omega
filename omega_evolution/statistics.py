"""Paired bootstrap and Holm correction; sample evidence is not a universal guarantee."""
import math,random,statistics
def paired_interval(before,after,seed=0,resamples=2000):
    before=tuple(before);after=tuple(after)
    if len(before)!=len(after) or not 2<=len(before)<=10000 or not 100<=resamples<=10000 or len(before)*resamples>2000000:raise ValueError('Invalid statistical budget')
    delta=[b-a for a,b in zip(before,after)]
    if any(not math.isfinite(x) for x in delta):raise ValueError('Finite paired measurements required')
    rng=random.Random(seed);means=sorted(statistics.mean(rng.choices(delta,k=len(delta))) for _ in range(resamples))
    return {'mean_delta':statistics.mean(delta),'ci95':(means[int(.025*resamples)],means[min(resamples-1,int(.975*resamples))]),'pairs':len(delta),'seed':seed}
def holm(pvalues,alpha=.05):
    if not 0<alpha<1 or any(not 0<=p<=1 for p in pvalues.values()):raise ValueError('Invalid significance input')
    decisions={k:False for k in pvalues};ordered=sorted(pvalues,key=lambda k:(pvalues[k],k))
    for rank,key in enumerate(ordered):
        if pvalues[key]>alpha/(len(ordered)-rank):break
        decisions[key]=True
    return decisions
