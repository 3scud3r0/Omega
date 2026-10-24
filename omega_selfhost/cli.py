"""Native Omega build and verification commands."""
import json
from pathlib import Path
import subprocess

COMMANDS=('bootstrap','native-build','native-run','verify-native','native-types','native-shapes','native-ir','validate-ir','native-ssa')


def register(sub):
    p=sub.add_parser('native-ssa',help='analyze SSA def-use and dominance for a tensor evaluation graph')
    p.add_argument('arquivo',type=Path)
    p=sub.add_parser('native-ir',help='export canonical, typed, versioned tensor IR')
    p.add_argument('arquivo',type=Path)
    p.add_argument('--saida',type=Path,required=True)
    p=sub.add_parser('validate-ir',help='validate canonical typed IR without executing it')
    p.add_argument('arquivo',type=Path)
    p=sub.add_parser('native-shapes',help='check every tensor graph dimension and emit a shape certificate')
    p.add_argument('arquivo',type=Path)
    p=sub.add_parser('native-types',help='infer source types without executing the program')
    p.add_argument('arquivo',type=Path)
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
        elif args.acao=='native-types':
            result=driver.source_types(args.arquivo)
            result=result.to_dict()
        elif args.acao=='native-shapes':
            from omega.dimensions import certify_graph_shapes
            result=certify_graph_shapes(driver.compile_ir(args.arquivo))
        elif args.acao=='native-ir':
            from omega.typed_ir import TypedIR
            ir=TypedIR.from_legacy(driver.compile_ir(args.arquivo))
            with args.saida.open('xb') as stream:stream.write(ir.to_bytes())
            result={'format':'omega-ir-validation-1','valid':True,'sha256':ir.sha256}
        elif args.acao=='validate-ir':
            from omega.typed_ir import TypedIR
            ir=TypedIR.load(args.arquivo)
            result={'format':'omega-ir-validation-1','valid':True,'sha256':ir.sha256}
        elif args.acao=='native-ssa':
            from omega.typed_ir import TypedIR
            from omega.ssa import analyze_tensor
            result=analyze_tensor(TypedIR.from_legacy(driver.compile_ir(args.arquivo)))
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
