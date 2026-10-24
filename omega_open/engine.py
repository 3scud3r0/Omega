"""Ômega 1.3: síntese aberta (Bool^n), metapolítica mutável e trilha auditável.

Cada execução é finita, com orçamentos explícitos. 'Aberta' significa que
não existe lista fixa de tarefas nem teto hardcoded de gerações.
"""
from __future__ import annotations
from itertools import product
from pathlib import Path
import json

from . import logic
from .checker import validate_task,verify_solution,fingerprint

FORMAT='omega-open-chain-1'
BASE=(0,0,0)


def source_policy(weights):
    a,b,c=weights
    return ("# Omega 1.3: programa substituivel de priorizacao\n"
            "parametro nos = 0;\nparametro profundidade = 0;\nparametro operacoes = 0;\n"
            f"tensor prioridade = ({a}) * nos + ({b}) * profundidade + ({c}) * operacoes;\n"
            "mostrar prioridade;\n")


def canonical_write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def model_candidates(task,orders=12,max_nodes=200000):
    result=[]
    n=task['arity'];tab=task['outputs']
    for name,expr in logic.candidates(tab,n,orders):
        m=logic.metrics(expr)
        if m['nos']>max_nodes:continue
        witness={'estrategia':name,'ast':logic.encode(expr),'metricas':m,
                 'semantica_sha256':fingerprint({'arity':n,'outputs':tab})}
        if not verify_solution(task,witness,max_rows=max(len(tab),1),max_nodes=max_nodes):
            raise RuntimeError('Inconsistência: o verificador rejeitou uma hipótese gerada')
        result.append(witness)
    if not result:raise ValueError('Orçamento de nós insuficiente para sintetizar a tarefa '+task['id'])
    return result


def priority(weights,metrics):
    return sum(int(w)*metrics[k] for w,k in zip(weights,('nos','profundidade','operacoes')))


def select(models,weights):
    return min(enumerate(models),key=lambda t:(priority(weights,t[1]['metricas']),t[0]))[1]


def measure(models,weights,train_ids):
    chosen={tid:select(options,weights) for tid,options in models.items()}
    train=[chosen[i]['metricas'] for i in train_ids]
    return (sum(x['nos'] for x in train),sum(x['profundidade'] for x in train))


def policy_search(models,train_ids,radius):
    # A exploração é expandida a cada geração; não há número fixo de políticas.
    if radius<1:raise ValueError('Raio deve ser positivo')
    choices=product(range(radius+1),repeat=3)
    return min(choices,key=lambda p:(measure(models,p,train_ids),sum(p),p))


def record(index,radius,weights,models,train_ids,prev):
    selected={tid:select(options,weights) for tid,options in models.items()}
    tr=set(train_ids)
    cost=measure(models,weights,train_ids)
    test=[v['metricas'] for k,v in selected.items() if k not in tr]
    row={'generation':index,'radius':radius,'weights':list(weights),
         'training_cost':list(cost),
         'holdout_cost':[sum(x['nos'] for x in test),sum(x['profundidade'] for x in test)],
         'solutions':selected,'source_sha256':fingerprint(source_policy(weights)),
         'previous':prev}
    row['id']=fingerprint(row)
    return row


def build(tasks,train_ids,generations=3,max_rows=4096,max_orders=12,max_nodes=200000):
    if type(tasks) is not list or not tasks:raise ValueError('Liste ao menos uma tarefa')
    if not isinstance(generations,int) or generations<0:raise ValueError('Gerações inválidas')
    if max_orders<1 or max_nodes<1 or max_rows<1:raise ValueError('Orçamentos inválidos')
    for t in tasks:validate_task(t,max_rows)
    ids=[x['id'] for x in tasks]
    if len(set(ids))!=len(ids):raise ValueError('IDs de tarefas duplicados')
    if not train_ids or len(set(train_ids))!=len(train_ids) or not set(train_ids)<=set(ids):
        raise ValueError('Informe um conjunto de treinamento não vazio e válido')
    models={t['id']:model_candidates(t,max_orders,max_nodes) for t in tasks}
    rows=[record(0,0,BASE,models,train_ids,'GENESIS')]
    for radius in range(1,generations+1):
        cand=policy_search(models,train_ids,radius)
        new=record(len(rows),radius,cand,models,train_ids,rows[-1]['id'])
        if tuple(new['training_cost']) < tuple(rows[-1]['training_cost']):
            rows.append(new)
    chain={'format':FORMAT,'tasks':tasks,'train_ids':list(train_ids),
           'max_orders':max_orders,'max_nodes':max_nodes,'max_rows':max_rows,
           'searched_radii':generations,'generations':rows}
    chain['sha256']=fingerprint(chain)
    return chain


