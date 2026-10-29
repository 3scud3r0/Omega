"""Native standard library, offline proofs and noninteractive incubation CLI."""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import subprocess
from .authority import Authority,create_key,load_key,public_hex,GENESIS
from .codec import canonical
from .toolchain import build,result


def main(argv=None):
    p=argparse.ArgumentParser(prog='omega native');sub=p.add_subparsers(dest='command',required=True)
    key=sub.add_parser('keygen');key.add_argument('path',type=Path)
    b=sub.add_parser('build');b.add_argument('--entry',choices=['suite','repl'],default='suite');b.add_argument('-o','--output',type=Path)
    sub.add_parser('repl')
    math=sub.add_parser('math');math.add_argument('operation',choices=['sqrt','exp','log','sin','cos','trig']);math.add_argument('x');math.add_argument('--bits',type=int,default=32);math.add_argument('--proof-output',type=Path);math.add_argument('--key',type=Path)
    search=sub.add_parser('search');search.add_argument('spec',type=Path);search.add_argument('--key',type=Path,required=True);search.add_argument('--output',type=Path,required=True);search.add_argument('--iterations',type=int,default=128);search.add_argument('--max-nodes',type=int,default=7);search.add_argument('--seed',type=int,default=1)
    gym=sub.add_parser('gym');gym.add_argument('request',type=Path)
    fitness=sub.add_parser('fitness');fitness.add_argument('request',type=Path)
    sim=sub.add_parser('simulate');sim.add_argument('request',type=Path)
    put=sub.add_parser('db-put');put.add_argument('--root',type=Path,required=True);put.add_argument('--path',default='memory.log');put.add_argument('--head',default=GENESIS);put.add_argument('--name',required=True);put.add_argument('--document',type=Path,required=True);put.add_argument('--bounds',type=Path,required=True);put.add_argument('--policy',required=True);put.add_argument('--key',type=Path,required=True);put.add_argument('--proof-output',type=Path,required=True)
    for name in ('db-get','db-audit'):
        sp=sub.add_parser(name);sp.add_argument('--root',type=Path,required=True);sp.add_argument('--path',default='memory.log');sp.add_argument('--head',required=True)
        if name=='db-get':sp.add_argument('--name',required=True)
    pkg=sub.add_parser('package-check');pkg.add_argument('--root',type=Path,required=True);pkg.add_argument('--lock',type=Path,required=True);pkg.add_argument('--policy',required=True);pkg.add_argument('--key',type=Path,required=True);pkg.add_argument('--proof-output',type=Path,required=True)
    incubate=sub.add_parser('incubate');incubate.add_argument('lhs');incubate.add_argument('--receipt',type=Path,required=True);incubate.add_argument('--proof-directory',type=Path,required=True);incubate.add_argument('--key',type=Path,required=True);incubate.add_argument('--output',type=Path,required=True)
    incubate.add_argument('--approval-mode',choices=['auto','manual'],default='auto');incubate.add_argument('--auto-approve',action='store_const',const='auto',dest='approval_mode')
    incubate.add_argument('--stage-only',action='store_true',help='Propose, approve and bootstrap without installing the generation');incubate.add_argument('--commit',action='store_true',help='Also replace source and commit; requires a clean repository')
    nursery=sub.add_parser('nursery');nursery.add_argument('--output',type=Path,required=True);nursery.add_argument('--key',type=Path);nursery.add_argument('--cycles',type=int,default=1);nursery.add_argument('--forever',action='store_true');nursery.add_argument('--interval',type=int,default=10);nursery.add_argument('--iterations',type=int,default=128);nursery.add_argument('--seed',type=int,default=1)
    nursery.add_argument('--approval-mode',choices=['auto','manual'],default='auto');nursery.add_argument('--auto-approve',action='store_const',const='auto',dest='approval_mode');nursery.add_argument('--evolve',action='store_true');nursery.add_argument('--install',action='store_true');nursery.add_argument('--commit',action='store_true')
    args=p.parse_args(argv)
    try:
        read=lambda path:json.loads(Path(path).read_text(),parse_float=Q)
        if args.command=='keygen':output={'public_key':public_hex(create_key(args.path)),'private_key':str(args.path)}
        elif args.command=='build':output={'binary':str(build('tools/repl.omega' if args.entry=='repl' else 'tools/native_suite.omega',args.output))}
        elif args.command=='repl':return subprocess.run([build('tools/repl.omega')],check=False).returncode
        elif args.command=='math':
            if args.proof_output:
                from .analytic import certify
                output=certify(args.operation,args.x,args.proof_output,bits=args.bits,signing_key=load_key(args.key) if args.key else None)
            else:output=result('math',{'operation':args.operation,'x':args.x,'bits':args.bits})
        elif args.command=='search':
            from .api import synthesize
            output=synthesize(read(args.spec),args.output,signing_key=load_key(args.key),iterations=args.iterations,max_nodes=args.max_nodes,seed=args.seed)
        elif args.command in ('fitness','simulate'):output=result(args.command,read(args.request))
        elif args.command=='gym':
            from .toolchain import execute
            request=read(args.request)
            # Streaming trusted native program, so hot weight updates are visible.
            print(execute('gym',request,interactive=True),end='');return 0
        elif args.command=='db-put':
            from .api import insert
            authority=Authority(load_key(args.key));document,permit=authority.database(key=args.name,document=read(args.document),head=args.head,policy=args.policy,bounds=read(args.bounds),directory=args.proof_output)
            output=insert(args.root,args.path,args.head,args.name,document,authority=authority.public,permit=permit,policy=args.policy)
        elif args.command=='db-get':
            from .api import lookup
            output={'document':canonical(lookup(args.root,args.path,args.head,args.name))}
        elif args.command=='db-audit':
            from .api import audit
            output=audit(args.root,args.path,args.head)
        elif args.command=='package-check':
            authority=Authority(load_key(args.key));lock=read(args.lock);token=authority.packages(lock,policy=args.policy,directory=args.proof_output)
            root=args.root.resolve();output=result('package-verify',dict(root=str(root),lock=lock,authority=authority.public,policy=args.policy,certificate=token),readonly=[root])
        elif args.command=='incubate':
            from .incubator import prepare,adopt
            authority=Authority(load_key(args.key));prepare(args.lhs,read(args.receipt),args.proof_directory,args.output,authority=authority)
            output=adopt(args.output,public_key=authority.key.public_key(),approval_mode=args.approval_mode,install=not args.stage_only,commit=args.commit)
        elif args.command=='nursery':
            from .nursery import supervise
            output=supervise(args.output,key_path=args.key,cycles=args.cycles,forever=args.forever,interval=args.interval,iterations=args.iterations,approval_mode=args.approval_mode,evolve=args.evolve,install=args.install,commit=args.commit,seed=args.seed)
        print(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2));return 0
    except (ValueError,RuntimeError,PermissionError,FileExistsError) as error:
        p.exit(1,str(error)+'\n')


if __name__=='__main__':raise SystemExit(main())
