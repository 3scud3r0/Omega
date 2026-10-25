import math
class Router:
    def __init__(self):self.metrics={}
    def observe(self,domain,model,correct,cost):
        if type(correct) is not bool or not math.isfinite(cost) or cost<=0:raise ValueError('Invalid routing observation')
        key=(domain,model);n,success,total=self.metrics.get(key,(0,0,0.0));self.metrics[key]=(n+1,success+correct,total+cost)
    def choose(self,domain,models,min_success=.5):
        ranked=[]
        for model in models:
            n,success,cost=self.metrics.get((domain,model),(0,0,0))
            if n and success/n>=min_success:ranked.append((-(success+1)/(n+2)/(cost/n),model))
        if not ranked:raise ValueError('No model has sufficient routing evidence')
        return min(ranked)[1]
