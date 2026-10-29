"""Small host adapters; the database, message verification and search run natively."""
from pathlib import Path
from .codec import decode
from .toolchain import result


def insert(root,path,head,key,document,*,authority,permit,policy):
    root=Path(root).resolve()
    return result('db-insert',dict(root=str(root),path=path,head=head,key=key,document=document,authority=authority,permit=permit,policy=policy),writable=[root])


def lookup(root,path,head,key):
    root=Path(root).resolve()
    return decode(result('db-get',dict(root=str(root),path=path,head=head,key=key),readonly=[root])['document'])


def audit(root,path,head):
    root=Path(root).resolve()
    return result('db-audit',dict(root=str(root),path=path,head=head),readonly=[root])


def seal(message,certificate,*,key_path):
    key_path=Path(key_path).resolve()
    return result('message-seal',dict(message=message,certificate=certificate,key_root=str(key_path.parent),key_path=key_path.name),readonly=[key_path.parent])


def receive(root,path,head,packet,*,recipient,channel,policy,senders,authority):
    root=Path(root).resolve()
    return result('message-receive',dict(root=str(root),path=path,head=head,packet=packet,recipient=recipient,channel=channel,policy=policy,senders=senders,authority=authority),writable=[root])


def nested_ast(flat,names):
    values=[];ops={2:'+',3:'-',4:'*',5:'/',6:'neg',7:'relu'}
    if type(flat) is not list or not 1<=len(flat)<=63:raise ValueError('Bounded topological AST required')
    for i,row in enumerate(flat):
        if type(row) is not list or len(row)!=4:raise ValueError('Malformed flat AST')
        op,l,r,data=row
        if op==0:node=('const',str(__import__('fractions').Fraction(data)))
        elif op==1:
            if type(data) is not int or not 0<=data<len(names):raise ValueError('Unbound input')
            node=('var',names[data])
        else:
            if op not in ops or type(l) is not int or not 0<=l<i or op<6 and (type(r) is not int or not 0<=r<i):raise ValueError('Forward or invalid AST edge')
            node=(ops[op],values[l]) if op>=6 else (ops[op],values[l],values[r])
        values.append(node)
    return values[-1]


def synthesize(spec,directory,*,signing_key,iterations=128,max_nodes=7,tree_capacity=4096,seed=1):
    from omega_synth_mcts.search import specification
    from omega_self_evolve_v2.bridge_lean_filter import prove_candidate
    specification(spec)  # Check examples and contracts before native search.
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=False)
    native={'variables':list(spec['variables']),'constants':[str(x) for x in spec.get('constants',[0,1,-1])],
            'operators':spec.get('operators',['+','-','*','/','neg','relu']),
            'examples':[{'inputs':[e['inputs'][name] for name in spec['variables']],'output':e['output']} for e in spec['examples']]}
    candidate=result('search',dict(spec=native,iterations=iterations,max_nodes=max_nodes,tree_capacity=tree_capacity,seed=seed),writable=[root],output_root=root)
    ast=nested_ast(candidate['ast'],list(spec['variables']))
    receipt=prove_candidate(spec,{'ast':ast},root/'proof',signing_key=signing_key)
    return {**candidate,'formal_admission':True,'receipt':receipt,'proof_directory':str(root/'proof'),'candidate_source':str(root/'candidate.omega')}
