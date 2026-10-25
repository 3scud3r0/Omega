"""Composition root for bounded host model adapters and independent checkers.

The model receives a copied public problem only. Tool invocation is separately
capability-controlled; the solver does not auto-promote or auto-train itself.
"""
from dataclasses import asdict
import hashlib,json
from .problem import Problem,Goal
from .reasoning_budget import ReasoningBudget
class CognitiveAgent:
    def __init__(self,model,decode,checker,capabilities,principal,audit):
        self.model=model;self.decode=decode;self.checker=checker;self.capabilities=capabilities;self.principal=principal;self.audit=audit
    def solve(self,problem,goal,capability,*,limit=32,seconds=30):
        if type(problem) is not Problem or type(goal) is not Goal or goal.problem_id!=problem.id:raise ValueError('Problem/authorized goal mismatch')
        self.capabilities.require(capability,self.principal,'agent.solve')
        if not 1<=limit<=min(goal.max_actions,256):raise ValueError('Agent proposal limit exceeds authorized objective')
        snapshot=json.dumps(asdict(problem),sort_keys=True,separators=(',',':'),allow_nan=False)
        claims=json.loads(snapshot);claims['constraints']=tuple(claims['constraints']);bound=Problem(**claims)
        digest=hashlib.sha256(snapshot.encode()).hexdigest();budget=ReasoningBudget(limit,seconds);attempts=[]
        for raw in self.model.propose(json.loads(snapshot),limit):
            budget.spend()
            if problem.fingerprint()!=digest:raise PermissionError('Problem changed during reasoning')
            self.capabilities.require(capability,self.principal,'agent.solve')
            candidate=self.decode(raw);decision=self.checker(bound,candidate)
            if type(decision) is not dict or type(decision.get('valid')) is not bool:raise ValueError('Independent checker protocol violation')
            attempts.append({'index':len(attempts),'valid':decision['valid']})
            if decision['valid']:
                self.audit.append({'event':'problem_solved','problem':problem.id,'input_sha256':digest,'attempts':len(attempts)})
                return {'problem':problem.id,'candidate':candidate,'certificate':decision.get('certificate'),'attempts':tuple(attempts),'promoted':False}
            if len(attempts)>=limit:break
        return {'problem':problem.id,'candidate':None,'certificate':None,'attempts':tuple(attempts),'promoted':False}
