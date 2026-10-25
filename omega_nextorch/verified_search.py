"""Verifier-in-the-loop proposal search, with immutable attempt accounting."""
import time
def search(problem,model,decode,verify,*,max_candidates=32,seconds=30):
    if not 1<=max_candidates<=256 or not 0<seconds<=3600:raise ValueError('Invalid neural search budget')
    start=time.monotonic();attempts=[]
    for raw in model.propose(problem,max_candidates):
        if len(attempts)>=max_candidates or time.monotonic()-start>=seconds:break
        candidate=decode(raw);result=verify(problem,candidate)
        if type(result) is not dict or type(result.get('valid')) is not bool:raise ValueError('Verifier protocol error')
        attempts.append({'valid':result['valid'],'elapsed':time.monotonic()-start})
        if result['valid']:return {'candidate':candidate,'certificate':result.get('certificate'),'attempts':tuple(attempts)}
    return {'candidate':None,'certificate':None,'attempts':tuple(attempts)}
