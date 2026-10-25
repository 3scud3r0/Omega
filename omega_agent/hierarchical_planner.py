from dataclasses import dataclass
@dataclass(frozen=True)
class Task:
    id: str
    description: str
    dependencies: tuple[str,...]=()
    priority: int=0
class Plan:
    def __init__(self,tasks):
        tasks=tuple(tasks)
        if len(tasks)>10000 or len({t.id for t in tasks})!=len(tasks):raise ValueError('Invalid task graph')
        self.tasks={t.id:t for t in tasks}
        if any(d not in self.tasks for t in tasks for d in t.dependencies):raise ValueError('Missing dependency')
        self.order()
    def order(self):
        pending=set(self.tasks);done=set();result=[]
        while pending:
            ready=sorted((n for n in pending if set(self.tasks[n].dependencies)<=done),key=lambda n:(-self.tasks[n].priority,n))
            if not ready:raise ValueError('Cyclic task graph')
            for n in ready:pending.remove(n);done.add(n);result.append(n)
        return tuple(result)
    def ready(self,completed):
        return tuple(n for n in self.order() if n not in completed and set(self.tasks[n].dependencies)<=set(completed))
def decompose(root,expand,limit=256):
    pending=[root];tasks=[];seen=set()
    while pending:
        task=pending.pop(0)
        if task.id in seen:raise ValueError('Repeated hierarchical task')
        seen.add(task.id);tasks.append(task)
        if len(tasks)>limit:raise ValueError('Decomposition budget exceeded')
        pending.extend(expand(task))
    return Plan(tasks)
