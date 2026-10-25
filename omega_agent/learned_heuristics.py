"""Online ridge heuristic; learning is separated from held-out evaluation."""
import math
class LinearHeuristic:
    def __init__(self,dimension,rate=.01,l2=.001):
        if not 0<dimension<=4096 or not 0<rate<=1 or l2<0:raise ValueError('Invalid heuristic parameters')
        self.weights=[0.0]*dimension;self.rate=rate;self.l2=l2;self.training_ids=set()
    def predict(self,features):
        if len(features)!=len(self.weights) or any(not math.isfinite(x) for x in features):raise ValueError('Feature mismatch')
        return sum(w*x for w,x in zip(self.weights,features))
    def learn(self,id,features,target):
        if not math.isfinite(target):raise ValueError('Finite target required')
        error=self.predict(features)-target
        self.weights=[w-self.rate*(error*x+self.l2*w) for w,x in zip(self.weights,features)];self.training_ids.add(id)
    def evaluate(self,cases):
        errors=[]
        for id,features,target in cases:
            if id in self.training_ids:raise ValueError('Held-out contamination')
            errors.append((self.predict(features)-target)**2)
        if not errors:raise ValueError('Held-out cases required')
        return {'mse':sum(errors)/len(errors),'cases':len(errors)}
