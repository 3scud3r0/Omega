"""Training creates an isolated candidate; rejected state never replaces baseline."""
import copy,math
def update(model,training,retained,train,evaluate,tolerance=0.0):
    if tolerance<0:raise ValueError('Negative regression tolerance')
    candidate=copy.deepcopy(model);baseline=evaluate(model,retained)
    train(candidate,training);after=evaluate(candidate,retained)
    if set(after)!=set(baseline) or any(not math.isfinite(x) for x in (*baseline.values(),*after.values())):raise ValueError('Invalid retained metrics')
    regressions={k:after[k]-v for k,v in baseline.items() if after[k]<v-tolerance}
    return {'candidate':candidate,'accepted_for_review':not regressions,'regressions':regressions,'before':baseline,'after':after,'promoted':False}
