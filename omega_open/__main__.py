"""CLI do experimento independente Ômega Open."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .engine import build,export,audit_directory,verify_chain,audit


def main(argv=None):
    p=argparse.ArgumentParser(description='Ômega 1.3 — síntese de programas para tabelas booleanas')
    sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('evolve');create.add_argument('tasks',type=Path);create.add_argument('output',type=Path)
    create.add_argument('--generations',type=int,default=3)
    create.add_argument('--max-rows',type=int,default=4096)
    create.add_argument('--max-orders',type=int,default=12)
    create.add_argument('--max-nodes',type=int,default=200000)
    a=sub.add_parser('audit');a.add_argument('folder',type=Path)
    b=sub.add_parser('verify');b.add_argument('file',type=Path)
    args=p.parse_args(argv)
    try:
        if args.action=='evolve':
            spec=json.loads(args.tasks.read_text(encoding='utf-8'))
            d=build(spec['tasks'],spec['train_ids'],args.generations,args.max_rows,args.max_orders,args.max_nodes)
            export(d,args.output)
            print(json.dumps(audit(d),ensure_ascii=False))
        elif args.action=='audit':print(json.dumps(audit_directory(args.folder),ensure_ascii=False))
        else:
            doc=json.loads(args.file.read_text(encoding='utf-8'))
            if not verify_chain(doc):raise ValueError('Verificação falhou')
            print('Provas finitas verificadas para '+str(len(doc['tasks']))+' tarefas')
        return 0
    except (KeyError,ValueError,OSError,json.JSONDecodeError,RecursionError) as e:
        print('ERRO ÔMEGA: '+str(e),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
