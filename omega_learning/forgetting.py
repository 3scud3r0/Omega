import math
class ForgettingMonitor:
    def __init__(self):self.best={};self.history=[]
    def observe(self,version,scores):
        if not scores or any(not math.isfinite(v) for v in scores.values()):raise ValueError('Finite skill/domain scores required')
        losses={skill:max(0,self.best.get(skill,value)-value) for skill,value in scores.items()}
        for skill,value in scores.items():self.best[skill]=max(value,self.best.get(skill,value))
        record={'version':version,'scores':dict(scores),'forgetting':losses,'worst':max(losses.values())};self.history.append(record)
        return record
