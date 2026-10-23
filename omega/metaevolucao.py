"""Ômega 1.2 — metaevolução de código de uma POLÍTICA EXECUTÁVEL de busca.

A decisão de prioridade não está embutida em Python: está em um .omega
mutado e compilado pela própria linguagem. O laço de enumeração e o
verificador continuam em Python. Garantia restrita a 16 tarefas finitas.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
import json

from .nucleo_meta import (GENES,BASE,TREINO,TESTE,FORMATO,
                          digest,otimo,candidatos,contagens,verificar,
                          certificado_completude,saidas,alvo,escore)
from .meta_programa import fonte_politica
from .sintaxe import ErroOmega,analisar
from .motor_v1 import CompiladorV1,MaquinaV1
from .nucleo_v1 import validar_ir


def construir():
    recs=[];prev='GENESIS'
    for fase in range(3):
        pesos=otimo(fase)
        cont=contagens(pesos)
        fonte=fonte_politica(pesos)
        rec={'fase':fase,'pesos':list(pesos),'hipoteses':len(candidatos(fase)),
             'avaliacoes':list(cont),'treino_total':sum(cont[i] for i in TREINO),
             'teste_total':sum(cont[i] for i in TESTE),'prev':prev,
             'codigo_sha256':sha256(fonte.encode()).hexdigest()}
        rec['id']=digest(rec);recs.append(rec);prev=rec['id']
    doc={'formato':FORMATO,'dominio':'Bool^2','parametros':'(-2..2)^4',
         'treino':list(TREINO),'teste':list(TESTE),'geracoes':recs}
    doc['hash']=digest(doc)
    if not verificar(doc):raise ErroOmega('Núcleo independente rejeitou metaevolução')
    return doc


def executar_codigo(fonte):
    ir=CompiladorV1().programa(analisar(fonte))
    validar_ir(ir)
    maquina=MaquinaV1(ir).executar()
    # Auditoria exaustiva: TODAS as hipóteses, não apenas amostras.
    return ir,maquina


def conferir_vm(maquina,ir,pesos):
    idx=ir['simbolos']['prioridade']
    for g in GENES:
        estado={**maquina.estado,**{name:Fraction(v) for name,v in zip('abcd',g)}}
        valor=maquina.frente(estado)[idx]
        if valor!=escore(pesos,g):
            raise ErroOmega('Política executada diverge da verificação independente')
    return True


def conferir_busca_vm(maquina,ir,esperadas):
    """Pesquisa tarefas pelo código compilado da política, não pela fórmula do kernel.

    Sem olhar a resposta desejada durante a ordenação; somente compara as
    previsões de cada hipótese sucessivamente ao alvo, como busca real.
    """
    idx=ir['simbolos']['prioridade']
    def score(g):
        st={**maquina.estado,**{nome:Fraction(v) for nome,v in zip('abcd',g)}}
        return maquina.frente(st)[idx]
    ordenados=sorted(GENES,key=lambda g:(score(g),g))
    numeros=[]
    for mascara in range(16):
        esperado=alvo(mascara)
        for n,(a,b,c,d) in enumerate(ordenados,1):
            observado=tuple(a+b*x+c*y+d*max(0,x+y-1)
                            for x,y in ((0,0),(0,1),(1,0),(1,1)))
            if observado==esperado:
                numeros.append(n);break
        else:
            raise ErroOmega('Universo de hipóteses não resolve uma tarefa')
    if numeros!=list(esperadas):
        raise ErroOmega('Busca real da VM divergiu da certificação independente')
    return True


def guardar(caminho,obj):
    Path(caminho).write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')


def exportar(destino):
    p=Path(destino);p.mkdir(parents=True,exist_ok=True)
    doc=construir()
    for r in doc['geracoes']:
        fonte=fonte_politica(r['pesos'])
        (p/f'politica_{r["fase"]}.omega').write_text(fonte,encoding='utf-8')
        ir,m=executar_codigo(fonte)
        conferir_vm(m,ir,r['pesos'])
        conferir_busca_vm(m,ir,r['avaliacoes'])
        guardar(p/f'politica_{r["fase"]}.omc',ir)
    guardar(p/'certificado_meta.json',doc)
    (p/'politica_ativa.omega').write_text(fonte_politica(doc['geracoes'][-1]['pesos']),encoding='utf-8')
    r0,r1,r2=doc['geracoes']
    texto=(f'ÔMEGA 1.2 — Autoevolução finita de política de busca\n'
           f'Espaço completo de programas candidatos: {len(GENES)}\n'
           f'Tarefas: 8 de treinamento, 8 reservadas para teste; total 16 gates booleanos.\n'
           f'Número de políticas verificadas em cada geração: '+', '.join(str(r['hipoteses']) for r in doc['geracoes'])+'\n'
           f'Código executável Ômega de prioridade gerado e executado sobre os 625 candidatos.\n'
           f'Custo total de treino: {r0["treino_total"]} -> {r1["treino_total"]} -> {r2["treino_total"]}\n'
           f'Custo total em tarefas reservadas: {r0["teste_total"]} -> {r1["teste_total"]} -> {r2["teste_total"]}\n'
           f'Política final: {r2["pesos"]}\n'
           f'Domínio exaustivo: 16 tarefas, universo de hipóteses 625, espaço de políticas 243.\n'
           f'Prova de completude do espaço de hipóteses: {certificado_completude()}\n'
           f'IMPORTANTE: melhoria em domínio finito NÃO é prova de AGI, evolução ilimitada ou segurança geral.\n')
    (p/'RELATORIO_META.txt').write_text(texto,encoding='utf-8')
    return texto


def auditar(destino):
    p=Path(destino)
    doc=json.loads((p/'certificado_meta.json').read_text(encoding='utf-8'))
    if not verificar(doc):raise ErroOmega('Certificado meta inválido')
    for r in doc['geracoes']:
        fonte=fonte_politica(r['pesos'])
        f=p/f'politica_{r["fase"]}.omega'
        if f.read_text(encoding='utf-8')!=fonte:raise ErroOmega('Política-fonte adulterada')
        ir,maquina=executar_codigo(fonte)
        if json.loads((p/f'politica_{r["fase"]}.omc').read_text(encoding='utf-8'))!=ir:
            raise ErroOmega('Política compilada adulterada')
        conferir_vm(maquina,ir,r['pesos'])
        conferir_busca_vm(maquina,ir,r['avaliacoes'])
    if (p/'politica_ativa.omega').read_text(encoding='utf-8')!=fonte_politica(doc['geracoes'][-1]['pesos']):
        raise ErroOmega('Código ativo foi adulterado')
    return {'geracoes':3,'treino':[r['treino_total'] for r in doc['geracoes']],
            'teste':[r['teste_total'] for r in doc['geracoes']],
            'completude_16':certificado_completude(),'hipoteses':len(GENES),
            'politicas_finais_verificadas':len(candidatos(2))}
