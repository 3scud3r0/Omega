"""Sintetizador evolutivo LIMITADO com sucessão de programas Ômega.

É busca exaustiva em três coeficientes e domínio Bool²; os programas são
reais .omega. Cada geração é revisada pelo núcleo independente antes de ser
aceita; a melhor IR também recebe uma prova de reescrita local universal.
"""
from __future__ import annotations
import json
from pathlib import Path
from fractions import Fraction as Q
from hashlib import sha256
from itertools import product

from .sintaxe import analisar, ErroOmega
from .motor_v1 import MaquinaV1
from omega_selfhost.driver import compile_text
from .otimizador_v1 import otimizar, validar_otimizacao
from .nucleo_v1 import validar_ir
from .nucleo_evolucao import (FORMATO,MAX_RAIO,CASOS,digest,
                              verificar_evolucao,provar_xor_exaustivo)


def calcular_fonte(genes):
    a,b,c=genes
    return ("# Programa sintetizado automaticamente por Omega.\n"
            "parametro x = 0;\nparametro y = 0;\nparametro esperado = 0;\n"
            "tensor soma_xy = x + y + 0;\n"
            "tensor h0 = relu(relu(soma_xy));\n"
            "tensor h1 = relu(soma_xy - 1);\n"
            "tensor h2 = relu(soma_xy - 2);\n"
            f"tensor saida = ({a}) * h0 + ({b}) * h1 + ({c}) * h2 + 0;\n"
            "perda custo = (saida - esperado)^2;\n"
            "mostrar saida;\n")


def relu(v):
    return v if v>0 else Q(0)


def executar_hipotese(genes,x,y):
    a,b,c=genes; s=Q(x+y)
    return a*relu(s)+b*relu(s-1)+c*relu(s-2)


def avaliar(genes):
    return (sum((executar_hipotese(genes,x,y)-alvo)**2 for x,y,alvo in CASOS),
            sum(abs(g) for g in genes),tuple(genes))


def sintetizar(raio_maximo=2):
    if type(raio_maximo) is not int or not 0<=raio_maximo<=MAX_RAIO:
        raise ErroOmega('Raio de busca fora do limite 0..4')
    geracoes=[]; predecessor='GENESIS'; anterior=None
    for raio in range(raio_maximo+1):
        genes=list(min(product(range(-raio,raio+1),repeat=3),key=avaliar))
        fonte=calcular_fonte(genes)
        tabela=[str(executar_hipotese(genes,x,y)) for x,y,_ in CASOS]
        erro=str(avaliar(genes)[0])
        if anterior is not None and Q(erro)>=Q(anterior):
            raise ErroOmega('Nenhuma melhoria estrita: parar evolução')
        rec={'raio':raio,'genes':genes,'tabela':tabela,'perda':erro,
             'fonte':fonte,'sha256_fonte':sha256(fonte.encode('utf-8')).hexdigest(),
             'anterior':predecessor}
        rec['id']=digest(rec)
        geracoes.append(rec)
        predecessor=rec['id'];anterior=erro
    doc={'formato':FORMATO,'dominio':'Bool²','raio_maximo':raio_maximo,
         'geracoes':geracoes,'propriedade':'erro_quadratico_exaustivo'}
    if not verificar_evolucao(doc):
        raise ErroOmega('Verificador independente rejeitou evolução')
    return doc


def compilar_fonte(fonte):
    ir=compile_text(fonte)
    validar_ir(ir)
    return ir


def verificar_execucao(ir, genes):
    """Audita a máquina real em TODOS os estados, contra núcleo fechado separado."""
    maquina=MaquinaV1(ir).executar()
    for x,y,alvo in CASOS:
        st={**maquina.estado,'x':Q(x),'y':Q(y),'esperado':Q(alvo)}
        value=maquina.frente(st)[ir['simbolos']['saida']]
        if value!=executar_hipotese(genes,x,y):
            raise ErroOmega('Máquina divergiu do modelo matemático independente')
    return True


def programa_lean(genes):
    """Proposições decidíveis Lean 4 / Int, prontas para compilação externa.

    A prova não é validada neste Python: é necessário executar `lean`.
    """
    a,b,c=genes
    linhas=['-- Quatro teoremas decidíveis sobre aritmética inteira. ',
            '-- Instale Lean 4 e execute `lean obrigacoes_lean.lean` para conferir.',
            'namespace Omega',
            'def relu (x : Int) : Int := if x < 0 then 0 else x', '']
    for x,y,alvo in CASOS:
        lin=(f'({a} : Int) * relu (({x} : Int)+{y}) + '
             f'({b} : Int) * relu (({x} : Int)+{y}-1) + '
             f'({c} : Int) * relu (({x} : Int)+{y}-2)')
        linhas.extend([f'theorem xor_{x}{y} : ({lin}) = ({alvo} : Int) := by',
                       '  decide', ''])
    linhas.append('end Omega')
    return '\n'.join(linhas)+'\n'


