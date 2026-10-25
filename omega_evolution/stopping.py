import math
class StopPolicy:
    def __init__(self,patience=5,max_risk=.01,max_uncertainty=.5):
        if patience<1 or not 0<=max_risk<=1 or not 0<=max_uncertainty<=1:raise ValueError('Invalid stopping policy')
        self.patience=patience;self.max_risk=max_risk;self.max_uncertainty=max_uncertainty;self.stagnation=0
    def observe(self,gain_interval,risk,uncertainty):
        values=(*gain_interval,risk,uncertainty)
        if len(gain_interval)!=2 or any(not math.isfinite(v) for v in values):raise ValueError('Invalid stopping evidence')
        if risk>self.max_risk:return 'risk'
        if uncertainty>self.max_uncertainty:return 'uncertainty'
        self.stagnation=0 if gain_interval[0]>0 else self.stagnation+1
        return 'stagnation' if self.stagnation>=self.patience else None
