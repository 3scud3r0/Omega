import argparse
import asyncio
import ctypes
import json
from pathlib import Path
import subprocess
from .backend import CudaSearch,CudaUnavailable
from .build import ROOT,cuda_library,compile_cuda


def benchmark(directory):
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    try:engine=CudaSearch()
    except CudaUnavailable as error:
        report={'format':'omega-hyper-benchmark-1','status':'pending','reason':str(error),
                'cuda_compile':'passed','cuda_execution':'unrun','ten_million_operations':'unrun',
                'fifty_thousand_nodes_under_one_second':'unrun','ten_nanosecond_filter':'unmeasured'}
        (root/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n');return report,77
    stress=compile_cuda([ROOT/'testes/cuda/rational_stress.cu'],root/'rational-stress')
    checked=subprocess.run([stress,'10000000'],capture_output=True,text=True,timeout=300)
    if checked.returncode:raise RuntimeError('CUDA rational stress failed: '+checked.stderr)
    spec={'variables':{'x':'self>=-1 and self<=1'},'ensures':'result==x+1',
          'examples':[{'inputs':{'x':str(x)},'output':str(x+1)} for x in (-1,0,1)]}
    result=engine.search(spec,input_bounds=[[-1,1]],output_bounds=[0,2],iterations=200,rollouts=256)
    stats=result['statistics'];met=stats['nodes_evaluated']>=50000 and stats['elapsed_ms']<1000
    report={'format':'omega-hyper-benchmark-1','status':'passed' if met else 'failed','cuda_compile':'passed','cuda_execution':'measured',
            'rational_stress':json.loads(checked.stdout),'statistics':stats,'fifty_thousand_nodes_under_one_second':met,
            'ten_nanosecond_filter':'unmeasured; no constant latency or pruning rate guarantee'}
    (root/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n');return report,0 if met else 1


def main(argv=None):
    parser=argparse.ArgumentParser(prog='omega hyper')
    parser.add_argument('mode',choices=['status','benchmark','search','sleep'])
    parser.add_argument('--spec',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.mode=='status':
            path=cuda_library();library=ctypes.CDLL(str(path));result={'cuda_compile':'passed','cuda_devices':library.omega_cuda_available(),'library':str(path)};status=0
        elif args.output is None:parser.error('--output is required')
        elif args.mode=='benchmark':result,status=benchmark(args.output)
        elif args.spec is None:parser.error('--spec is required')
        elif args.mode=='search':
            from omega_autotelic.curiosity_driver import authority
            from omega_self_evolve_v2.bridge_lean_filter import LeanBridge
            spec=json.loads(args.spec.read_text());key=authority(args.output)
            engine=CudaSearch();batch=engine.search(spec['spec'],input_bounds=spec['input_bounds'],output_bounds=spec['output_bounds'],**spec.get('search',{}))
            with LeanBridge(signing_key=key,queue_capacity=64) as bridge:result=asyncio.run(bridge.consume(spec['spec'],batch,args.output/'tier2'))
            status=0 if result['accepted'] else 1
        else:
            from omega_autotelic.curiosity_driver import authority
            from omega_autotelic.bank import consolidate,AbstractionBank
            key=authority(args.output);records=json.loads(args.spec.read_text());proposals=consolidate(records,public_key=key.public_key())
            bank=AbstractionBank(args.output/'bank',public_key=key.public_key())
            result={'proposals':len(proposals),'promoted':[bank.promote(p,signing_key=key)['id'] for p in proposals[:16]]};status=0
        print(json.dumps(result,sort_keys=True,indent=2));return status
    except CudaUnavailable as error:print(json.dumps({'status':'pending','reason':str(error)}));return 77
