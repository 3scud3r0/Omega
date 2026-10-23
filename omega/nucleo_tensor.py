"""Verificação independente das operações vetoriais e matriciais.

NÃO importa omega.tensores, omega.algebra ou omega.execucao. Recebe apenas
AST serializada, reconstrói diretamente vetores de polinômios e compara.
"""
from __future__ import annotations

from fractions import Fraction
from . import nucleo as n

MAX_DIM = 32
MAX_PROF = 90


def dimensoes(v):
    if isinstance(v, dict):
        return ()
    if not isinstance(v, tuple) or not 1 <= len(v) <= MAX_DIM:
        raise n.ProvaInvalida('Tensor com dimensão inválida')
    sub = tuple(dimensoes(x) for x in v)
    if len(set(sub)) != 1 or len(sub[0]) > 1:
        raise n.ProvaInvalida('Tensor não retangular ou posto > 2')
    return (len(v), *sub[0])


def par(a, b):
    if dimensoes(a) != dimensoes(b):
        raise n.ProvaInvalida('Dimensões diferentes')
    if isinstance(a, tuple):
        return tuple(par(x, y) for x, y in zip(a, b))
    return n.soma(a, b)


def neg(a):
    if isinstance(a, tuple):
        return tuple(neg(x) for x in a)
    return {m: -c for m,c in a.items()}


def soma_val(a, b, sinal=1):
    if sinal == -1:
        b = neg(b)
    return par(a,b)


def escalar_prod(a, b):
    fa, fb = dimensoes(a), dimensoes(b)
    if fa and fb:
        raise n.ProvaInvalida('Multiplicação de tensores exige @')
    if not fa and not fb:
        return n.produto(a,b)
    if fa:
        return tuple(escalar_prod(x,b) for x in a)
    return tuple(escalar_prod(a,x) for x in b)


def dot(a,b):
    fa, fb = dimensoes(a), dimensoes(b)
    if len(fa) != 1 or fa != fb:
        raise n.ProvaInvalida('dot exige dois vetores de mesmo tamanho')
    acc = {}
    for x,y in zip(a,b):
        acc = n.soma(acc, n.produto(x,y))
    return acc


def mm(a,b):
    fa, fb = dimensoes(a), dimensoes(b)
    if len(fa) != 2 or len(fb) not in (1,2) or fa[1] != fb[0]:
        raise n.ProvaInvalida('Produto matricial incompatível')
    if len(fb) == 1:
        return tuple(dot(a[i], b) for i in range(fa[0]))
    return tuple(tuple(dot(a[i], tuple(b[k][j] for k in range(fb[0])))
                       for j in range(fb[1])) for i in range(fa[0]))


def constante(p):
    if dimensoes(p) or any(m != () for m in p):
        raise n.ProvaInvalida('Operação exige escalar constante')
    return p.get((), Fraction(0))


def avaliar_ast(ast, env=None, nivel=0, visitadas=frozenset()):
    if nivel > MAX_PROF or not isinstance(ast, dict):
        raise n.ProvaInvalida('Árvore tensorial inválida ou profunda demais')
    defs = env or {}
    tipo = ast.get('tipo')
    if tipo == 'lista':
        itens = ast.get('itens')
        if not isinstance(itens,list) or not 1 <= len(itens) <= MAX_DIM:
            raise n.ProvaInvalida('Lista tensorial inválida')
        ans = tuple(avaliar_ast(x, defs, nivel+1, visitadas) for x in itens)
        dimensoes(ans)
        return ans
    if tipo == 'var' and ast.get('nome') in defs:
        var = ast['nome']
        if var in visitadas:
            raise n.ProvaInvalida('Ciclo de tensores')
        return avaliar_ast(defs[var], defs, nivel+1, visitadas | {var})
    if tipo in {'num', 'var'}:
        return n.polinomio(ast)
    if tipo == 'un' and ast.get('op') == '-':
        return neg(avaliar_ast(ast['arg'], defs, nivel+1, visitadas))
    if tipo == 'chamada':
        fname = ast.get('funcao')
        args = ast.get('args')
        if not isinstance(args, list) or len(args) > 2:
            raise n.ProvaInvalida('Chamada inválida')
        args = [avaliar_ast(a,defs,nivel+1,visitadas) for a in args]
        if fname == 'dot' and len(args) == 2:
            return dot(*args)
        if fname == 'transposta' and len(args) == 1:
            matriz = args[0]
            if len(dimensoes(matriz)) != 2:
                raise n.ProvaInvalida('transposta exige matriz')
            return tuple(tuple(matriz[i][j] for i in range(len(matriz)))
                         for j in range(len(matriz[0])))
        raise n.ProvaInvalida('Função tensorial desconhecida')
    if tipo != 'bin' or ast.get('op') not in {'+','-','*','/','^','@'}:
        raise n.ProvaInvalida('Expressão tensorial inválida')
    a = avaliar_ast(ast['esq'],defs,nivel+1,visitadas)
    b = avaliar_ast(ast['dir'],defs,nivel+1,visitadas)
    op = ast['op']
    if op == '+':
        return soma_val(a,b)
    if op == '-':
        return soma_val(a,b,-1)
    if op == '*':
        return escalar_prod(a,b)
    if op == '@':
        return mm(a,b)
    if dimensoes(a) or dimensoes(b):
        raise n.ProvaInvalida('Operação escalar aplicada a tensor')
    c = constante(b)
    if op == '/':
        if c == 0:
            raise n.ProvaInvalida('Divisão por zero')
        return n.produto(a, {():Fraction(1)/c})
    if c.denominator != 1:
        raise n.ProvaInvalida('Expoente não inteiro')
    return n.potencia(a, int(c))


def canon(v):
    if isinstance(v, tuple):
        return [canon(x) for x in v]
    return n.forma_normal(v)


def _defs(obj):
    if not isinstance(obj,dict) or len(obj) > 64:
        raise n.ProvaInvalida('Definições inválidas')
    for nome, ast in obj.items():
        if not isinstance(nome,str) or not nome.isidentifier() or not isinstance(ast,dict):
            raise n.ProvaInvalida('Definição inválida')
    return obj


def validar_expansao(cert):
    defs = _defs(cert['definicoes'])
    original = avaliar_ast(cert['original'], defs)
    expandido = avaliar_ast(cert['expandido'], {})
    return (original == expandido and
            cert['dimensoes'] == list(dimensoes(original)) and
            cert['formas'] == canon(original))


def validar_identidade_tensorial(cert):
    defs = _defs(cert['definicoes'])
    a = avaliar_ast(cert['esquerda'], defs)
    b = avaliar_ast(cert['direita'], defs)
    return (a == b and cert['dimensoes'] == list(dimensoes(a)) and
            cert['formas'] == canon(a))
