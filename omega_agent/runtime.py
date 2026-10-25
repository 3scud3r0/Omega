"""Bind reasoning, checked tools and metadata-only episodic recording.

Models/checkers/authorization callbacks are bounded host adapters. Calls are
cooperatively checked before/after; hard CPU/wall isolation requires the host
worker/sandbox. No proposal can manufacture its own capability or approval.
"""
from dataclasses import dataclass
import hashlib
import uuid
from .problem import Problem,Goal
from .reasoning_budget import ReasoningBudget
from omega_security.capabilities import Capability
from omega_security.encoding import canonical,decode,digest,snapshot


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict
    def __post_init__(self):
        if type(self.name) is not str or not 0<len(self.name)<=256 or type(self.arguments) is not dict:raise ValueError('Typed tool request required')
        canonical(self.arguments)


@dataclass(frozen=True)
class ToolAuthorization:
    capability: Capability
    approval: object=None
    def __post_init__(self):
        if type(self.capability) is not Capability:raise TypeError('Host-issued tool capability required')


class _Proposals:
    def __init__(self,model):self.model=model;self.stream=None
    def replace(self,context,limit):
        self.close();self.stream=iter(self.model.propose(snapshot(context,max_bytes=2*1024**2,max_nodes=20000),limit))
    def next(self):return next(self.stream)
    def close(self):
        stream,self.stream=self.stream,None
        close=getattr(stream,'close',None)
        if close is not None:close()