def exportar_evolucao(diretorio, raio_maximo=2):
    destino=Path(diretorio);destino.mkdir(parents=True,exist_ok=True)
    doc=sintetizar(raio_maximo)
    for registro in doc['geracoes']:
        (destino/f'geracao_{registro["raio"]}.omega').write_text(registro['fonte'],encoding='utf-8')
    ultimo=doc['geracoes'][-1]
    ir=compilar_fonte(ultimo['fonte'])
    verificar_execucao(ir,ultimo['genes'])
    maquina=MaquinaV1(ir).executar()
    novo,prova=otimizar(ir)
    if not validar_otimizacao(prova):
        raise ErroOmega('Falha em prova de otimização da própria IR')
    if len(novo['nos'])>=len(ir['nos']):
        raise ErroOmega('O programa não reduziu estruturalmente')
    maquina.substituir_ir(novo,prova)
    verificar_execucao(novo,ultimo['genes'])
    def save(nome,obj):
        (destino/nome).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    save('cadeia_provada.json',doc)
    save('codigo_compilado.omc',ir)
    save('codigo_auto_otimizado.omc',novo)
    save('prova_auto_otimizacao.json',prova)
    (destino/'programa_sucessor.omega').write_text(ultimo['fonte'],encoding='utf-8')
    (destino/'obrigacoes_lean.lean').write_text(programa_lean(ultimo['genes']),encoding='utf-8')
    resumo=(f"Ômega — prova finita de evolução\nDomínio completo: Bool² (4 entradas)\n"
            f"Funções avaliadas no último raio: {(2*raio_maximo+1)**3}\n"
            'Gerações: '+ ' → '.join(r['perda'] for r in doc['geracoes'])+' (erro quadrático exato)\n'
            f"Genes finais: {ultimo['genes']}\n"
            f"Prova de XOR no domínio: {provar_xor_exaustivo(doc)}\n"
            f"Nós de IR: {len(ir['nos'])} → {len(novo['nos'])}\n"
            f"Certificado de reescrita: {validar_otimizacao(prova)}\n"
            'Escopo: função XOR em Bool² e equivalências de regras locais, não AGI.\n'
            'As obrigações Lean exigem compilador Lean/Mathlib externo para validação.\n')
    (destino/'RELATORIO.txt').write_text(resumo,encoding='utf-8')
    return resumo


def auditar_artefatos(diretorio):
    """Auditoria integral dos artefatos, não apenas dos campos de um JSON."""
    import json
    destino=Path(diretorio)
    def carregar(nome):
        return json.loads((destino/nome).read_text(encoding='utf-8'))
    doc=carregar('cadeia_provada.json')
    if not verificar_evolucao(doc):
        raise ErroOmega('Certificado evolutivo inválido')
    for rec in doc['geracoes']:
        if (destino/f'geracao_{rec["raio"]}.omega').read_text(encoding='utf-8') != rec['fonte']:
            raise ErroOmega('Fonte de geração adulterada')
        verificar_execucao(compilar_fonte(rec['fonte']),rec['genes'])
    ultimo=doc['geracoes'][-1]
    if (destino/'programa_sucessor.omega').read_text(encoding='utf-8') != ultimo['fonte']:
        raise ErroOmega('Sucessor não corresponde à prova')
    ir=carregar('codigo_compilado.omc')
    if ir!=compilar_fonte(ultimo['fonte']):
        raise ErroOmega('IR compilada divergente da fonte')
    novo=carregar('codigo_auto_otimizado.omc')
    prova=carregar('prova_auto_otimizacao.json')
    if prova.get('original')!=ir or prova.get('otimizado')!=novo or not validar_otimizacao(prova):
        raise ErroOmega('Prova de autotransformação inválida')
    if len(novo['nos'])>=len(ir['nos']):
        raise ErroOmega('Não houve redução estrutural')
    verificar_execucao(novo,ultimo['genes'])
    if (destino/'obrigacoes_lean.lean').read_text(encoding='utf-8')!=programa_lean(ultimo['genes']):
        raise ErroOmega('Obrigações Lean adulteradas')
    return {'geracoes':len(doc['geracoes']),'erro_final':ultimo['perda'],
            'xor_exaustivamente_provado':provar_xor_exaustivo(doc),
            'nos_iniciais':len(ir['nos']),'nos_finais':len(novo['nos'])}
