import random
def propose(weights,seed,count=8,scale=.05):
    if not 1<=count<=128 or not 0<scale<=1 or not weights:raise ValueError('Invalid heuristic mutation budget')
    rng=random.Random(seed);names=sorted(weights);result=[]
    for _ in range(count):
        candidate=dict(weights);name=rng.choice(names);candidate[name]+=rng.uniform(-scale,scale)
        result.append(candidate)
    return tuple(result)
def compare(baseline,candidates,heldout,evaluate,budget):
    cases=tuple(heldout);reference=evaluate(baseline,cases,budget)
    return {'baseline':reference,'candidates':tuple({'configuration':c,'metrics':evaluate(c,cases,budget)} for c in candidates),'promoted':False}
