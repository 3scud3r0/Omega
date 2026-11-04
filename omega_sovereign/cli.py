"""Commands expose bounded implementations without implying full sovereignty."""
import argparse
import json
from pathlib import Path
from omega_security.encoding import decode
from .native import build_seed,build_crypto
from .baremetal import build as build_boot
from .hardware import fpga,asic
from .air_fri import prove,verify


def read(path):return decode(Path(path).read_bytes(),max_bytes=2*1024**2,max_nodes=60000,max_depth=32)
def save(path,value):
    data=json.dumps(value,sort_keys=True,indent=2)+'\n'
    with Path(path).open('x') as output:output.write(data)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    seed=commands.add_parser('seed',help='Build RV64 compiler for closed rational expressions')
    seed.add_argument('output',type=Path);seed.add_argument('--limbs',type=int,default=128)
    for name in ('crypto-reference','boot','fpga'):
        p=commands.add_parser(name);p.add_argument('output',type=Path)
    p=commands.add_parser('asic');p.add_argument('output',type=Path);p.add_argument('--pdk-root',type=Path,required=True)
    p=commands.add_parser('model');p.add_argument('operation',choices=('tcp','raft'));p.add_argument('request',type=Path)
    p=commands.add_parser('air-prove',help='Research AIR/FRI proof; no zero-knowledge guarantee')
    p.add_argument('request',type=Path);p.add_argument('output',type=Path)
    p=commands.add_parser('air-verify');p.add_argument('proof',type=Path);p.add_argument('statement',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='seed':result=build_seed(args.output,limbs=args.limbs)
        elif args.command=='crypto-reference':result=build_crypto(args.output)
        elif args.command=='boot':result=build_boot(args.output)
        elif args.command=='fpga':result=fpga(args.output)
        elif args.command=='asic':result=asic(args.output,pdk_root=args.pdk_root)
        elif args.command=='model':
            from .models import call
            result=call(args.operation,read(args.request))
        elif args.command=='air-prove':
            request=read(args.request)
            result=prove(request['start'],request['c'],request['steps'])
            save(args.output,result)
            result={'written':str(args.output),'zero_knowledge':False,'production_approved':False}
        elif args.command=='air-verify':
            valid=verify(read(args.proof),read(args.statement))
            print(json.dumps({'valid':valid,'zero_knowledge':False}));return 0 if valid else 1
        print(json.dumps(result,sort_keys=True,indent=2));return 0
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        parser.exit(2,str(exc)+'\n')


if __name__=='__main__':raise SystemExit(main())
