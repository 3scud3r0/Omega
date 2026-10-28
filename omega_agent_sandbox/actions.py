"""Turn an action intent into code, a Hoare obligation and a pinned snapshot."""
import hashlib
import json
from omega_refine_check.syntax import parse,rational,evaluate,substitute,render,identifier
from omega_refine_check.contracts import verify_contract
from omega_selfhost.proof_protocol import encode
from .policy import Policy


def _and(predicates):
    result=('true',)
    for p in predicates:result=('and',result,p)
    return result


def plan(policy,state,proposal):
    if type(policy) is not Policy:raise TypeError('Immutable host policy required')
    data=policy.data
    if type(state) is not dict or set(state)!={'version','values'} or type(state['version']) is not int or state['version']<0 or set(state['values'])!=set(data['state']):raise ValueError('Invalid state snapshot')
    if type(proposal) is not dict or set(proposal)!={'action','parameters','nonce','expected_version'}:raise ValueError('Unknown action proposal')
    if type(proposal['expected_version']) is not int or proposal['expected_version']!=state['version']:raise ValueError('Stale action proposal')
    identifier(proposal['action'])
    if type(proposal['nonce']) is not str or not 1<=len(proposal['nonce'])<=128 or any(ord(c)<32 for c in proposal['nonce']):raise ValueError('Bounded action nonce required')
    if proposal['action'] not in data['actions']:raise PermissionError('Action is not admitted by the policy')
    action=data['actions'][proposal['action']]
    if type(proposal['parameters']) is not dict or set(proposal['parameters'])!=set(action['parameters']):raise ValueError('Action parameter mismatch')
    values={k:rational(state['values'][k]) for k in data['state']}
    params={k:rational(proposal['parameters'][k]) for k in action['parameters']}
    env={**values,**params}
    for name,predicate in {**data['state'],**action['parameters']}.items():
        if evaluate(parse(predicate),{**env,'self':env[name]}) is not True:raise ValueError('State or parameter invariant violated')
    if any(evaluate(parse(p),env) is not True for p in action['requires']):raise ValueError('Action precondition is false')
    updates={name:parse(expr) for name,expr in action['updates'].items()}
    after={name:evaluate(expr,env) for name,expr in updates.items()}
    if any(evaluate(parse(predicate),{**after,'self':after[name]}) is not True for name,predicate in data['state'].items()):raise ValueError('Action would violate a state invariant')
    post=[substitute(parse(predicate),{'self':updates[name],**updates}) for name,predicate in data['state'].items()]
    variables={**data['state'],**action['parameters']}
    expression=('vector',tuple(updates.values()))
    statement={'policy_sha256':policy.sha256,'state':{'version':state['version'],'values':{k:str(v) for k,v in values.items()}},
               'proposal':{**proposal,'parameters':{k:str(v) for k,v in params.items()}},
               'post_state':{'version':state['version']+1,'values':{k:str(v) for k,v in after.items()}},'effect':action['effect']}
    source='\n'.join(f'parametro {name}={render(("const",str(value)))};' for name,value in env.items())+'\n'
    for i,(name,expr) in enumerate(updates.items()):source+=f'tensor after_{i}={render(expr)};\nmostrar after_{i};\n'
    return statement,source,variables,expression,_and(post),action['requires']


def prepare(policy,state,proposal,*,signing_key):
    statement,program,variables,expression,post,requires=plan(policy,state,proposal)
    proof=verify_contract(variables,expression,post,requires=requires)
    payload={'format':'omega-action-pcc-1','statement':statement,
             'program_sha256':hashlib.sha256(program.encode()).hexdigest(),
             'proof_sha256':hashlib.sha256(proof['source'].encode()).hexdigest()}
    subject=hashlib.sha256(encode(payload)).hexdigest()
    return {'payload':payload,'subject':subject,'program':program,'proof':proof['source'],
            'admission':proof['admission'],'signature':signing_key.sign(encode(payload)).hex()}
