"""omega live: durable run history and authenticated real-time controls."""
import argparse
import json
from pathlib import Path
import secrets
import sys
import time
from .store import Store,encode
from .native import invoke


def main(argv=None):
    p=argparse.ArgumentParser(prog='omega live');p.add_argument('--state',type=Path,default=Path('build/live'))
    sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('spec',type=Path);create.add_argument('--iterations',type=int,default=128);create.add_argument('--max-nodes',type=int,default=7);create.add_argument('--capacity',type=int,default=1024);create.add_argument('--seed',type=int,default=1);create.add_argument('--backend',choices=['native','cuda'],default='native');create.add_argument('--bounds',type=Path)
    worker=sub.add_parser('work');worker.add_argument('run');worker.add_argument('--idle-timeout',type=int,default=300);worker.add_argument('--no-proof',action='store_true',help='Search only; results remain formally unadmitted')
    monitor=sub.add_parser('monitor');monitor.add_argument('--host',default='127.0.0.1');monitor.add_argument('--port',type=int,default=8765);monitor.add_argument('--token-file',type=Path)
    tui=sub.add_parser('tui');tui.add_argument('run');tui.add_argument('--watch',action='store_true')
    history=sub.add_parser('history');history.add_argument('--run');history.add_argument('--after',type=int,default=0);history.add_argument('--follow',action='store_true')
    control=sub.add_parser('control');control.add_argument('run');control.add_argument('kind',choices=['pause','resume','step','cancel','weights','iterations']);control.add_argument('--revision',type=int,required=True);control.add_argument('--value')
    audit=sub.add_parser('audit');audit.add_argument('--head')
    export=sub.add_parser('export');export.add_argument('path',type=Path)
    native=sub.add_parser('native');native.add_argument('module');native.add_argument('request',type=Path)
    args=p.parse_args(argv)
    try:
        store=Store(args.state)
        if args.command=='create':
            from .worker import create_run
            bounds=json.loads(args.bounds.read_text()) if args.bounds else {}
            output=create_run(store,json.loads(args.spec.read_text()),iterations=args.iterations,max_nodes=args.max_nodes,capacity=args.capacity,seed=args.seed,backend=args.backend,input_bounds=bounds.get('inputs'),output_bounds=bounds.get('output'))
        elif args.command=='work':
            from .worker import work
            output=work(store,args.run,idle_timeout=args.idle_timeout,prove=not args.no_proof)
        elif args.command=='monitor':
            from .server import Monitor
            token=None
            if args.token_file:
                path=args.token_file
                if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:raise ValueError('Token file must be a private regular file')
                token=path.read_text().strip()
            server=Monitor((args.host,args.port),store,token)
            print('Monitor: http://'+args.host+':'+str(server.server_address[1]),flush=True)
            # This is a newly generated local capability, not an injected cloud
            # credential. Show it only on the explicitly requested terminal.
            if token is None:print('Local monitor token: '+server.token,flush=True)
            try:server.serve_forever(poll_interval=.2)
            finally:server.server_close()
            return 0
        elif args.command=='control':
            value=json.loads(args.value) if args.value is not None else None
            output=store.command(args.run,args.kind,expected_revision=args.revision,value=value)
        elif args.command=='history':
            cursor=args.after
            while True:
                batch=store.events(after=cursor,run=args.run)
                for event in batch:print(encode(event),flush=True);cursor=event['seq']
                if not args.follow:return 0
                time.sleep(.2)
        elif args.command=='tui':
            while True:
                state=store.snapshot(args.run);render=invoke('tools/dashboard/dashboard_tui.omega',{'state':state});print(('\x1b[2J\x1b[H' if args.watch and sys.stdout.isatty() else '')+render,flush=True)
                if not args.watch or state['status'] in ('completed','failed','cancelled'):return 0
                time.sleep(.5)
        elif args.command=='audit':output=store.audit(expected_head=args.head)
        elif args.command=='export':output=store.export(args.path)
        elif args.command=='native':output=invoke(args.module,json.loads(args.request.read_text()))
        print(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2));return 0
    except KeyboardInterrupt:return 130
    except (ValueError,KeyError,RuntimeError,OSError) as error:p.exit(1,str(error)+'\n')


if __name__=='__main__':raise SystemExit(main())
