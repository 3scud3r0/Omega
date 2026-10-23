"""Núcleo independente para verificação FINITA de políticas de metabusca.

Não importa o compilador Ômega, a VM, o sintetizador, nem a tabela de
resultados do executor. Recalcula políticas, enumeração e todas as 16 funções
Booleanas (duas entradas). Não prova generalização aberta nem AGI.
"""
from __future__ import annotations
from itertools import product
from hashlib import sha256
import json

FORMATO='omega-meta-cert-1'
GENES=tuple(product(range(-2,3),repeat=4))  # 625 hipóteses em ordem fixa
TREINO=(0,1,2,4,6,7,8,13)  # split selado antes da busca
TESTE=tuple(i for i in range(16) if i not in TREINO)
PESOS=tuple(product((-1,0,1), repeat=5))
BASE=(0,0,0,0,0)


def canon(d):
    return json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()


def digest(d):
    return sha256(canon(d)).hexdigest()


def saidas(g):
    """Expressão fechada para a base 1,x,y,AND, sem executar AST ou VM."""
    p,q,r,s=g
    return (p,p+r,p+q,p+q+r+s)


def alvo(k):
    return tuple((k>>j)&1 for j in range(4))


def certificado_completude():
    """Representabilidade para cada tabela: fórmula de diferenças finitas."""
    for k in range(16):
        v=alvo(k)
        g=(v[0],v[2]-v[0],v[1]-v[0],v[3]-v[2]-v[1]+v[0])
        if g not in GENES or saidas(g)!=v:
            return False
    return True


def escore(p,g):
    return p[0]*sum(abs(v) for v in g) + sum(p[i+1]*g[i] for i in range(4))


def contagens(p):
    """Reexecuta enumeração exaustiva independente, sem atalho de busca."""
    ordenados=sorted(GENES,key=lambda g:(escore(p,g),g))
    indices={}
    for n,g in enumerate(ordenados,1):
        indices.setdefault(saidas(g),n)
    return tuple(indices[alvo(k)] for k in range(16))


def objetivo(p):
    n=contagens(p)
    return (sum(n[i] for i in TREINO),max(n[i] for i in TREINO),sum(abs(v) for v in p),p)


def candidatos(fase):
    if fase==0:return (BASE,)
    if fase==1:return tuple(w for w in PESOS if sum(v!=0 for v in w)<=1)
    if fase==2:return PESOS
    raise ValueError('Fase inválida')


def otimo(fase):
    return min(candidatos(fase),key=objetivo)


def verificar(doc):
    """Auditoria de cada campo; hashes não substituem verificação matemática."""
    try:
        if type(doc) is not dict or set(doc)!={'formato','dominio','parametros','treino','teste','geracoes','hash'}:
            return False
        if doc['formato']!=FORMATO or doc['dominio']!='Bool^2' or doc['parametros']!='(-2..2)^4':return False
        if doc['treino']!=list(TREINO) or doc['teste']!=list(TESTE):return False
        if not certificado_completude():return False
        recs=doc['geracoes']
        if type(recs) is not list or len(recs)!=3:return False
        prev='GENESIS'; old=None
        for fase,rec in enumerate(recs):
            if type(rec) is not dict or set(rec)!={'fase','pesos','hipoteses','avaliacoes','treino_total','teste_total','prev','codigo_sha256','id'}:return False
            p=rec['pesos']
            if type(p) is not list or len(p)!=5 or any(type(k) is not int or k not in (-1,0,1) for k in p):return False
            if rec['fase']!=fase or tuple(p)!=otimo(fase):return False
            if rec['hipoteses']!=len(candidatos(fase)):return False
            n=contagens(p)
            if rec['avaliacoes']!=list(n) or rec['treino_total']!=sum(n[i] for i in TREINO) or rec['teste_total']!=sum(n[i] for i in TESTE):return False
            if old is not None and rec['treino_total']>=old:return False
            if rec['prev']!=prev:return False
            # Vincula o código à semântica somente após checar o template
            from hashlib import sha256
            from .meta_programa import fonte_politica  # somente template, não sintese nem VM
            if rec['codigo_sha256']!=sha256(fonte_politica(p).encode()).hexdigest():return False
            if rec['id']!=digest({k:v for k,v in rec.items() if k!='id'}):return False
            prev=rec['id'];old=rec['treino_total']
        return doc['hash']==digest({k:v for k,v in doc.items() if k!='hash'})
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError,ImportError):
        return False
