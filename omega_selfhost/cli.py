"""Native Omega build and verification commands."""
import json
from pathlib import Path
import sys

COMMANDS=('bootstrap','native-build','native-run','verify-native','native-types','native-shapes','native-ir','validate-ir','native-ssa','module-link','module-build','generic-build','generic-ir')


def register(sub):
    for action in ('generic-build','generic-ir'):
        p=sub.add_parser(action,help='specialize closed rational/tensor templates with checked dimensions')
        p.add_argument('arquivo',type=Path)
        p.add_argument('--templates',type=Path,required=True)
        p.add_argument('--saida',type=Path,required=True)
    for action in ('module-link','module-build'):
        p=sub.add_parser(action,help='link local procedural modules with explicit exports and a bounded import root')
        p.add_argument('arquivo',type=Path)
        p.add_argument('--raiz',type=Path)
        p.add_argument('--saida',type=Path,required=True)
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


def _execute(args):
    from . import driver
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
        result=driver.build_checked(args.arquivo,args.saida,args.optimize).unwrap()
    elif args.acao=='generic-build':
        result=driver.build_generic(args.arquivo,args.templates,args.saida)
    elif args.acao=='generic-ir':
        from omega.typed_ir import TypedIR
        ir=TypedIR.from_legacy(driver.generic_ir(args.arquivo,args.templates))
        with args.saida.open('xb') as stream:stream.write(ir.to_bytes())
        result={'format':'omega-ir-validation-1','valid':True,'sha256':ir.sha256}
    elif args.acao=='module-build':
        result=driver.build_module(args.arquivo.resolve(),args.saida,root=args.raiz)
    elif args.acao=='module-link':
        from omega.modules import link
        from omega_platform.manifest import canonical
        source=args.arquivo.resolve();linked=link(source,args.raiz or source.parent)
        target=args.saida;manifest=target.with_suffix('.modules.json')
        if target==manifest or target.exists() or manifest.exists():raise FileExistsError('Linked module artifacts already exist or collide')
        with target.open('x',encoding='utf-8') as stream:stream.write(linked.source)
        with manifest.open('xb') as stream:stream.write(canonical(linked.manifest()))
        result={'linked_source':str(target),'module_manifest':str(manifest),'sha256':linked.manifest()['linked_sha256']}
    elif args.acao=='native-run':
        data,result=driver.run_checked(args.arquivo,destination=args.saida).unwrap()
        for line in data['outputs']:print(line)
    else:
        from omega_platform.results import attempt
        result=attempt('proof',driver.verify_result,json.loads(args.arquivo.read_text())).unwrap()
    print(json.dumps(result,ensure_ascii=False))
    return 0


def execute(args):
    from omega_platform.results import attempt,Err
    result=attempt(args.acao,_execute,args)
    if isinstance(result,Err):
        print(json.dumps(result.to_dict(),ensure_ascii=False),file=sys.stderr)
        return 1
    return result.unwrap()
