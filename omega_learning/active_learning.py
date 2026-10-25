import math
def select(candidates,budget):
    if budget<0:raise ValueError('Negative labeling budget')
    ranked=[]
    for id,probability,cost in candidates:
        if not 0<=probability<=1 or not math.isfinite(cost) or cost<=0:raise ValueError('Invalid acquisition candidate')
        entropy=-sum(p*math.log(p) for p in (probability,1-probability) if p)
        ranked.append((entropy/cost,id,cost))
    result=[];spent=0.0
    for utility,id,cost in sorted(ranked,key=lambda r:(-r[0],r[1])):
        if spent+cost<=budget:spent+=cost;result.append(id)
    return {'ids':tuple(result),'cost':spent}
