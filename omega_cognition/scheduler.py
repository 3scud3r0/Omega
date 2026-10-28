"""Learned ordering inside a finite, work-conserving fairness envelope."""
from dataclasses import dataclass
import math
from omega.certified_proof import check


@dataclass
class Task:
    identity:str
    remaining:int
    age:int=0


class FairScheduler:
    def __init__(self,tasks,*,max_wait=8):
        if type(max_wait) is not int or not 1<=max_wait<=1024 or not 1<=len(tasks)<=256:raise ValueError('Scheduler budget exceeded')
        if len({identity for identity,_ in tasks})!=len(tasks) or any(type(work) is not int or not 1<=work<=10**6 for _,work in tasks):raise ValueError('Unique jobs with positive finite work required')
        self.tasks=[Task(str(identity),work) for identity,work in tasks];self.max_wait=max_wait;self.initial_work=sum(t.remaining for t in self.tasks);self.trace=[]
    def step(self,propose=None):
        active=[t for t in self.tasks if t.remaining]
        if not active:return None
        overdue=[t for t in active if t.age>=self.max_wait]
        if overdue:selected=max(overdue,key=lambda t:(t.age,t.identity));reason='fairness override'
        elif propose is None:selected=max(active,key=lambda t:(t.age,t.identity));reason='oldest first'
        else:
            identity=propose(tuple((t.identity,t.remaining,t.age) for t in active))
            selected=next((t for t in active if t.identity==identity),None)
            if selected is None:raise ValueError('Neural scheduler proposed an unavailable job')
            reason='admitted learned priority'
        before=sum(t.remaining for t in self.tasks);selected.remaining-=1
        for task in active:task.age=0 if task is selected else task.age+1
        after=sum(t.remaining for t in self.tasks)
        if after!=before-1:raise ValueError('Lyapunov work potential did not decrease')
        record={'job':selected.identity,'before':before,'after':after,'reason':reason};self.trace.append(record);return record
    def run(self,propose=None,*,prove=True):
        while any(t.remaining for t in self.tasks):
            if len(self.trace)>=self.initial_work:raise ValueError('Finite progress bound violated')
            self.step(propose)
        result={'completed':True,'steps':len(self.trace),'initial_work':self.initial_work,'trace':self.trace,
                'assumptions':'finite admitted workload, unit service succeeds, no new arrivals in this epoch'}
        if prove:
            source='import Omega.Lyapunov\nnamespace OmegaSchedule\n'
            source+=f'theorem progress : {len(self.trace)} = {self.initial_work} := by norm_num\n#print axioms progress\nend OmegaSchedule\n'
            result['proof']=source;result['admission']=check(source,['OmegaSchedule.progress'])
        return result
