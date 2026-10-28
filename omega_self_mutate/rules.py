from fractions import Fraction as Q
import hashlib
import json
from omega_refine_check.syntax import tree,parse,render,evaluate
from omega_refine_check.contracts import verify_contract
from omega_synth_mcts.search import search
from omega_selfhost.proof_protocol import encode


def variables(node):
    if node[0]=='var':return {node[1]}
    return set().union(*(variables(x) for x in node[1:] if isinstance(x,(tuple,list))))


def validate_rule(lhs,rhs):
    lhs=tree(lhs) if type(lhs) is not str else parse(lhs)
    rhs=tree(rhs) if type(rhs) is not str else parse(rhs)
    names=sorted(variables(lhs))
    def polynomial(node):
        if node[0] not in ('const','var','+','-','*','neg'):raise ValueError('Mutations are total rational polynomial rewrites')
        for child in node[1:]:
            if isinstance(child,(tuple,list)):polynomial(child)
    polynomial(lhs);polynomial(rhs)
    if lhs[0] not in ('+','-','*','neg') or rhs[0]!='var' or rhs[1] not in names or not 1<=len(names)<=4:
        raise ValueError('Optimizer mutations must eliminate a scalar expression to an existing matched variable')
    certificate=verify_contract({v:'true' for v in names},rhs,('==',('var','result'),lhs))
    statement={'lhs':lhs,'rhs':rhs,'variables':names}
    return {**statement,'id':hashlib.sha256(encode(statement)).hexdigest(),'proof':certificate}


def discover_rule(lhs,*,iterations=256,seed=0):
    lhs=parse(lhs) if type(lhs) is str else tree(lhs)
    names=sorted(variables(lhs))
    if not names:raise ValueError('A parametric rewrite is required')
    examples=[]
    for i in (-2,-1,0,1,2):
        env={v:Q(i+j) for j,v in enumerate(names)}
        examples.append({'inputs':{v:str(x) for v,x in env.items()},'output':str(evaluate(lhs,env))})
    spec={'variables':{v:'true' for v in names},'constants':[0,1,2,-1],
          'ensures':'result == '+render(lhs),'examples':examples,'operators':['+','-','*','neg']}
    result=search(spec,iterations=iterations,max_nodes=7,seed=seed,seconds=60)
    if not result['verified']:raise ValueError('MCTS did not find a universally admitted rewrite')
    return {**validate_rule(lhs,result['candidate']),'search':result}


def omega_pattern(node):
    if node[0]=='const':return ['const',node[1]]
    if node[0]=='var':return ['var',node[1]]
    return [node[0],*[omega_pattern(x) for x in node[1:]]]


def install_template(source,rule):
    # Revalidate data. A caller-supplied "proof passed" boolean is never used.
    admitted=validate_rule(rule['lhs'],rule['rhs'])
    if admitted['id']!=rule['id']:raise ValueError('Rule statement digest mismatch')
    if 'funcao synth_match(' in source:raise ValueError('Start a new generation from a recorded baseline, not an arbitrary prepatched compiler')
    matcher='''funcao synth_total(nodes,i) {
  var n=nodes[i];var op=n["op"];se(op=="/"){se(nodes[n["args"][1]]["op"]!="num" || number(nodes[n["args"][1]]["v"])==0){retornar 0;}}
  var j=0;enquanto(j<len(n["args"])){se(!synth_total(nodes,n["args"][j])){retornar 0;}j=j+1;}retornar 1;
}
funcao synth_match(pattern,index,nodes,env) {
  var op=pattern[0];var node=nodes[index];
  se(op=="var"){se(!synth_total(nodes,index)){retornar 0;}se(has(env,pattern[1])){retornar env[pattern[1]]==index;}put(env,pattern[1],index);retornar 1;}
  se(op=="const"){retornar node["op"]=="num" && number(node["v"])==number(pattern[1]);}
  se(op=="neg"){se(node["op"]!="neg"){retornar 0;}retornar synth_match(pattern[1],node["args"][0],nodes,env);}
  se(node["op"]!=op || len(node["args"])!=2){retornar 0;}
  retornar synth_match(pattern[1],node["args"][0],nodes,env) && synth_match(pattern[2],node["args"][1],nodes,env);
}
'''
    anchor='funcao literal(nodes,i,q)'
    if source.count(anchor)!=1:raise ValueError('Unknown compiler source layout')
    source=source.replace(anchor,matcher+anchor,1)
    pattern=omega_pattern(rule['lhs']);outer=pattern[0]
    arity=len(pattern)-1
    matches=' && '.join(f'synth_match(pattern[{i+1}],n["args"][{i}],nodes,captures)' for i in range(arity))
    snippet=(f'  se(n["forma"]==[] && n["op"]=={json.dumps(outer)} && len(n["args"])=={arity}){{var captures=obj();'
             f'var pattern=parsejson({json.dumps(json.dumps(pattern,separators=(",",":")))});'
             f'se({matches}){{retornar ["synth_{rule["id"]}",captures[{json.dumps(rule["rhs"][1])}]];}}}}\n')
    end='  retornar [];\n}\nfuncao optimize(ir)'
    if source.count(end)!=1:raise ValueError('Unknown optimizer boundary')
    source=source.replace(end,snippet+end,1)
    source=source.replace('put(cert,"formato","omega-opt-cert-1")','put(cert,"formato","omega-opt-cert-2")')
    return source
