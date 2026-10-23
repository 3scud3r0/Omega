"""Núcleo pequeno de verificação EXAUSTIVA de evolução em domínio finito.

Este módulo NÃO importa o gerador, a VM, o otimizador ou o gradiente.
Para a gramática fixa de três unidades ReLU, usa a redução matemática:
 f(0,0)=0, f(0,1)=f(1,0)=a, f(1,1)=2a+b.
A terceira unidade fica inativa no domínio booleano, mas seu coeficiente
faz parte da complexidade sintática e do programa emitido.

Garantia condicional: sob aritmética de Q e esta semântica fixa,
check_evolution confere exaustivamente o objetivo e a optimalidade dentro
DO ESPAÇO FINITO de hipóteses limitado por raio. Não prova AGI.
"""
from __future__ import annotations
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
import re

FORMATO = 'omega-evolution-cert-1'
CASOS = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))
MAX_RAIO = 4  # 9^3 hipóteses; limitação deliberada de busca exaustiva.
PADRAO = re.compile(r'''\A# Programa sintetizado automaticamente por Omega\.\nparametro x = 0;\nparametro y = 0;\nparametro esperado = 0;\ntensor soma_xy = x \+ y \+ 0;\ntensor h0 = relu\(relu\(soma_xy\)\);\ntensor h1 = relu\(soma_xy - 1\);\ntensor h2 = relu\(soma_xy - 2\);\ntensor saida = \((-?\d+)\) \* h0 \+ \((-?\d+)\) \* h1 \+ \((-?\d+)\) \* h2 \+ 0;\nperda custo = \(saida - esperado\)\^2;\nmostrar saida;\n\Z''')


def tabela_fechada(genes):
    """Expressão matemática simplificada independente da execução da AST."""
    a, b, c = genes
    return ('0', str(a), str(a), str(2*a+b))


def perda_fechada(genes):
    a, b, c = genes
    return 2*(a-1)**2+(2*a+b)**2


def chave(genes):
    return (perda_fechada(genes), sum(abs(x) for x in genes), tuple(genes))


def melhor_no_raio(raio):
    return list(min(product(range(-raio, raio+1),repeat=3),key=chave))


def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def digest(obj):
    return sha256(canon(obj)).hexdigest()


def verificar_evolucao(documento):
    """Aceita apenas uma linhagem ótima em cada raio, com prova exaustiva.

    Sem usar eval, exec, floats, mutação externa nem assinaturas não confiáveis.
    SHA-256 detecta adulteração ACIDENTAL; não autentica um autor.
    """
    try:
        if type(documento) is not dict or set(documento)!= {'formato','dominio','raio_maximo','geracoes','propriedade'}:
            return False
        if documento['formato']!=FORMATO or documento['dominio']!='Bool²' or documento['propriedade']!='erro_quadratico_exaustivo':
            return False
        raio=documento['raio_maximo']; registros=documento['geracoes']
        if type(raio) is not int or not 0<=raio<=MAX_RAIO or type(registros) is not list or len(registros)!=raio+1:
            return False
        previo='GENESIS'; erro_previo=None
        for k,rec in enumerate(registros):
            if type(rec) is not dict or set(rec)!= {'raio','genes','tabela','perda','fonte','sha256_fonte','anterior','id'}:
                return False
            if rec['raio']!=k or type(rec['genes']) is not list or len(rec['genes'])!=3:
                return False
            genes=rec['genes']
            if any(type(v) is not int or abs(v)>k for v in genes):
                return False
            # Verifica a busca ÓTIMA sobre a hipótese finita inteira, sem confiar no gerador.
            if genes!=melhor_no_raio(k):
                return False
            if type(rec['tabela']) is not list or rec['tabela']!=list(tabela_fechada(genes)):
                return False
            erro=perda_fechada(genes)
            if rec['perda']!=str(erro):
                return False
            if erro_previo is not None and erro>=erro_previo:
                return False
            # Vincula o código efetivamente entregue aos coeficientes provados.
            if type(rec['fonte']) is not str or len(rec['fonte'])>4096:
                return False
            match=PADRAO.fullmatch(rec['fonte'])
            if match is None or [int(t) for t in match.groups()]!=genes:
                return False
            if rec['sha256_fonte']!=sha256(rec['fonte'].encode('utf-8')).hexdigest():
                return False
            if rec['anterior']!=previo:
                return False
            fields={key:value for key,value in rec.items() if key!='id'}
            if rec['id']!=digest(fields):
                return False
            previo=rec['id']; erro_previo=erro
        return True
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        return False


def provar_xor_exaustivo(documento):
    """Prova operacional FINITA: |domínio|=4, e erros quadráticos exatos zero."""
    return (verificar_evolucao(documento)
            and documento['geracoes'][-1]['perda']=='0'
            and documento['geracoes'][-1]['tabela']==['0','1','1','0'])
