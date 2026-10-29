"""CUDA SoA MCTS and pinned elite transfer; no implicit CPU substitution."""
from fractions import Fraction as Q
import ctypes as C
import math
from omega_refine_check.syntax import tree,identifier
from omega_synth_mcts.search import specification
from .build import cuda_library
from .numeric import Rational64
from .flat import RationalInterval,FlatBatch


class CudaUnavailable(RuntimeError):pass


class Config(C.Structure):
    _fields_=[(x,C.c_uint32) for x in ('forests','capacity','rollouts','iterations','max_tokens','examples','variables','constants','elites')]+[('seed',C.c_uint64)]


class Grammar(C.Structure):
    _fields_=[('nonterminals',C.c_uint64*1),('scope',C.c_uint64),('priors',C.c_uint32*64),('prior_sum',C.c_uint32)]


class Elite(C.Structure):
    _fields_=[('tokens',C.c_uint16*63),('length',C.c_uint16),('reserved',C.c_uint16),('reward',C.c_uint32),('candidate_index',C.c_uint32),('admissible',C.c_uint8),('error',C.c_uint8),('padding',C.c_uint16)]


class Stats(C.Structure):
    _fields_=[('candidates',C.c_uint64),('nodes_evaluated',C.c_uint64),('tier1_survivors',C.c_uint64),('elapsed_ms',C.c_float),('elite_count',C.c_uint32)]


def decode_prefix(tokens,variables,constants):
    stack=[]
    if not 1<=len(tokens)<=63:raise ValueError('Bounded elite token sequence required')
    for token in reversed(tokens):
        if type(token) is not int:raise ValueError('Integer grammar token required')
        if 0<=token<len(variables):node=('var',variables[token])
        elif 32<=token<32+len(constants):node=('const',str(Q(constants[token-32])))
        elif 48<=token<=53:
            arity=2 if token<=51 else 1
            if len(stack)<arity:raise ValueError('Elite grammar underflow')
            args=[stack.pop() for _ in range(arity)];node=(('+','-','*','/','neg','relu')[token-48],*args)
        else:raise ValueError('Elite token is outside host grammar scope')
        stack.append(node)
    if len(stack)!=1:raise ValueError('Unclosed elite grammar')
    return tree(stack[0])


class CudaSearch:
    def __init__(self):
        self.library=C.CDLL(str(cuda_library()))
        if not self.library.omega_cuda_available():raise CudaUnavailable('CUDA kernels compiled, but no NVIDIA device is available')
        self.library.omega_cuda_search.argtypes=[Config,Grammar,C.POINTER(Rational64),C.POINTER(Rational64),C.POINTER(Rational64),C.POINTER(RationalInterval),C.POINTER(RationalInterval),C.POINTER(Elite),C.POINTER(Stats),C.POINTER(C.c_char),C.c_uint32]
    def search(self,spec,*,input_bounds,output_bounds,forests=8,capacity=1024,rollouts=128,iterations=64,max_nodes=15,seed=0,elite_limit=64,priors=None):
        examples=specification(spec);variables=tuple(identifier(v) for v in spec['variables'])
        constants=tuple(dict.fromkeys(str(Q(c)) for c in spec.get('constants',[0,1,-1])))
        options={'forests':(forests,1,128),'capacity':(capacity,64,65536),'rollouts':(rollouts,1,4096),
                 'iterations':(iterations,1,4096),'max_nodes':(max_nodes,1,63),'elite_limit':(elite_limit,1,64),'seed':(seed,0,2**64-1)}
        if any(type(v) is not int or not lo<=v<=hi for v,lo,hi in options.values()) or rollouts*iterations>1000000:raise ValueError('CUDA search resource budget exceeded')
        if len(variables)>32 or len(constants)>16 or len(input_bounds)!=len(variables):raise ValueError('CUDA grammar/box shape mismatch')
        bounds=[RationalInterval.from_pair(x) for x in input_bounds];limit=RationalInterval.from_pair(output_bounds)
        for env,_ in examples:
            if any(not Q(pair[0])<=env[v]<=Q(pair[1]) for v,pair in zip(variables,input_bounds)):raise ValueError('Training example lies outside the declared Tier-1 input box')
        operators=spec.get('operators',['+','-','*','/','neg','relu']);codes={'+':48,'-':49,'*':50,'/':51,'neg':52,'relu':53}
        if len(set(operators))!=len(operators) or any(x not in codes for x in operators):raise ValueError('CUDA grammar operator mismatch')
        tokens=list(range(len(variables)))+list(range(32,32+len(constants)))+[codes[x] for x in operators]
        if not tokens:raise ValueError('A complete grammar requires an atom')
        grammar=Grammar();grammar.scope=sum(1<<x for x in tokens);grammar.nonterminals[0]=grammar.scope
        priors=priors or {}
        if set(priors)-set(tokens):raise ValueError('Neural prior outside grammar scope')
        for token in tokens:
            weight=priors.get(token,1)
            if type(weight) not in (int,float) or not math.isfinite(weight) or not 0<weight<=1024:raise ValueError('Positive finite guide weight required')
            grammar.priors[token]=max(1,int(weight*1024));grammar.prior_sum+=grammar.priors[token]
        elite_count=min(elite_limit,math.ceil(rollouts*iterations/1000))
        config=Config(forests,capacity,rollouts,iterations,max_nodes,len(examples),len(variables),len(constants),elite_count,seed)
        cconstants=(Rational64*len(constants))(*map(Rational64.from_q,constants))
        inputs=(Rational64*(len(examples)*len(variables)))(*[Rational64.from_q(env[v]) for env,_ in examples for v in variables])
        targets=(Rational64*len(examples))(*[Rational64.from_q(y) for _,y in examples]);cbounds=(RationalInterval*len(bounds))(*bounds)
        climits=(RationalInterval*1)(limit);output=(Elite*elite_count)();stats=Stats();message=C.create_string_buffer(2048)
        status=self.library.omega_cuda_search(config,grammar,cconstants,inputs,targets,cbounds,climits,output,C.byref(stats),message,len(message))
        if status==77:raise CudaUnavailable(message.value.decode())
        if status:raise RuntimeError('CUDA search rejected: '+message.value.decode())
        if not 0<=stats.elite_count<=elite_count:raise ValueError('Invalid GPU elite count')
        candidates=[]
        for e in output[:stats.elite_count]:
            if not e.admissible or e.error or e.length>max_nodes:raise ValueError('Malformed GPU elite metadata')
            ast=decode_prefix(list(e.tokens[:e.length]),variables,constants)
            # Treat VRAM flags as untrusted proposals. Replay exact arithmetic
            # and the shared interval algorithm before formal Tier-2 admission.
            batch=FlatBatch.create([ast],variables);observed=batch.evaluate([env for env,_ in examples])[0]
            if any(observed['errors']) or not batch.filter(input_bounds,output_bounds)['admissible'][0]:raise ValueError('GPU candidate failed host replay')
            candidates.append({'ast':ast,'reward':int(e.reward),'index':int(e.candidate_index),'tier1_admissible':True,'formal_admission':False})
        return {'backend':'cuda','candidates':candidates,'statistics':{name:getattr(stats,name) for name,_ in stats._fields_},
                'input_bounds':input_bounds,'output_bounds':output_bounds,'formal_admission':False,
                'scope':'bounded rational Tier-1 analysis and search guidance; requires independent Lean admission'}