def verify_chain(doc):
    """Verifica soluções, proveniência por hash e métricas sem confiar na síntese.

    A auditoria exaustiva das estratégias usa audit() para reproduzir busca.
    """
    try:
        if type(doc) is not dict or set(doc)!={'format','tasks','train_ids','max_orders','max_nodes','max_rows','searched_radii','generations','sha256'}:return False
        if doc['format']!=FORMAT or doc['sha256']!=fingerprint({k:v for k,v in doc.items() if k!='sha256'}):return False
        tasks=doc['tasks'];max_rows=doc['max_rows'];max_nodes=doc['max_nodes']
        if type(tasks) is not list or not tasks or type(max_rows) is not int or not 1<=max_rows<=1000000:return False
        if type(max_nodes) is not int or not 1<=max_nodes<=1000000:return False
        if type(doc['max_orders']) is not int or doc['max_orders']<1:return False
        if type(doc['searched_radii']) is not int or doc['searched_radii']<0:return False
        for t in tasks:validate_task(t,max_rows)
        ids=[t['id'] for t in tasks]
        if len(ids)!=len(set(ids)):return False
        train=doc['train_ids']
        if type(train) is not list or not train or len(train)!=len(set(train)) or not set(train)<=set(ids):return False
        generations=doc['generations']
        if type(generations) is not list or not generations:return False
        prev='GENESIS';last=None;last_radius=0
        tasks_by_id={t['id']:t for t in tasks}
        for i,row in enumerate(generations):
            if type(row) is not dict or set(row)!={'generation','radius','weights','training_cost','holdout_cost','solutions','source_sha256','previous','id'}:return False
            if row['generation']!=i or row['previous']!=prev or row['id']!=fingerprint({k:v for k,v in row.items() if k!='id'}):return False
            weights=row['weights']
            if type(weights) is not list or len(weights)!=3 or any(type(v) is not int or v<0 or v>row['radius'] for v in weights):return False
            if (i==0 and (row['radius']!=0 or weights!=list(BASE))) or (i>0 and not last_radius<row['radius']<=doc['searched_radii']):return False
            if row['source_sha256']!=fingerprint(source_policy(weights)):return False
            sols=row['solutions']
            if type(sols) is not dict or set(sols)!=set(ids):return False
            for tid,sol in sols.items():
                if not verify_solution(tasks_by_id[tid],sol,max_rows,max_nodes):return False
            tr=[sols[k]['metricas'] for k in train]
            held=[sols[k]['metricas'] for k in ids if k not in train]
            costs=[sum(v['nos'] for v in tr),sum(v['profundidade'] for v in tr)]
            hold=[sum(v['nos'] for v in held),sum(v['profundidade'] for v in held)]
            if row['training_cost']!=costs or row['holdout_cost']!=hold:return False
            if last is not None and not tuple(costs)<tuple(last):return False
            prev=row['id'];last=costs;last_radius=row['radius']
        return True
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError):return False


def audit(doc):
    if not verify_chain(doc):raise ValueError('Certificado inválido')
    expected=build(doc['tasks'],doc['train_ids'],doc['searched_radii'],
                   doc['max_rows'],doc['max_orders'],doc['max_nodes'])
    if doc != expected:raise ValueError('Cadeia difere da síntese integral reproduzida')
    return {'valid':True,'tasks':len(doc['tasks']),'generations':len(doc['generations']),
            'train_costs':[r['training_cost'][0] for r in doc['generations']],
            'holdout_costs':[r['holdout_cost'][0] for r in doc['generations']]}


def compile_policy(weights):
    """Compila de verdade no motor Ômega anterior quando disponível."""
    try:
        from omega.motor_v1 import MaquinaV1
        from omega_selfhost.driver import compile_text
        from omega.nucleo_v1 import validar_ir
        from fractions import Fraction
    except ImportError:
        return None
    ir=compile_text(source_policy(weights))
    validar_ir(ir)
    machine=MaquinaV1(ir).executar()
    idx=ir['simbolos']['prioridade']
    for n,d,o in ((0,0,0),(1,2,3),(7,3,4),(100,9,23)):
        state={**machine.estado,'nos':Fraction(n),'profundidade':Fraction(d),'operacoes':Fraction(o)}
        if machine.frente(state)[idx]!=priority(weights,{'nos':n,'profundidade':d,'operacoes':o}):
            raise ValueError('Política compilada diverge da semântica exata')
    return ir


def export(doc,path):
    if not verify_chain(doc):raise ValueError('Certificado inválido')
    folder=Path(path);folder.mkdir(parents=True,exist_ok=True)
    canonical_write(folder/'cadeia_aberta.json',doc)
    for row in doc['generations']:
        (folder/f'politica_{row["generation"]}.omega').write_text(source_policy(row['weights']),encoding='utf-8')
        compiled=compile_policy(row['weights'])
        if compiled is not None:
            canonical_write(folder/f'politica_{row["generation"]}.omc',compiled)
    (folder/'politica_ativa.omega').write_text(source_policy(doc['generations'][-1]['weights']),encoding='utf-8')
    return folder


def audit_directory(path):
    p=Path(path);doc=json.loads((p/'cadeia_aberta.json').read_text(encoding='utf-8'))
    result=audit(doc)
    for row in doc['generations']:
        if (p/f'politica_{row["generation"]}.omega').read_text(encoding='utf-8')!=source_policy(row['weights']):
            raise ValueError('Código-fonte de política adulterado')
        generated=compile_policy(row['weights'])
        if generated is not None:
            saved=json.loads((p/f'politica_{row["generation"]}.omc').read_text(encoding='utf-8'))
            if saved!=generated:raise ValueError('IR da política alterada')
    if (p/'politica_ativa.omega').read_text(encoding='utf-8')!=source_policy(doc['generations'][-1]['weights']):
        raise ValueError('Política ativa adulterada')
    return result
