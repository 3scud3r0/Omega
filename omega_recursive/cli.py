"""Six native research components in one reproducible source distribution."""
import argparse
import asyncio
import json
from pathlib import Path

from omega_kernel.protocol import read_document
from .runtime import call
from .cycle import run_cycle, export_proposal, prove_task, self_play
from .certificates import verify_claim,verify_improvement
from .gpu import sieve
from .amalgamation import inspect,extract


def output(value,path=None):
    text = json.dumps(value,indent=2,ensure_ascii=False)+'\n'
    if path:
        with Path(path).open('x') as stream:
            stream.write(text)
    else:
        print(text,end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    native = sub.add_parser('run')
    native.add_argument('operation',choices=['dag','induce','improve','universe','quarantine','sieve'])
    native.add_argument('request',type=Path)
    native.add_argument('--output',type=Path)
    cycle = sub.add_parser('cycle')
    cycle.add_argument('request',type=Path)
    cycle.add_argument('--rounds',type=int,default=4)
    cycle.add_argument('--export',type=Path)
    cycle.add_argument('--output',type=Path)
    gpu = sub.add_parser('sieve')
    gpu.add_argument('request',type=Path)
    gpu.add_argument('--backend',choices=['cpu','gpu','auto'],default='cpu')
    gpu.add_argument('--max-admitted',type=int,default=8)
    gpu.add_argument('--output',type=Path)
    prove = sub.add_parser('prove-universe')
    prove.add_argument('request',type=Path)
    prove.add_argument('--output',type=Path)
    play = sub.add_parser('self-play')
    play.add_argument('request',type=Path)
    play.add_argument('--backend',choices=['cpu','gpu','auto'],default='cpu')
    play.add_argument('--output',type=Path)
    verify = sub.add_parser('verify')
    verify.add_argument('certificate',type=Path)
    bundle = sub.add_parser('inspect')
    bundle.add_argument('file',type=Path)
    unpack = sub.add_parser('extract')
    unpack.add_argument('file',type=Path)
    unpack.add_argument('destination',type=Path)
    serve = sub.add_parser('serve')
    serve.add_argument('--peer',action='append',required=True,help='allowed Ed25519 public key hex')
    serve.add_argument('--listen',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=8486)
    serve.add_argument('--database',type=Path,required=True)
    args = parser.parse_args(argv)
    if args.command == 'run':
        output(call(args.operation,read_document(args.request)),args.output)
    elif args.command == 'cycle':
        request = read_document(args.request)
        result = run_cycle(request['baseline'],request['observations'],rounds=args.rounds)
        if args.export:
            export_proposal(result,args.export)
        output(result,args.output)
    elif args.command == 'sieve':
        request = read_document(args.request)
        output(sieve(request['programs'],request['observations'],backend=args.backend,max_admitted=args.max_admitted),args.output)
    elif args.command == 'prove-universe':
        universe = call('universe',read_document(args.request))
        output({'universe':universe,'proofs':[prove_task(task) for task in universe['tasks']]},args.output)
    elif args.command == 'self-play':
        output(self_play(read_document(args.request),backend=args.backend),args.output)
    elif args.command == 'verify':
        cert = read_document(args.certificate)
        result = verify_claim(cert) if cert['format']=='omega-point-certificate-1' else verify_improvement(cert)
        output(result)
        return 0 if result['accepted'] else 1
    elif args.command == 'inspect':
        output(inspect(args.file.read_bytes())[0])
    elif args.command == 'extract':
        output(extract(args.file.read_bytes(),args.destination))
    elif args.command == 'serve':
        from .swarm import Store,handle_peer
        if not 1 <= args.port <= 65535:
            parser.error('port 1..65535')
        async def run_server():
            store = Store(args.peer,database=str(args.database))
            try:
                server = await asyncio.start_server(lambda r,w:handle_peer(r,w,store),args.listen,args.port,limit=65540)
                async with server:
                    await server.serve_forever()
            finally:
                store.close()
        asyncio.run(run_server())
    return 0
