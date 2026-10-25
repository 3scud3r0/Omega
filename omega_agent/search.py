"""Budgeted uniform-cost/A* search over caller-supplied pure state transitions."""
from dataclasses import dataclass
import heapq,itertools,math,time
@dataclass(frozen=True)
class SearchResult:
    found: bool
    path: tuple
    cost: float
    expanded: int
    reason: str
def search(initial,goal,successors,key,*,heuristic=lambda state:0,max_nodes=10000,max_depth=256,wall_seconds=10):
    if not 0<max_nodes<=1000000 or not 0<max_depth<=10000 or not 0<wall_seconds<=3600:raise ValueError('Invalid search budget')
    start=time.monotonic();counter=itertools.count();queue=[];best={key(initial):0.0}
    heapq.heappush(queue,(0.0,next(counter),0.0,initial,()))
    expanded=0
    while queue:
        if expanded>=max_nodes or time.monotonic()-start>=wall_seconds:return SearchResult(False,(),0,expanded,'budget')
        _,_,cost,state,path=heapq.heappop(queue)
        if cost!=best.get(key(state)):continue
        if goal(state):return SearchResult(True,path,cost,expanded,'goal')
        expanded+=1
        if len(path)>=max_depth:continue
        for edge_index,(action,next_state,weight) in enumerate(successors(state)):
            if edge_index>=max_nodes or time.monotonic()-start>=wall_seconds:return SearchResult(False,(),0,expanded,'budget')
            if type(weight) not in (int,float) or not math.isfinite(weight) or weight<0:raise ValueError('Nonnegative finite edge cost required')
            new=cost+weight;identity=key(next_state)
            if new>=best.get(identity,math.inf):continue
            if len(best)>=max_nodes:continue
            estimate=heuristic(next_state)
            if not math.isfinite(estimate) or estimate<0:raise ValueError('Invalid heuristic')
            best[identity]=new;heapq.heappush(queue,(new+estimate,next(counter),new,next_state,path+(action,)))
    return SearchResult(False,(),0,expanded,'exhausted')
def breadth_first(initial,goal,successors,key,**budget):
    return search(initial,goal,lambda s:((a,t,1) for a,t in successors(s)),key,**budget)
