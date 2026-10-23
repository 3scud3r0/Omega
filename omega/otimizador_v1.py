"""Transformações de IR por regras algébricas tipadas, com testemunhas verificáveis.

Não altera Python, CUDA ou código de máquina. O certificado mostra que cada
nó otimizado é obtido por regras locais conhecidas ou pela cópia exata do nó.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as Q
from .sintaxe import ErroOmega
from .nucleo_v1 import validar_ir


REGRAS = ('add_zero', 'sub_zero', 'mul_one', 'div_one', 'pow_one',
          'double_neg', 'double_transpose', 'relu_idem')


def procurar_regra(node, nos):
    op=node['op']; args=node['args']; s=node['forma']
    def literal(i, value):
        return nos[i]['op']=='num' and Q(nos[i]['v'])==value
    if op=='+' and len(args)==2:
        if literal(args[0],0):return ('add_zero',args[1])
        if literal(args[1],0):return ('add_zero',args[0])
    if op=='-' and len(args)==2 and literal(args[1],0):return ('sub_zero',args[0])
    if op=='*' and len(args)==2:
        if literal(args[0],1):return ('mul_one',args[1])
        if literal(args[1],1):return ('mul_one',args[0])
    if op=='/' and literal(args[1],1):return ('div_one',args[0])
    if op=='^' and literal(args[1],1):return ('pow_one',args[0])
    if op=='neg' and nos[args[0]]['op']=='neg':return ('double_neg',nos[args[0]]['args'][0])
    if op=='transposta' and nos[args[0]]['op']=='transposta':
        return ('double_transpose',nos[args[0]]['args'][0])
    if op=='relu' and nos[args[0]]['op']=='relu':return ('relu_idem',args[0])
    return None


def otimizar(ir):
    validar_ir(ir)
    nos=[]; remap=[]; provas=[]
    for i,n in enumerate(ir['nos']):
        clone=deepcopy(n)
        clone['args']=[remap[j] for j in n['args']]
        regra=procurar_regra(clone,nos)
        if regra is not None:
            nome,destino=regra
            if clone['forma']!=nos[destino]['forma']:
                raise ErroOmega('Otimização inválida: formas divergentes')
            remap.append(destino)
            provas.append({'indice':i,'regra':nome,'resultado':destino})
        else:
            remap.append(len(nos))
            nos.append(clone)
    result=deepcopy(ir)
    result['nos']=nos
    result['simbolos']={k:remap[v] for k,v in ir['simbolos'].items()}
    result['perdas']={k:remap[v] for k,v in ir['perdas'].items()}
    result['parametros']=[{**p,'id':remap[p['id']],'inicial':remap[p['inicial']]}
                          for p in ir['parametros']]
    result['comandos']=[{k:(remap[v] if k=='taxa' else v) for k,v in c.items()}
                        for c in ir['comandos']]
    validar_ir(result)
    cert={'tipo':'reescrita_ir','formato':'omega-opt-cert-1',
          'original':ir,'otimizado':result,'mapeamento':remap,'regras':provas}
    if not validar_otimizacao(cert):
        raise ErroOmega('Reescrita recusada pelo verificador de transformação')
    return result,cert


def validar_otimizacao(cert):
    """Reaplica localmente regras de equivalência ao mapa declarado.

    Não chama otimizar e não executa exemplos de teste. Cada igualdade é
    uma instância de uma regra da base confiável deste módulo.
    """
    try:
        if not isinstance(cert,dict) or cert.get('formato')!='omega-opt-cert-1':return False
        orig=cert['original']; new=cert['otimizado']; mp=cert['mapeamento']; proof=cert['regras']
        validar_ir(orig); validar_ir(new)
        if not isinstance(mp,list) or len(mp)!=len(orig['nos']) or not isinstance(proof,list):return False
        if len(proof)>len(mp):return False
        por_indice={p['indice']:p for p in proof if isinstance(p,dict) and type(p.get('indice')) is int}
        if len(por_indice)!=len(proof):return False
        pos=0
        for i,node in enumerate(orig['nos']):
            if type(mp[i]) is not int:return False
            clone=deepcopy(node)
            clone['args']=[mp[j] for j in node['args']]
            if any(j>=pos or j<0 for j in clone['args']):return False
            if i in por_indice:
                entry=por_indice[i]
                rule=procurar_regra(clone,new['nos'][:pos])
                if rule is None or rule[0]!=entry['regra'] or rule[1]!=entry['resultado']:
                    return False
                if mp[i]!=rule[1] or clone['forma']!=new['nos'][mp[i]]['forma']:return False
            else:
                if mp[i]!=pos or pos>=len(new['nos']) or clone!=new['nos'][pos]:return False
                pos+=1
        if pos != len(new['nos']):return False
        if new['simbolos']!={k:mp[v] for k,v in orig['simbolos'].items()}:return False
        if new['perdas']!={k:mp[v] for k,v in orig['perdas'].items()}:return False
        if new['parametros']!=[{**p,'id':mp[p['id']],'inicial':mp[p['inicial']]} for p in orig['parametros']]:return False
        cmds=[{k:(mp[v] if k=='taxa' else v) for k,v in c.items()} for c in orig['comandos']]
        if new['comandos']!=cmds:return False
        return True
    except (KeyError,IndexError,TypeError,ValueError,RecursionError,ErroOmega,ZeroDivisionError):
        return False
