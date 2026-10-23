"""Microverificador sem dependência do sintetizador nem de seu avaliador.

Verifica semântica total em Bool^n; NÃO prova equivalência sobre R nem AGI.
"""
from __future__ import annotations
import hashlib
import json

OPS={'const':0,'c':1,'v':1,'not':1,'and':2,'or':2,'xor':2,'ite':3}

def canonical(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def fingerprint(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def evaluate(node,bits,arity,fuel=100000):
    """Iterador de programa prefixado: sem eval/exec nem imports de executor."""
    # Valida tipagem e executa recursão restrita por combustível.
    if fuel <= 0 or not isinstance(node,list) or not node or not isinstance(node[0],str):
        raise ValueError('AST inválida/limite de combustível')
    op=node[0]
    if op not in OPS or len(node)-1 != OPS[op]:raise ValueError('Operação/aridade inválida')
    if op=='c':
        if type(node[1]) is not int or node[1] not in (0,1):raise ValueError('Constante inválida')
        return node[1]
    if op=='v':
        if type(node[1]) is not int or not 0<=node[1]<arity:raise ValueError('Variável inválida')
        return int(bool(bits&(1<<node[1])))
    if op=='not': return 1-evaluate(node[1],bits,arity,fuel-1)
    if op=='ite':
        test=evaluate(node[1],bits,arity,fuel-1)
        # valida somente ramo alcançado? Check structural every node separately.
        return evaluate(node[3] if test else node[2],bits,arity,fuel-1)
    left=evaluate(node[1],bits,arity,fuel-1)
    right=evaluate(node[2],bits,arity,fuel-1)
    if op=='and': return int(bool(left and right))
    if op=='or': return int(bool(left or right))
    return (left+right)%2

def validate_tree(node,arity,budget=200000):
    stack=[node]
    count=0
    while stack:
        count+=1
        if count>budget:raise ValueError('AST excede orçamento')
        x=stack.pop()
        if not isinstance(x,list) or not x or x[0] not in ('c','v','not','and','or','xor','ite'):
            raise ValueError('Nó inválido')
        op=x[0]
        if len(x)!=OPS[op]+1:raise ValueError('Número de operandos inválido')
        if op=='v' and (type(x[1]) is not int or x[1]<0 or x[1]>=arity):raise ValueError('Índice de variável inválido')
        if op=='c' and (type(x[1]) is not int or x[1] not in (0,1)):raise ValueError('Constante inválida')
        if op not in ('v','c'):stack.extend(x[1:])
    return True

def validate_task(t,max_rows=4096):
    if type(t) is not dict or set(t)!={'id','arity','outputs'}:raise ValueError('Tarefa deve conter id, arity, outputs')
    n=t['arity']; outputs=t['outputs']
    if type(t['id']) is not str or not t['id'] or len(t['id'])>100:raise ValueError('Identificador inválido')
    if type(n) is not int or n<0:raise ValueError('Número de entradas inválido')
    if type(outputs) is not list or len(outputs)>max_rows or len(outputs)!=(1<<n):
        raise ValueError('Tabela excede orçamento ou tem dimensão inválida')
    if any(type(v) is not int or v not in (0,1) for v in outputs):raise ValueError('Saídas devem ser bits')
    return True

def verify_solution(task,solution,max_rows=4096,max_nodes=200000):
    try:
        validate_task(task,max_rows)
        if type(solution) is not dict or set(solution)!={'ast','semantica_sha256','metricas','estrategia'}:return False
        n=task['arity'];ast=solution['ast']
        validate_tree(ast,n,max_nodes)
        outputs=[evaluate(ast,i,n) for i in range(len(task['outputs']))]
        if outputs!=task['outputs']:return False
        if solution['semantica_sha256']!=fingerprint({'arity':n,'outputs':outputs}):return False
        # Independently tally unique nodes and DAG depth.
        seen=set()
        def tally(x):
            k=canonical(x)
            if k in seen:return
            seen.add(k)
            for child in x[1:]:
                if isinstance(child,list):tally(child)
        tally(ast)
        def depth(x):return 1+max((depth(c) for c in x[1:] if isinstance(c,list)),default=0)
        reported=solution['metricas']
        if type(reported) is not dict or reported.get('nos')!=len(seen) or reported.get('profundidade')!=depth(ast):return False
        if reported.get('operacoes')!=sum(json.loads(x)[0] not in ('c','v') for x in seen):return False
        return type(solution['estrategia']) is str
    except (ValueError,TypeError,KeyError,IndexError,RecursionError,OverflowError):
        return False
