"""Four independent processes exercising the Omega BFT state machine.

Trusted test/router adapter, not a production transport or native Ed25519.
Effects are signed only after durable state publication. Membership is fixed.
No process, listener, network message or promotion starts on import.
"""
from collections import deque
import hashlib
import multiprocessing
import os
from pathlib import Path
import tempfile
from omega_security.encoding import canonical,decode
from .models import call,build


def signing(body):
    return ('omega-bft-v1|'+body['chain']+'|'+str(body['height'])+'|'+str(body['round'])+'|'+body['phase']+'|'+body['value']+'|'+body['parent']+'|'+str(body['pol_round'])+'|'+body['sender']).encode()


def key(seed):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(seed)


def public(private):
    from cryptography.hazmat.primitives import serialization
    return private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()


def sign(body,private):return {'body':body,'signature':private.sign(signing(body)).hex()}


def _worker(pipe,directory,seed,members):
    private=key(seed);identity=public(private);state=None
    path=Path(directory);path.mkdir(mode=0o700)
    try:
        while True:
            command=pipe.recv()
            if command is None:break
            request={'members':members,'self':identity,'chain':'omega-test','events':command}
            if state is not None:request['state']=state
            result=call('bft',request);state=result['state']
            payload=canonical(state,max_bytes=1024**2,max_nodes=60000,max_depth=32)
            temporary=path/'state.tmp'
            with temporary.open('wb') as stream:
                stream.write(payload);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path/'state.json')
            fd=os.open(path,os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
            effects=[sign(body,private) for body in result['effects_after_persist']]
            pipe.send({'state':state,'messages':effects,'commits':result['commits'],
                       'rejected':result['rejected'],'equivocations':result['equivocations'],'pid':os.getpid(),
                       'state_sha256':hashlib.sha256(payload).hexdigest()})
    except BaseException as exc:
        pipe.send({'error':type(exc).__name__+': '+str(exc)})
    finally:pipe.close()


def experiment(directory,*,max_messages=256,value=None):
    """f=1 adversary equivocates and withholds; bounded delays, then good round.

    Demonstrates this schedule only, not a universal liveness theorem. Four
    actual Python supervisor processes independently execute sandboxed Omega
    binaries; process 0 is adversarial and its honest effects are suppressed.
    """
    if type(max_messages) is not int or not 32<=max_messages<=1024:raise ValueError('Message budget')
    if value is not None and (type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value)):raise ValueError('BFT value digest')
    root=Path(directory)
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True)
    build()
    seeds=[hashlib.sha256(f'omega-bft-test-{i}'.encode()).digest() for i in range(4)]
    keys=[key(seed) for seed in seeds];members=[public(k) for k in keys]
    context=multiprocessing.get_context('spawn');processes=[];pipes=[];states={};pids=set();queue=deque();delayed=[];deliveries=0;rejected=0;evidence=[]
    def step(index,events):
        nonlocal rejected
        pipes[index].send(events)
        if not pipes[index].poll(120):raise TimeoutError('BFT worker response budget')
        out=pipes[index].recv()
        if 'error' in out:raise RuntimeError(out['error'])
        states[index]=out['state'];pids.add(out['pid']);rejected+=out['rejected'];evidence.extend(out['equivocations'])
        if index:
            for message in out['messages']:
                for receiver in (1,2,3):queue.append((receiver,{'kind':'message','message':message}))
            for commit in out['commits']:
                for receiver in (1,2,3):queue.append((receiver,{'kind':'commit','entry':commit}))
        return out
    def drain():
        nonlocal deliveries
        while queue:
            if deliveries>=max_messages:raise RuntimeError('BFT message quota')
            receiver,event=queue.popleft();deliveries+=1
            if deliveries%7==0:delayed.append((receiver,event))
            else:step(receiver,[event])
        if delayed:
            queue.extend(reversed(delayed));delayed.clear();drain()
    def body(sender,phase,value,round=0):
        return {'chain':'omega-test','height':0,'round':round,'phase':phase,'value':value,
                'parent':'0'*64,'pol_round':-1,'sender':members[sender]}
    try:
        for index,seed in enumerate(seeds):
            parent,child=context.Pipe();p=context.Process(target=_worker,args=(child,root/f'node-{index}',seed,members));p.start();child.close();pipes.append(parent);processes.append(p)
        for i in range(4):step(i,[])
        # Distinct signed proposals and double votes by member 0. No honest
        # quorum can be assembled in this round; duplicate votes count once.
        a,b=value or hashlib.sha256(b'proposal-A').hexdigest(),hashlib.sha256(b'proposal-B').hexdigest()
        for i in (1,2,3):
            step(i,[{'kind':'message','message':sign(body(0,'propose',b if i==2 else a),keys[0])}])
            step(i,[{'kind':'message','message':sign(body(0,'prevote',a),keys[0])},
                    {'kind':'message','message':sign(body(0,'prevote',b),keys[0])}])
        # Simulate Byzantine withholding of both equivocated votes on the wire
        # to other peers: retain state/evidence but delay honest round-0 traffic
        # until round 1; nodes must preserve any locks they already established.
        queue.clear()
        forged=sign(body(1,'precommit',b),keys[0])
        for i in (1,2,3):step(i,[{'kind':'message','message':forged},{'kind':'timeout'}])
        # Honest proposer 1 supplies the value. All three correct processes are
        # now delivered messages fairly; adversarial process 0 stays silent.
        proposal=sign(body(1,'propose',a,1),keys[1])
        for i in (1,2,3):step(i,[{'kind':'message','message':proposal}])
        drain()
        ledgers=[states[i]['ledger'] for i in (1,2,3)]
        signatures=[[(e['height'],e['value'],e['parent']) for e in ledger] for ledger in ledgers]
        if not signatures[0] or any(s!=signatures[0] for s in signatures):raise AssertionError('Honest BFT ledgers diverged')
        report={'format':'omega-bft-process-experiment-1','processes':sorted(pids),'faults':1,
                'delivered':deliveries,'delays_injected':True,'equivocations':len(evidence),'rejected':rejected,
                'honest_ledgers':signatures,'converged':True,'liveness_scope':'this finite delayed schedule after an honest proposer',
                'ed25519_backend':'host reference / native Omega OpenSSL primitive'}
        (root/'report.json').write_bytes(canonical(report));return report
    finally:
        for pipe in pipes:
            try:pipe.send(None)
            except (BrokenPipeError,EOFError):pass
            pipe.close()
        for process in processes:
            process.join(5)
            if process.is_alive():process.terminate();process.join(5)
