import random,math,time
def search(space,evaluate,*,seed=0,trials=16,total_cost=100,seconds=600):
    if not 1<=trials<=1000 or not 0<total_cost or not 0<seconds<=3600:raise ValueError('Invalid tuning budget')
    rng=random.Random(seed);history=[];spent=0.0;started=time.monotonic()
    for index in range(trials):
        if spent>=total_cost or time.monotonic()-started>=seconds:break
        configuration={k:rng.choice(tuple(v)) for k,v in sorted(space.items())}
        score,cost=evaluate(configuration,seed+index,total_cost-spent)
        if not math.isfinite(score) or not math.isfinite(cost) or cost<=0 or spent+cost>total_cost:raise ValueError('Experiment exceeded declared cost')
        spent+=cost;history.append({'configuration':configuration,'score':score,'cost':cost,'seed':seed+index})
    return {'history':tuple(history),'spent':spent,'best':max(history,key=lambda h:h['score']) if history else None}