class CognitiveAgent:
    def __init__(self,model,decode,checker,capabilities,principal,audit,*,tools=None,
                 authorize_tool=None,observe_tool=None,record_episode=None,checker_id='host-checker'):
        if not callable(decode) or not callable(checker) or not callable(getattr(model,'propose',None)):raise TypeError('Bounded model/decoder/checker adapters required')
        if tools is not None and (tools.principal!=principal or tools.verifier is not capabilities or not callable(authorize_tool)):
            raise ValueError('Tools must share the supervisor and have an authorization resolver')
        if observe_tool is not None and not callable(observe_tool):raise TypeError('Host observation filter required')
        if record_episode is not None and not callable(record_episode):raise TypeError('Host episode sink required')
        if type(checker_id) is not str or not checker_id:raise ValueError('Checker identity required')
        self.model=model;self.decode=decode;self.checker=checker;self.capabilities=capabilities
        self.principal=principal;self.audit=audit;self.tools=tools;self.authorize_tool=authorize_tool
        self.observe_tool=observe_tool;self.record_episode=record_episode;self.checker_id=checker_id

    def _event(self,run_id,event,**metadata):
        self.audit.append({'run_id':run_id,'event':event,**metadata})

    def solve(self,problem,goal,capability,*,limit=32,seconds=30):
        if type(problem) is not Problem or type(goal) is not Goal or goal.problem_id!=problem.id:raise ValueError('Problem/authorized goal mismatch')
        if type(limit) is not int or not 1<=limit<=min(goal.max_actions,256):raise ValueError('Action budget exceeds authorized goal')
        data=problem.snapshot();input_digest=hashlib.sha256(data).hexdigest();subject=goal.subject(input_digest)
        if type(capability) is not Capability or capability.issuer!=goal.authorized_by:raise PermissionError('Goal issuer does not match authorization')
        budget=ReasoningBudget(limit,seconds);run_id=uuid.uuid4().hex
        def authorize():
            budget.check(require_step=False)
            if problem.fingerprint()!=input_digest or goal.subject(input_digest)!=subject:raise PermissionError('Objective/input changed during reasoning')
            return self.capabilities.require(capability,self.principal,'agent.solve',subject=subject)
        authorize()
        public=decode(data);public['goal']={'objective':goal.objective,'max_actions':goal.max_actions}
        public['observations']=[];attempts=[];proposals=_Proposals(self.model)
        self._event(run_id,'agent_started',problem_sha256=input_digest,goal_sha256=subject)
        try:
            proposals.replace(public,budget.remaining)
            result=self._solve(problem,goal,subject,data,public,budget,proposals,attempts,authorize,run_id)
        except BaseException as exc:
            try:self._event(run_id,'agent_failed',error_type=type(exc).__name__,goal_sha256=subject)
            except Exception:pass
            raise
        finally:
            try:proposals.close()
            except Exception as exc:
                self._event(run_id,'provider_cleanup_failed',error_type=type(exc).__name__)
                raise
        authorize()
        result.update(run_id=run_id,goal_sha256=subject,checker_id=self.checker_id,promoted=False)
        result['remaining_actions']=budget.remaining
        self._event(run_id,'agent_finished',status=result['status'],attempts=len(attempts),goal_sha256=subject)
        if self.record_episode is not None:
            from omega_memory.episodes import Episode
            # Store only identifiers/digests; raw problem/tool data is not replayed.
            outcome={'status':result['status'],'problem_sha256':input_digest,'goal_sha256':subject,'attempts':len(attempts)}
            if result['candidate'] is not None:outcome['candidate_sha256']=digest(result['candidate'])
            evidence=(digest(result['certificate']),) if result['certificate'] is not None else ()
            self.record_episode(Episode(run_id,problem.id,outcome,evidence,goal.authorized_by,sensitive=True))
        return result

    def _solve(self,problem,goal,subject,data,public,budget,proposals,attempts,authorize,run_id):
        for _ in range(budget.remaining):
            budget.check();authorize()
            try:raw=proposals.next()
            except StopIteration:break
            budget.spend();authorize()
            try:
                candidate=self.decode(raw)
                if not isinstance(candidate,ToolRequest):candidate_bytes=canonical(candidate)
            except (ValueError,TypeError,UnicodeError,RecursionError) as exc:
                attempts.append({'index':len(attempts),'kind':'candidate','valid':False,'error_type':type(exc).__name__})
                self._event(run_id,'candidate_rejected',index=len(attempts)-1,error_type=type(exc).__name__)
                continue
            if isinstance(candidate,ToolRequest):
                if self.tools is None:raise PermissionError('No tools configured for this agent')
                request=self.tools.request(candidate.name,candidate.arguments);request_sha=digest(request)
                authorization=self.authorize_tool(subject,snapshot(request))
                authorize()
                if authorization is None:
                    attempts.append({'index':len(attempts),'kind':'tool','tool':candidate.name,'request_sha256':request_sha,'status':'awaiting_approval'})
                    self._event(run_id,'tool_approval_required',request_sha256=request_sha)
                    return {'status':'awaiting_approval','problem':problem.id,'candidate':None,'certificate':None,
                            'request':request,'request_sha256':request_sha,'attempts':tuple(attempts)}
                if type(authorization) is not ToolAuthorization:raise PermissionError('Invalid host tool authorization')
                output=self.tools.call(candidate.name,request['arguments'],authorization.capability,approval=authorization.approval)
                authorize()
                observation={'kind':'untrusted_tool_output','tool':candidate.name,'request_sha256':request_sha,
                             'response_sha256':digest(output,max_bytes=8*1024**2),'authority':False}
                if self.observe_tool is not None:
                    filtered=self.observe_tool(subject,snapshot(request),snapshot(output,max_bytes=8*1024**2))
                    if filtered is not None:observation['data']=snapshot(filtered,max_bytes=65536)
                public['observations'].append(observation)
                # The accumulated context remains bounded even if all actions use tools.
                canonical(public,max_bytes=2*1024**2,max_nodes=20000)
                attempts.append({'index':len(attempts),'kind':'tool','tool':candidate.name,'request_sha256':request_sha,'status':'completed'})
                self._event(run_id,'tool_observed',request_sha256=request_sha,response_sha256=observation['response_sha256'])
                if budget.remaining:proposals.replace(public,budget.remaining)
                continue
            checked_candidate=decode(candidate_bytes)
            decision=self.checker(Problem.from_snapshot(data),checked_candidate)
            authorize()
            if canonical(checked_candidate)!=candidate_bytes:raise ValueError('Checker mutated the proposed candidate')
            decision=snapshot(decision)
            if type(decision) is not dict or type(decision.get('valid')) is not bool:raise ValueError('Independent checker protocol violation')
            candidate_sha=hashlib.sha256(candidate_bytes).hexdigest()
            attempts.append({'index':len(attempts),'kind':'candidate','valid':decision['valid'],'candidate_sha256':candidate_sha})
            self._event(run_id,'candidate_checked',candidate_sha256=candidate_sha,valid=decision['valid'])
            if decision['valid']:
                return {'status':'solved','problem':problem.id,'candidate':decode(candidate_bytes),
                        'certificate':decision.get('certificate'),'attempts':tuple(attempts)}
        return {'status':'exhausted','problem':problem.id,'candidate':None,'certificate':None,'attempts':tuple(attempts)}
