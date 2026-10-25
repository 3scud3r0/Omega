import math
def entropy(probabilities):
    values=tuple(probabilities)
    if not values or any(not math.isfinite(p) or p<0 for p in values) or abs(sum(values)-1)>1e-6:raise ValueError('Probability simplex required')
    return -sum(p*math.log(p) for p in values if p)
def selective_risk(confidences,correct,threshold):
    if len(confidences)!=len(correct) or not 0<=threshold<=1:raise ValueError('Invalid selective observations')
    accepted=[bool(ok) for c,ok in zip(confidences,correct) if c>=threshold]
    return {'coverage':len(accepted)/len(correct) if correct else 0.0,
            'risk':1-sum(accepted)/len(accepted) if accepted else None,'accepted':len(accepted)}
def abstain(probabilities,threshold=.8):
    entropy(probabilities)
    return max(probabilities)<threshold
