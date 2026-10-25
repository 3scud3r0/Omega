import math
class Hypotheses:
    def __init__(self,priors):
        if not priors or len(priors)>10000 or any(not math.isfinite(v) or v<=0 for v in priors.values()):raise ValueError('Positive finite priors required')
        self.log_weights={k:math.log(v) for k,v in priors.items()};self.evidence=[]
    def update(self,likelihoods,evidence):
        if set(likelihoods)!=set(self.log_weights) or not evidence:raise ValueError('Incomplete likelihood evidence')
        if any(not math.isfinite(v) or not 0<=v<=1 for v in likelihoods.values()):raise ValueError('Invalid likelihood')
        updated={k:self.log_weights[k]+(math.log(v) if v else -math.inf) for k,v in likelihoods.items()}
        if all(v==-math.inf for v in updated.values()):raise ValueError('Evidence rejects every hypothesis')
        self.log_weights=updated;self.evidence.append(evidence)
    def posterior(self):
        maximum=max(self.log_weights.values());weights={k:math.exp(v-maximum) for k,v in self.log_weights.items()};total=sum(weights.values())
        return {k:v/total for k,v in weights.items()}
