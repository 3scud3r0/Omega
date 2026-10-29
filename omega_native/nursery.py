"""Idle-only, bounded native synthesis epochs with explicit optional persistence.

No daemon is installed. --forever opts into supervision until interrupted; the
same proof, artifact and measured-improvement gates apply in automatic mode.
"""
import json
from pathlib import Path
import time
from omega_autotelic.curiosity_driver import IdleGate,sleep_epoch
from omega_autotelic.curiosity_engine import CuriosityEngine
from .authority import Authority,create_key,load_key
from .api import synthesize
from .incubator import prepare,adopt


def epoch(engine,directory,*,authority,iterations=128,approval_mode='auto',evolve=False,install=False,commit=False,family=None):
    root=Path(directory);root.mkdir(parents=True,exist_ok=False);task=engine.task(family)
    record={'format':'omega-native-nursery-1','task':task,'backend':'native-cpu-mcts','approval_mode':approval_mode,'attempted':True}
    try:
        solved=synthesize(task['spec'],root/'search',signing_key=authority.key,iterations=iterations,max_nodes=15,seed=engine.seed%2147483647)
        record['tier2']={'accepted':1,'results':[{'accepted':True,'receipt':solved['receipt'],'directory':solved['proof_directory']}]}
        if evolve and task['family']=='compiler-identity':
            try:
                prepare(task['lhs'],solved['receipt'],solved['proof_directory'],root/'proposal',authority=authority)
                record['adoption']=adopt(root/'proposal',public_key=authority.key.public_key(),approval_mode=approval_mode,install=install,commit=commit)
            except (ValueError,PermissionError) as error:record['adoption']={'accepted':False,'reason':str(error)[-2000:]}
    except (ValueError,RuntimeError) as error:record['tier2']={'accepted':0,'results':[],'reason':str(error)[-2000:]}
    record['observation']=engine.observe(task,record['tier2']['accepted']>0)
    (root/'epoch.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n');return record


def supervise(directory,*,key_path=None,cycles=1,forever=False,interval=10,iterations=128,approval_mode='auto',evolve=False,install=False,commit=False,seed=1,gate=None,family=None):
    if type(cycles) is not int or not 1<=cycles<=1024 or type(interval) is not int or not 1<=interval<=60 or type(iterations) is not int or not 1<=iterations<=4096:raise ValueError('Bounded nursery configuration required')
    if (install or commit) and not evolve:raise ValueError('Installation requires evolution')
    if commit and not install:raise ValueError('Committing requires installation')
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True)
    key_path=Path(key_path).resolve() if key_path else root/'.authority.seed'
    if not key_path.exists():create_key(key_path)
    authority=Authority(load_key(key_path));engine=CuriosityEngine(seed);gate=gate or IdleGate();history=root/'history.json';epochs=[]
    if history.exists():
        epochs=json.loads(history.read_text())
        if type(epochs) is not list or len(epochs)>32:raise ValueError('Nursery history budget exceeded')
        for item in epochs:engine.observe(item['task'],item['tier2']['accepted']>0)
    completed=0
    while forever or completed<cycles:
        if gate.idle(require_gpu=False):
            record=epoch(engine,root/f'epoch-{time.time_ns()}',authority=authority,iterations=iterations,approval_mode=approval_mode,evolve=evolve,install=install,commit=commit,family=family)
            epochs=(epochs+[record])[-32:]
            consolidation=sleep_epoch(epochs,root/'abstractions',signing_key=authority.key)
            temporary=root/'.history.tmp';temporary.write_text(json.dumps(epochs,sort_keys=True)+'\n');temporary.replace(history)
            (root/'sleep.json').write_text(json.dumps(consolidation,sort_keys=True)+'\n')
            print(json.dumps({'attempted':True,'backend':'native-cpu-mcts','accepted':record['tier2']['accepted'],'approval_mode':approval_mode,'consolidation':consolidation}),flush=True);completed+=1
        elif not forever:return {'attempted':False,'reason':'host utilization exceeds idle threshold'}
        if forever:time.sleep(interval)
    return {'completed':completed,'history':str(history),'authority':authority.public}
