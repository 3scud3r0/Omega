from dataclasses import dataclass
import math
@dataclass(frozen=True)
class Alert:
    metric: str
    observed: float
    limit: float
    action: str
class Monitor:
    def __init__(self,limits):self.limits=dict(limits);self.alerts=[]
    def observe(self,metrics):
        for name,value in metrics.items():
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid monitored measurement')
            if name in self.limits and value>self.limits[name]:self.alerts.append(Alert(name,value,self.limits[name],'block_and_review'))
        return tuple(self.alerts)
    @property
    def blocked(self):return bool(self.alerts)
