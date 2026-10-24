"""Native Omega build and verification commands."""
import json
from pathlib import Path
import subprocess

COMMANDS=('bootstrap','native-build','native-run','verify-native')


def register(sub):
    p=sub.add_parser('bootstrap',help='build and compare native compiler stages 0/1/2')
    p.add_argument('--saida',type=Path)
    p=sub.add_parser('native-build',help='self-hosted compiler, rational tensors and native machine code')
    p.add_argument('arquivo',type=Path)
    p.add_argument('--saida',type=Path,required=True)
    p.add_argument('--optimize',action='store_true')
    p=sub.add_parser('native-run',help='run native code and require independent Lean admission')
    p.add_argument('arquivo',type=Path)
    p.add_argument('--saida',type=Path)
    p=sub.add_parser('verify-native',help='recheck an execution with the formal tensor kernel')
    p.add_argument('arquivo',type=Path)


def execute(args):
    from . import driver
    try:
        if args.acao=='bootstrap':
            result=driver.bootstrap(args.saida or driver.BUILD)
        elif args.acao=='native-build':
            result=driver.build(args.arquivo,args.saida,args.optimize)
        elif args.acao=='native-run':
            data,result=driver.run(args.arquivo,destination=args.saida)
            for line in data['outputs']:print(line)
        else:
            result=driver.verify_result(json.loads(args.arquivo.read_text()))
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (RuntimeError,subprocess.SubprocessError) as exc:
        raise ValueError(str(exc)) from exc
