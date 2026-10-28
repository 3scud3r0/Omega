"""Interface Ômega 1.0; compatível com o motor clássico 0.4."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .execucao import MaquinaOmega, verificar_certificado
from .tipos import checar_tipos
from .sintaxe import (ErroOmega, analisar, comando_de_dict, comando_para_dict,
                      Binario, Lista, Unario, Chamada)

VERSAO = '2.0.0'
FORMATO_IR = 'omega-ir-1'
FORMATO_PROVAS = 'omega-cert-1'
FORMATO_IR_V1 = 'omega-ir-2'
FORMATO_PROVAS_V1 = 'omega-cert-2'


def ler_json(p):
    return json.loads(p.read_text(encoding='utf-8'))


def ler_comandos(caminho: Path):
    if caminho.suffix == '.omc':
        d=ler_json(caminho)
        if not isinstance(d,dict) or d.get('formato')!=FORMATO_IR or not isinstance(d.get('comandos'),list):
            raise ErroOmega('IR clássica incompatível')
        return [comando_de_dict(c) for c in d['comandos']]
    return analisar(caminho.read_text(encoding='utf-8'))


def gravar_json(destino: Path, dados: dict):
    destino.parent.mkdir(parents=True,exist_ok=True)
    destino.write_text(json.dumps(dados,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def nova_funcao(e):
    if isinstance(e,Chamada):
        return e.funcao in {'relu','soma','zeros','identidade'} or any(nova_funcao(a) for a in e.argumentos)
    if isinstance(e,Lista):return any(nova_funcao(a) for a in e.elementos)
    if isinstance(e,Binario):return nova_funcao(e.esquerda) or nova_funcao(e.direita)
    if isinstance(e,Unario):return nova_funcao(e.argumento)
    return False


def novo_motor(comandos):
    return any(c.tipo in {'passo_livre','passo_ruidoso'} or any(nova_funcao(e) for e in (c.expressao,c.taxa,c.direita) if e is not None) for c in comandos)


def principal(argumentos: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(prog='omega',description='Ômega 2.0 — auto-hospedagem, execução nativa e certificação')
    p.add_argument('--versao', action='version',version='Ômega '+VERSAO)
    sub=p.add_subparsers(dest='acao',required=True)
    agent_parser=sub.add_parser('agent',help='finite reasoning, planning and rational expression synthesis')
    agent_parser.add_argument('arguments',nargs=argparse.REMAINDER)
    extensions={'refine':'omega_refine_check.cli','synth':'omega_synth_mcts.cli',
                'mutate':'omega_self_mutate.cli','action':'omega_agent_sandbox.cli','cognition':'omega_cognition.cli'}
    for name,module in extensions.items():
        sp=sub.add_parser(name,help=module)
        sp.add_argument('arguments',nargs=argparse.REMAINDER)
    from omega_nextorch.cli import register, execute, COMMANDS
    register(sub)
    from omega_selfhost import cli as native_cli
    native_cli.register(sub)
    for acao,help_text in (
        ('open-evolve','sintetiza tarefas Bool^n com políticas reprogramáveis'),('audit-open','audita evolução aberta e os arquivos'),('verify-open','verifica certificados de evolução aberta'),('run','executa .omega ou .omc'),('check','verifica execução e certificados'),
        ('types','lista tipos e formas'),('compile','compila para .omc'),
        ('verify','verifica certificados JSON'),('optimize','reescreve IR com equivalências'),
        ('inspect','mostra a estrutura do grafo'),('meta-evolve','sintetiza políticas de busca em Ômega'),('audit-meta','audita política autossintetizada'),('verify-meta','confere certificado completo de políticas'),('audit-evolution','audita todos os artefatos da evolução'),('evolve','sintetiza programa sucessor e prova finita'),('verify-evolution','verifica linhagem finita'),('export-lean','gera teoremas Lean 4 de fatos numéricos')):
        sp=sub.add_parser(acao,help=help_text)
        sp.add_argument('arquivo',type=Path)
        if acao=='open-evolve':
            sp.add_argument('--saida',type=Path,required=True)
            sp.add_argument('--geracoes',type=int,default=3)
            sp.add_argument('--max-linhas',type=int,default=4096)
            sp.add_argument('--max-ordens',type=int,default=12)
            sp.add_argument('--max-nos',type=int,default=200000)
        if acao=='run':sp.add_argument('--certificados',type=Path)
        if acao=='evolve':sp.add_argument('--raio',type=int,default=2)
        if acao in ('compile','optimize','export-lean'):
            sp.add_argument('-o','--saida',type=Path)
        if acao=='compile':
            sp.add_argument('--standalone',action='store_true')
            sp.add_argument('--target',type=Path)
            sp.add_argument('--contracts',type=Path,help='JSON architecture, input/output bounds and input_scale for a weights-only checkpoint')
        if acao=='optimize':sp.add_argument('--prova',type=Path)
        if acao in ('run','check','types','compile'):sp.add_argument('--motor',choices=['auto','classico','v1'],default='auto')
    args=p.parse_args(argumentos)
    try:
        if args.acao in extensions:
            from importlib import import_module
            return import_module(extensions[args.acao]).main(args.arguments)
        if args.acao=='compile' and args.standalone:
            if args.contracts is None or args.target is None:p.error('--standalone requires --contracts and --target')
            if args.target.suffix!='.c' or args.target.exists():raise ValueError('A fresh .c target is required')
            from omega_cognition.standalone import export
            manifest=ler_json(args.contracts)
            bundle=args.target.parent/(args.target.stem+'.certified')
            result=export(args.arquivo,manifest['architecture'],bundle,input_bounds=manifest['input_bounds'],
                          output_bounds=manifest['output_bounds'],input_scale=manifest.get('input_scale',1))
            args.target.parent.mkdir(parents=True,exist_ok=True)
            args.target.write_bytes(Path(result['source']).read_bytes())
            print(json.dumps(result,sort_keys=True,indent=2));return 0
        if args.acao=='agent':
            from omega_agent.cli import main as agent_main
            return agent_main(args.arguments)
        if args.acao in COMMANDS:
            return execute(args)
        if args.acao in native_cli.COMMANDS:
            return native_cli.execute(args)
        if args.acao=='open-evolve':
            from omega_open.engine import build,export,audit
            doc=ler_json(args.arquivo)
            cadeia=build(doc['tasks'],doc['train_ids'],args.geracoes,args.max_linhas,args.max_ordens,args.max_nos)
            export(cadeia,args.saida)
            print('EVOLUÇÃO ABERTA: '+json.dumps(audit(cadeia),ensure_ascii=False))
            return 0
        if args.acao=='audit-open':
            from omega_open.engine import audit_directory
            print('AUDITORIA ABERTA: '+json.dumps(audit_directory(args.arquivo),ensure_ascii=False))
            return 0
        if args.acao=='verify-open':
            from omega_open.engine import verify_chain
            if not verify_chain(ler_json(args.arquivo)):raise ErroOmega('Certificado aberto inválido')
            print('CERTIFICADO ABERTO: válido para as tarefas declaradas')
            return 0
        if args.acao=='meta-evolve':
            from .metaevolucao import exportar
            print(exportar(args.arquivo));return 0
        if args.acao=='audit-meta':
            from .metaevolucao import auditar
            print('META AUDITORIA APROVADA: '+json.dumps(auditar(args.arquivo),ensure_ascii=False));return 0
        if args.acao=='verify-meta':
            from .nucleo_meta import verificar
            if not verificar(ler_json(args.arquivo)):raise ErroOmega('Certificado meta inválido')
            print('CERTIFICADO META VÁLIDO: 16 tarefas, 625 hipóteses, 243 políticas finais');return 0
        if args.acao=='evolve':
            from .evolucao import exportar_evolucao
            print(exportar_evolucao(args.arquivo,args.raio))
            return 0
        if args.acao=='audit-evolution':
            from .evolucao import auditar_artefatos
            dados=auditar_artefatos(args.arquivo)
            print('AUDITORIA APROVADA: '+json.dumps(dados,ensure_ascii=False))
            return 0
        if args.acao=='verify-evolution':
            from .nucleo_evolucao import verificar_evolucao,provar_xor_exaustivo
            doc=ler_json(args.arquivo)
            if not verificar_evolucao(doc):raise ErroOmega('Linhagem evolutiva inválida')
            print(f'CADEIA VÁLIDA: {len(doc["geracoes"])} gerações; XOR demonstrado: {provar_xor_exaustivo(doc)}')
            return 0
        from .nucleo_v1 import verificar_certificado_v1,validar_ir
        from .motor_v1 import CompiladorV1,MaquinaV1
        from .otimizador_v1 import otimizar,validar_otimizacao
        if args.acao=='verify':
            d=ler_json(args.arquivo)
            if not isinstance(d,dict):raise ErroOmega('Certificados JSON precisam ser objeto')
            if d.get('formato')=='omega-opt-cert-1':
                if not validar_otimizacao(d):raise ErroOmega('Reescrita IR inválida')
                print(f'VALIDADO: {len(d["regras"])} transformação(ões) local(is) de IR')
                return 0
            certs=d.get('certificados')
            if not isinstance(certs,list):raise ErroOmega('Lista de certificados inválida')
            fmt=d.get('formato')
            if fmt not in (FORMATO_PROVAS,FORMATO_PROVAS_V1):raise ErroOmega('Formato de certificados inválido')
            for i,c in enumerate(certs,1):
                if not (verificar_certificado(c) if fmt==FORMATO_PROVAS else verificar_certificado_v1(c)):
                    raise ErroOmega(f'Certificado {i} rejeitado')
            print(f'VERIFICADO: {len(certs)} certificado(s)')
            return 0
        if args.acao=='export-lean':
            from .exportar_lean import gerar_lean
            d=ler_json(args.arquivo)
            if d.get('formato')!=FORMATO_PROVAS_V1:raise ErroOmega('Apenas certificados omega-cert-2')
            if not all(verificar_certificado_v1(c) for c in d['certificados']):
                raise ErroOmega('A exportação Lean exige certificados previamente válidos')
            destino=args.saida or args.arquivo.with_suffix('.lean')
            destino.write_text(gerar_lean(d['certificados']),encoding='utf-8')
            print(f'Fatos numéricos exportados: {destino} (execute `lake env lean` com Mathlib)')
            return 0
        arquivo=args.arquivo
        if arquivo.suffix=='.omc':
            doc=ler_json(arquivo)
            if doc.get('formato')==FORMATO_IR_V1:
                ir=doc
                validar_ir(ir)
                tipo_motor='v1'
            elif doc.get('formato')==FORMATO_IR:
                comandos=ler_comandos(arquivo);tipo_motor='classico'
            else:raise ErroOmega('IR desconhecida')
        else:
            comandos=ler_comandos(arquivo)
            solicitado=getattr(args,'motor','v1')
            if args.acao in ('optimize','inspect'):solicitado='v1'
            tipo_motor=('v1' if novo_motor(comandos) else 'classico') if solicitado=='auto' else solicitado
            if tipo_motor=='classico' and novo_motor(comandos):
                raise ErroOmega('Programa exige motor v1 (ReLU ou política experimental)')
            if tipo_motor=='v1':ir=CompiladorV1().programa(comandos)
        if args.acao in ('optimize','inspect') and tipo_motor!='v1':
            raise ErroOmega('Comando requer a IR tipada v1')
        if args.acao=='inspect':
            print(f'Ômega 1.0: {len(ir["nos"])} nós, {len(ir["parametros"])} parâmetros, {len(ir["perdas"])} perdas')
            for i,n in enumerate(ir['nos']):
                print(f'{i:>4}: {n["op"]:<12} forma={n["forma"]} entradas={n["args"]}')
            return 0
        if args.acao=='optimize':
            novo,prova=otimizar(ir)
            saida=args.saida or arquivo.with_suffix('.otimizado.omc')
            provapath=args.prova or saida.with_suffix('.prova.json')
            gravar_json(saida,novo);gravar_json(provapath,prova)
            print(f'Otimizado: {len(ir["nos"])} -> {len(novo["nos"])} nós; {len(prova["regras"])} regras')
            print(f'IR: {saida} | Prova: {provapath}')
            return 0
        if tipo_motor=='v1':
            if args.acao=='compile':
                if arquivo.suffix=='.omc':raise ErroOmega('Compile a fonte .omega')
                destino=args.saida or arquivo.with_suffix('.omc')
                ir['sha256_fonte']=hashlib.sha256(arquivo.read_bytes()).hexdigest()
                gravar_json(destino,ir)
                print(f'Compilado para IR tensorial: {destino}')
                return 0
            if args.acao=='types':
                for nome,i in ir['simbolos'].items():
                    shape=ir['nos'][i]['forma']
                    kind='Escalar' if not shape else ('Vetor' if len(shape)==1 else 'Matriz')
                    print(f'{nome}: {kind}{shape}, id={i}')
                return 0
            maquina=MaquinaV1(ir).executar()
            if args.acao=='check':
                print(f'VÁLIDO: {len(ir["comandos"])} comandos; {len(maquina.certificados)} certificados v1')
                return 0
            for linha in maquina.saidas:print(linha)
            if args.certificados:
                gravar_json(args.certificados,{'formato':FORMATO_PROVAS_V1,'linguagem':'Ômega',
                                              'versao':VERSAO,'certificados':maquina.certificados})
                print(f'Certificados salvos: {args.certificados}')
            return 0
        # Semântica de 0.4 preservada, inclusive os certificados omega-cert-1.
        t=checar_tipos(comandos)
        if args.acao=='types':
            for i,(c,tip) in enumerate(zip(comandos,t.tipos_comandos),1):print(f'{i:>3} {c.tipo:<14} {tip}')
            print('SÍMBOLOS:')
            for name,typ in sorted(t.simbolos.items()):print(f'  {name}: {typ}')
            return 0
        if args.acao=='compile':
            if arquivo.suffix=='.omc':raise ErroOmega('Compile a fonte .omega')
            destino=args.saida or arquivo.with_suffix('.omc')
            gravar_json(destino,{'formato':FORMATO_IR,'versao_compilador':VERSAO,
                                 'sha256_fonte':hashlib.sha256(arquivo.read_bytes()).hexdigest(),
                                 'comandos':[comando_para_dict(c) for c in comandos],
                                 'tipos':t.simbolos})
            print(f'Compilado para representação intermediária: {destino}')
            return 0
        maquina=MaquinaOmega().executar(comandos)
        if args.acao=='check':
            print(f'VÁLIDO: {len(comandos)} comandos; {len(maquina.certificados)} certificados clássicos')
            return 0
        for linha in maquina.saidas:print(linha)
        if args.certificados:
            gravar_json(args.certificados,{'formato':FORMATO_PROVAS,'linguagem':'Ômega',
                                          'versao':VERSAO,'certificados':maquina.certificados})
            print(f'Certificados salvos: {args.certificados}')
        return 0
    except (ErroOmega,OSError,ValueError,TypeError,KeyError,UnicodeError,
            RecursionError,OverflowError,json.JSONDecodeError) as erro:
        print(f'ERRO ÔMEGA: {erro}',file=sys.stderr)
        return 1


def compilador_principal() -> int:
    return principal(['compile',*sys.argv[1:]])
