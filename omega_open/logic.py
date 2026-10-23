"""Síntese exata de funções Bool^n: AST imutável com compartilhamento de DAG.

Operadores têm interpretação booleana; o verificador está em checker.py.
Nenhum eval, compilação de código não confiável ou operação de rede.
"""
from __future__ import annotations
from itertools import permutations

ZERO = ('c', 0)
ONE = ('c', 1)


def var(i):
    return ('v', i)


def neg(x):
    if x == ZERO: return ONE
    if x == ONE: return ZERO
    if x[0] == 'not': return x[1]
    return ('not', x)


def gate(op, a, b):
    if op in ('and', 'or', 'xor') and repr(a) > repr(b):
        a, b = b, a
    if op == 'and':
        if a == ZERO or b == ZERO: return ZERO
        if a == ONE: return b
        if b == ONE or a == b: return a
        if neg(a) == b: return ZERO
    if op == 'or':
        if a == ONE or b == ONE: return ONE
        if a == ZERO: return b
        if b == ZERO or a == b: return a
        if neg(a) == b: return ONE
    if op == 'xor':
        if a == ZERO: return b
        if b == ZERO: return a
        if a == b: return ZERO
        if a == ONE: return neg(b)
        if b == ONE: return neg(a)
    return (op, a, b)


def choose(x, low, high):
    if low == high: return low
    if low == ZERO and high == ONE: return x
    if low == ONE and high == ZERO: return neg(x)
    return ('ite', x, low, high)


def fold(op, terms, identity):
    result = identity
    for term in terms: result = gate(op, result, term)
    return result


def truth_table(expr, arity):
    """Executor rápido para síntese; checker.py usa avaliador independente."""
    def evaluate(node, bits):
        op=node[0]
        if op == 'c': return node[1]
        if op == 'v': return (bits >> node[1]) & 1
        if op == 'not': return 1-evaluate(node[1], bits)
        if op == 'ite': return evaluate(node[3] if evaluate(node[1], bits) else node[2], bits)
        a,b=evaluate(node[1], bits),evaluate(node[2], bits)
        return {'and':a & b, 'or':a | b, 'xor':a ^ b}[op]
    return [evaluate(expr,i) for i in range(1 << arity)]


def metrics(root):
    seen=set()
    def walk(t):
        if t in seen: return 0,0
        seen.add(t)
        depths=[walk(a)[1] for a in t[1:] if isinstance(a,tuple)]
        return 1,1 + (max(depths) if depths else 0)
    # Depth independently of sharing; count unique DAG nodes.
    def depth(t):
        return 1+max((depth(x) for x in t[1:] if isinstance(x,tuple)),default=0)
    walk(root)
    return {'nos':len(seen),'profundidade':depth(root),'operacoes':sum(t[0] not in ('c','v') for t in seen)}


def dnf(table, n):
    clauses=[]
    for row,val in enumerate(table):
        if val:
            clauses.append(fold('and',(var(j) if row >> j & 1 else neg(var(j)) for j in range(n)),ONE))
    return fold('or',clauses,ZERO)


def anf(table,n):
    coeff=list(table)
    for j in range(n):
        for mask in range(1 << n):
            if mask & (1 << j): coeff[mask] ^= coeff[mask^(1 << j)]
    terms=[]
    for mask,c in enumerate(coeff):
        if c: terms.append(fold('and',(var(j) for j in range(n) if mask >> j & 1),ONE))
    return fold('xor',terms,ZERO)


def shannon(table, n, order):
    def recur(rows, offset):
        values={table[r] for r in rows}
        if len(values)==1: return ONE if 1 in values else ZERO
        if offset >= n: raise ValueError('Tabela inconsistente')
        j=order[offset]
        lows=[r for r in rows if not (r >> j & 1)]
        highs=[r for r in rows if r >> j & 1]
        return choose(var(j),recur(lows,offset+1),recur(highs,offset+1))
    return recur(list(range(1 << n)),0)


def candidates(table,n,max_orders=12):
    """Gera famílias diferentes; max_orders é orçamento, não limite da linguagem."""
    yield 'dnf',dnf(table,n)
    yield 'anf',anf(table,n)
    # Ordens permitem árvores não fixadas a Bool²; enumerador preguiçoso.
    for ix,order in enumerate(permutations(range(n))):
        if ix>=max_orders: break
        yield 'shannon_'+''.join(str(x)+'_' for x in order),shannon(table,n,order)


def encode(expr):
    return [expr[0]]+[encode(a) if isinstance(a,tuple) else a for a in expr[1:]]
