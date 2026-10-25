import time,math
class ReasoningBudget:
    def __init__(self,steps=1000,seconds=30):
        if type(steps) is not int or not 0<steps<=1000000 or not math.isfinite(seconds) or not 0<seconds<=3600:raise ValueError('Invalid reasoning budget')
        self.remaining=steps;self.deadline=time.monotonic()+seconds;self.history=[]
    def spend(self,steps=1,*,benefit=None):
        if type(steps) is not int or steps<1:raise ValueError('Invalid reasoning cost')
        if steps>self.remaining or time.monotonic()>=self.deadline:raise TimeoutError('Reasoning budget exhausted')
        self.remaining-=steps;self.history.append({'steps':steps,'benefit':benefit})
    def allocate(self,benefits,costs):
        if set(benefits)!=set(costs) or any(v<=0 for v in costs.values()):raise ValueError('Invalid allocation options')
        return tuple(sorted(benefits,key=lambda k:(-benefits[k]/costs[k],k)))
