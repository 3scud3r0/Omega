"""Idle-only finite epochs; --forever is an explicit supervisor operation."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from .curiosity_engine import CuriosityEngine
from omega_self_evolve_v2.bridge_lean_filter import LeanBridge
from omega_synth_mcts.search import search as host_mcts
from omega_gpu_mcts.flat import FlatBatch


class IdleGate:
    def __init__(self,cpu_threshold=0.5,gpu_threshold=20):
        if not 0<=cpu_threshold<=1 or not 0<=gpu_threshold<=100:raise ValueError('Utilization thresholds must be bounded')
        self.cpu_threshold=cpu_threshold;self.gpu_threshold=gpu_threshold
    def idle(self,*,require_gpu=True):
        cpu=os.getloadavg()[0]/max(1,os.cpu_count() or 1)
        if cpu>self.cpu_threshold:return False
        if not require_gpu:return True
        import shutil
        tool=shutil.which('nvidia-smi')
        if not tool:return False
        result=subprocess.run([tool,'--query-gpu=utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
        if result.returncode:return False
        values=[int(x.strip()) for x in result.stdout.splitlines() if x.strip()]
        return bool(values) and max(values)<=self.gpu_threshold


async def cycle(engine,directory,*,signing_key,backend='cuda',gate=None,iterations=256,evolve=False,install=False,commit=False,replace_source=False):
    if backend not in ('cuda','host-reference'):raise ValueError('Explicit CUDA or host-reference backend required')
    if gate is not None and not gate.idle(require_gpu=backend=='cuda'):return {'idle':False,'attempted':False}
    task=engine.task();root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    if backend=='cuda':
        from omega_gpu_mcts.backend import CudaSearch
        gpu=CudaSearch()
        batch=await asyncio.to_thread(gpu.search,task['spec'],input_bounds=task['input_bounds'],output_bounds=task['output_bounds'],iterations=max(1,min(4096,iterations)),elite_limit=4)
    else:
        proposal=await asyncio.to_thread(host_mcts,task['spec'],iterations=iterations,seconds=30,verify=False,seed=engine.seed,max_nodes=15)
        candidates=[]
        if proposal['candidate'] is not None:
            ast=proposal['candidate'];flat=FlatBatch.create([ast],task['spec']['variables'])
            if flat.filter(task['input_bounds'],task['output_bounds'])['admissible'][0]:candidates=[{'ast':ast,'formal_admission':False}]
        batch={'backend':'host-reference','candidates':candidates,'formal_admission':False,
               'input_bounds':task['input_bounds'],'output_bounds':task['output_bounds']}
    with LeanBridge(signing_key=signing_key,queue_capacity=4) as bridge:formal=await bridge.consume(task['spec'],batch,root/'tier2')
    observation=engine.observe(task,formal['accepted']>0)
    record={'format':'omega-curiosity-epoch-1','backend':backend,'task':task,'tier1':batch,'tier2':formal,
            'observation':observation,'attempted':True,'idle':True,'optimality_proved':False}
    if evolve and task['family']=='compiler-identity' and formal['accepted']:
        from omega_self_evolve_v2.cycle import evolve_from_receipt
        chosen=next(r for r in formal['results'] if r['accepted'])
        try:
            generation=await asyncio.to_thread(evolve_from_receipt,task.get('lhs','(x*2)-x'),chosen['receipt'],chosen['directory'],root/'generation',
                                              public_key=signing_key.public_key(),install=install,commit=commit,replace_source=replace_source)
            record['evolution']={'accepted':True,'fixed_point':generation['bootstrap']['fixed_point'],'objective':generation['objective'],'runtime_epoch':generation.get('runtime_epoch')}
        except ValueError as error:
            record['evolution']={'accepted':False,'reason':str(error)[-4000:]}
    from omega_selfhost.proof_protocol import encode
    (root/'epoch.json').write_bytes(encode(record));return record


def sleep_epoch(epochs,directory,*,signing_key):
    from .bank import consolidate,AbstractionBank
    records=[]
    for epoch in epochs[-32:]:
        for result in epoch.get('tier2',{}).get('results',[]):
            if result.get('accepted'):records.append({'receipt':result['receipt'],'directory':result['directory']})
    records=records[-64:]
    proposals=consolidate(records,public_key=signing_key.public_key()) if len(records)>1 else []
    bank=AbstractionBank(directory,public_key=signing_key.public_key());promoted=[]
    for proposal in proposals[:16]:promoted.append(bank.promote(proposal,signing_key=signing_key)['id'])
    return {'accepted_records':len(records),'proposals':len(proposals),'promoted':promoted}


def authority(directory):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    root=Path(directory);root.mkdir(parents=True,exist_ok=True);path=root/'.authority.key'
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:raise PermissionError('Private authority file requires regular mode 0600')
        return Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    key=Ed25519PrivateKey.generate()
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(),0o600);stream.write(key.private_bytes_raw())
    (root/'authority-public.hex').write_text(key.public_key().public_bytes_raw().hex()+'\n')
    return key


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(prog='omega curiosity')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--backend',choices=['cuda','host-reference'],default='cuda')
    parser.add_argument('--cycles',type=int,default=1);parser.add_argument('--forever',action='store_true');parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--interval',type=float,default=10)
    parser.add_argument('--evolve',action='store_true');parser.add_argument('--install',action='store_true')
    parser.add_argument('--commit',action='store_true');parser.add_argument('--replace-source',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.cycles<=1024 or not 1<=args.interval<=60:parser.error('Bounded cycles and polling interval required')
    if (args.install or args.commit or args.replace_source) and not args.evolve:parser.error('Adoption requires --evolve')
    key=authority(args.output);engine=CuriosityEngine(args.seed);gate=IdleGate();completed=0
    history=args.output/'history.json';epochs=[]
    if history.exists():
        data=json.loads(history.read_text())
        if type(data) is not list or len(data)>32:raise ValueError('Bounded epoch history required')
        epochs=data
        for epoch in epochs:
            if 'task' in epoch:engine.observe(epoch['task'],epoch.get('tier2',{}).get('accepted',0)>0)
    try:
        while args.forever or completed<args.cycles:
            if gate.idle(require_gpu=args.backend=='cuda'):
                result=asyncio.run(cycle(engine,args.output/f'epoch-{time.time_ns()}',signing_key=key,backend=args.backend,gate=gate,
                                        evolve=args.evolve,install=args.install,commit=args.commit,replace_source=args.replace_source))
                if result['attempted']:
                    epochs=(epochs+[result])[-32:]
                    consolidation=sleep_epoch(epochs,args.output/'abstractions',signing_key=key)
                    (args.output/'sleep.json').write_text(json.dumps(consolidation,sort_keys=True)+'\n')
                    temporary=history.with_suffix('.tmp');temporary.write_text(json.dumps(epochs,sort_keys=True)+'\n');temporary.replace(history)
                print(json.dumps({'attempted':result['attempted'],'backend':args.backend,'accepted':result.get('tier2',{}).get('accepted',0)}),flush=True);completed+=1
            elif not args.forever:return 0
            if args.forever:time.sleep(args.interval)
    except KeyboardInterrupt:return 130
    return 0


if __name__=='__main__':raise SystemExit(main())
