"""Checkpointed native synthesis; controls are applied only at safe boundaries."""
import json
from pathlib import Path
import threading
import time
import uuid
from omega_native.authority import create_key,load_key
from omega_native.api import nested_ast
from omega_self_evolve_v2.bridge_lean_filter import prove_candidate
from omega_synth_mcts.search import specification
from .native import invoke
from .store import Store,encode,digest


def create_run(store,spec,*,iterations=128,max_nodes=7,capacity=1024,seed=1,backend='native',input_bounds=None,output_bounds=None):
    specification(spec)
    if type(iterations) is not int or not 1<=iterations<=4096 or type(max_nodes) is not int or not 1<=max_nodes<=63 or type(capacity) is not int or not 64<=capacity<=65536 or type(seed) is not int or not 0<=seed<2147483647:raise ValueError('Native live search budget')
    if backend not in ('native','cuda'):raise ValueError('Explicit native/CUDA backend required')
    config={'spec':spec,'iterations':iterations,'max_nodes':max_nodes,'capacity':capacity,'seed':seed,'backend':backend,
            'objectives':['4/5','1/5','0','0'],'baseline_ns':100000,'memory_budget':4096}
    if backend=='cuda':
        if input_bounds is None or output_bounds is None:raise ValueError('CUDA requires explicit input/output interval boxes')
        config['input_bounds']=input_bounds;config['output_bounds']=output_bounds
    return store.create(config=config)


def work(store,run,*,idle_timeout=300,prove=True):
    if not 1<=idle_timeout<=3600:raise ValueError('Bounded pause timeout required')
    worker='worker-'+uuid.uuid4().hex;state=store.checkpoint(run,worker,lease_seconds=300)
    if state['status'] in ('completed','failed','cancelled'):return state
    config=state['config'];spec=config['spec'];names=list(spec['variables'])
    native_spec={'variables':names,'constants':[str(c) for c in spec.get('constants',[0,1,-1])],'operators':spec.get('operators',['+','-','*','/','neg','relu']),
                 'examples':[{'inputs':[e['inputs'][n] for n in names],'output':e['output']} for e in spec['examples']]}
    root=store.root/'runs'/run;root.mkdir(parents=True,exist_ok=True)
    model_path=root/'search-state.json';native=json.loads(model_path.read_text()) if model_path.exists() else None
    iteration=state['iteration'];weights_hash=None;last_progress=time.monotonic();best=None;best_loss=None
    try:
        while True:
            state=store.checkpoint(run,worker,iteration=iteration,lease_seconds=300);config=state['config']
            if state['status']=='cancelled':return store.finish(run,worker,status='cancelled')
            if iteration>=config['iterations']:break
            if not store.take_step(run,worker):
                if time.monotonic()-last_progress>=idle_timeout:
                    store.event(run,'worker.parked',{'iteration':iteration,'reason':'paused; restart omega live work to resume'},worker)
                    with store.transaction() as db:
                        current=store._state(db,run);current['lease_until_ns']=0;store._save(db,current)
                    return store.snapshot(run)
                time.sleep(.05);continue
            last_progress=time.monotonic()
            if config['backend']=='native':
                request={'spec':native_spec,'max_nodes':config['max_nodes'],'capacity':config['capacity'],'seed':config['seed']}
                if native is not None:request['state']=native
                policy={k:config[k] for k in ('objectives','baseline_ns','memory_budget')}
                if digest(policy)!=weights_hash:request['fitness_config']=policy;weights_hash=digest(policy);store.event(run,'search.reweighted',policy,worker)
                result=invoke('live-step',request);native=result['state'];event=result['event'];iteration=event['iteration'];best=native['best'];best_loss=native['best_loss']
                temporary=model_path.with_suffix('.tmp');temporary.write_text(encode(native));temporary.replace(model_path)
                if 'source' in result:(root/'candidate.omega').write_text(result['source'])
            else:
                from .gpu import BridgeSearch
                batch=BridgeSearch().search(spec,input_bounds=config['input_bounds'],output_bounds=config['output_bounds'],iterations=1,seed=config['seed']+iteration,elite_limit=1)
                iteration+=1;event={'iteration':iteration,'backend':'cuda','candidates':batch['candidates'],'formal_admission':False}
                if batch['candidates']:best=batch['candidates'][0]['ast'];best_loss='0'
            store.event(run,'candidate.evaluated',event,worker)
        state=store.checkpoint(run,worker,iteration=iteration,lease_seconds=300)
        receipt=None
        if prove and best and __import__('fractions').Fraction(str(best_loss))==0:
            store.event(run,'proof.started',{'candidate':best,'scope':'universal contract under declared premises'},worker)
            path=store.root/'.proof-authority.seed'
            if not path.exists():
                try:create_key(path)
                except FileExistsError:pass
            key=load_key(path);ast=nested_ast(best,names) if config['backend']=='native' else best
            try:
                receipt=prove_candidate(spec,{'ast':ast},root/('proof-'+uuid.uuid4().hex),signing_key=key)
                state=store.checkpoint(run,worker,iteration=iteration,lease_seconds=300)
                if state['status']=='cancelled':
                    store.event(run,'proof.discarded',{'reason':'cancelled before formal admission'},worker);return store.finish(run,worker,status='cancelled')
                store.event(run,'proof.checked',{'receipt':receipt,'authority_public_key':key.public_key().public_bytes_raw().hex()},worker)
            except (ValueError,RuntimeError) as error:store.event(run,'proof.rejected',{'reason':str(error)[-4000:]},worker)
        return store.finish(run,worker,result={'best':best,'loss':str(best_loss),'formal_admission':receipt is not None,'source':str(root/'candidate.omega')})
    except BaseException as error:
        store.event(run,'worker.error',{'type':type(error).__name__,'reason':str(error)[-4000:]},worker)
        store.finish(run,worker,status='cancelled' if isinstance(error,KeyboardInterrupt) else 'failed',result={'error':str(error)[-4000:]})
        if isinstance(error,KeyboardInterrupt):raise
        return store.snapshot(run)
