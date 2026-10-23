"""Verificador independente da fita reversa Ômega 1.0.

Valida a IR estaticamente e recalcula derivadas por propagação DIRETA de
números duais racionais, sem importar o executor nem seus operadores tensoriais.
Até 64 coordenadas executa todos os vetores-base. Acima disso, compara 8
direções determinísticas: validação parcial, explicitamente não exaustiva.
"""
from __future__ import annotations

from fractions import Fraction as F
import random

from .sintaxe import ErroOmega

OP_UN = {'neg','relu','soma','transposta'}
OP_BIN = {'+','-','*','/','^','@','dot'}
OP_NULO = {'num','param','zeros','identidade'}


def check_form(s):
    if not isinstance(s,list) or len(s)>2 or any(type(n) is not int or not 1<=n<=2048 for n in s):
        raise ErroOmega('Forma incorreta na IR')
    size=1
    for n in s: size*=n
    if size>1_000_000: raise ErroOmega('Tensor demasiado grande')
    return tuple(s)


def validar_ir(ir):
    if not isinstance(ir,dict) or ir.get('formato')!='omega-ir-2':
        raise ErroOmega('IR v1 incompatível')
    nodes=ir.get('nos')
    if not isinstance(nodes,list) or not 1<=len(nodes)<=12000:
        raise ErroOmega('Número de nós inválido')
    formas=[]; nomes=[]
    for i,n in enumerate(nodes):
        if not isinstance(n,dict) or not isinstance(n.get('op'),str):
            raise ErroOmega('Nó malformado')
        op=n['op']; args=n.get('args'); shape=check_form(n.get('forma'))
        if not isinstance(args,list) or any(type(j) is not int or j<0 or j>=i for j in args):
            raise ErroOmega('Referência futura ou inválida no grafo')
        f=[formas[j] for j in args]
        if op=='num':
            if args or shape or not isinstance(n.get('v'),str) or len(n['v'])>10000: raise ErroOmega('Número inválido')
            try: F(n['v'])
            except (ValueError,ZeroDivisionError): raise ErroOmega('Literal racional inválido') from None
        elif op=='param':
            name=n.get('nome')
            if args or not isinstance(name,str) or not name.isidentifier() or name in nomes:
                raise ErroOmega('Parâmetro malformado ou repetido')
            nomes.append(name)
        elif op in ('zeros','identidade'):
            if args or len(shape) not in (1,2) or (op=='identidade' and (len(shape)!=2 or shape[0]!=shape[1])):
                raise ErroOmega('Construtor tensorial inválido')
        elif op=='stack':
            if not args or len(set(f))!=1 or shape!=(len(args),)+f[0] or len(shape)>2:
                raise ErroOmega('Empilhamento mal tipado')
        elif op in OP_UN | OP_BIN:
            if len(args)!=(1 if op in OP_UN else 2): raise ErroOmega('Aridade inválida')
            a=f[0]; b=f[1] if len(f)==2 else ()
            if op in ('neg','relu'): expected=a
            elif op in ('+','-'):
                if a!=b: raise ErroOmega('Soma com formas distintas')
                expected=a
            elif op=='*':
                if a and b: raise ErroOmega('Dois tensores em multiplicação escalar')
                expected=a or b
            elif op=='/':
                if b: raise ErroOmega('Divisão por tensor')
                expected=a
            elif op=='^':
                if a or b or nodes[args[1]]['op']!='num': raise ErroOmega('Potência fora da regra')
                exp=F(nodes[args[1]]['v'])
                if exp.denominator!=1 or not 0<=exp<=20: raise ErroOmega('Expoente inválido')
                expected=()
            elif op=='@':
                if len(a)!=2 or len(b) not in (1,2) or a[1]!=b[0]:
                    raise ErroOmega('Produto matricial mal tipado')
                expected=(a[0],) if len(b)==1 else (a[0],b[1])
            elif op=='dot':
                if len(a)!=1 or a!=b: raise ErroOmega('Produto interno mal tipado')
                expected=()
            elif op=='transposta':
                if len(a)!=2: raise ErroOmega('Transposta mal tipada')
                expected=(a[1],a[0])
            else: expected=()
            if shape!=expected: raise ErroOmega(f'Forma adulterada no operador {op}')
        else: raise ErroOmega('Operador IR não autorizado: '+op)
        formas.append(shape)
    params=ir.get('parametros'); sym=ir.get('simbolos'); loss=ir.get('perdas'); cmds=ir.get('comandos')
    if not isinstance(params,list) or not isinstance(sym,dict) or not isinstance(loss,dict) or not isinstance(cmds,list):
        raise ErroOmega('Tabelas IR ausentes')
    visto=set()
    for p in params:
        if not isinstance(p,dict) or p.get('nome') in visto or type(p.get('id')) is not int or type(p.get('inicial')) is not int:
            raise ErroOmega('Parâmetro IR repetido/inválido')
        name=p['nome']; i=p['id']; init=p['inicial']
        if not 0<=init<i<len(nodes) or nodes[i]['op']!='param' or nodes[i]['nome']!=name or formas[i]!=formas[init]:
            raise ErroOmega('Assinatura de parâmetro inválida')
        visto.add(name)
    if visto != set(nomes): raise ErroOmega('Parâmetros da IR inconsistentes')
    for label, ids in [('símbolos',sym),('perdas',loss)]:
        for name,i in ids.items():
            if not isinstance(name,str) or not name.isidentifier() or type(i) is not int or not 0<=i<len(nodes):
                raise ErroOmega('Referência inválida: '+label)
            if label=='perdas' and formas[i]: raise ErroOmega('Perda não escalar')
    for cmd in cmds:
        if not isinstance(cmd,dict) or cmd.get('tipo') not in ('declaracao','mostrar','gradiente','gradientes','passo','passo_livre','passo_ruidoso','reescrever'):
            raise ErroOmega('Comando IR inválido')
        tipo=cmd['tipo']; name=cmd.get('nome')
        if tipo in ('gradiente','gradientes','passo','passo_livre','passo_ruidoso') and name not in loss:
            raise ErroOmega('Comando com perda inexistente')
        if tipo in ('gradiente','passo','passo_livre','passo_ruidoso') and cmd.get('parametro') not in visto:
            raise ErroOmega('Comando com parâmetro inexistente')
        if tipo.startswith('passo'):
            i=cmd.get('taxa')
            if type(i) is not int or not 0<=i<len(nodes) or formas[i]:
                raise ErroOmega('Taxa inválida na IR')
            if tipo=='passo_ruidoso' and (type(cmd.get('semente')) is not int or not 0<=cmd['semente']<2**32):
                raise ErroOmega('Semente inválida na IR')
    return True


def formato(v):
    if isinstance(v,tuple):
        if not v: raise ErroOmega('Tensor vazio')
        dims={formato(x) for x in v}
        if len(dims)!=1: raise ErroOmega('Valor tensorial irregular')
        return (len(v),)+next(iter(dims))
    if not isinstance(v,F): raise ErroOmega('Escalar racional obrigatório')
    return ()


def read(v):
    if isinstance(v,list): return tuple(read(x) for x in v)
    if not isinstance(v,str) or len(v)>10000: raise ErroOmega('Escalar serializado inválido')
    return F(v)


def elem(fn,*vs):
    if isinstance(vs[0],tuple):
        return tuple(elem(fn,*(v[k] for v in vs)) for k in range(len(vs[0])))
    return fn(*vs)


def z(s):
    if not s: return F(0)
    return tuple(z(s[1:]) for _ in range(s[0]))


def const(s,q):
    if not s: return q
    return tuple(const(s[1:],q) for _ in range(s[0]))


def plus(a,b):return elem(lambda x,y:x+y,a,b)
def times(a,c):return elem(lambda x:x*c,a)
def total(a):
    if not isinstance(a,tuple):return a
    return sum((total(x) for x in a),F(0))


def mm(a,b):
    if not isinstance(b[0],tuple):
        return tuple(sum((a[i][k]*b[k] for k in range(len(b))),F(0)) for i in range(len(a)))
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(len(b))),F(0)) for j in range(len(b[0]))) for i in range(len(a)))


def aval_dual(ir, estado, direcao):
    """Dual forward: (valor, derivada direcional). Independente da VJP."""
    out=[]
    for node in ir['nos']:
        op=node['op']; aa=[out[i] for i in node['args']]
        if op=='num': pair=(F(node['v']),F(0))
        elif op=='param':
            name=node['nome']; pair=(estado[name],direcao[name])
        elif op=='zeros': pair=(z(node['forma']),z(node['forma']))
        elif op=='identidade':
            n=node['forma'][0]; pair=(tuple(tuple(F(int(i==j)) for j in range(n)) for i in range(n)),z(node['forma']))
        elif op=='stack': pair=(tuple(a[0] for a in aa),tuple(a[1] for a in aa))
        elif op=='neg': pair=tuple(elem(lambda x:-x,a) for a in aa[0])
        elif op in ('+','-'):
            fn=(lambda x,y:x+y) if op=='+' else (lambda x,y:x-y)
            pair=(elem(fn,aa[0][0],aa[1][0]),elem(fn,aa[0][1],aa[1][1]))
        elif op=='*':
            (a,da),(b,db)=aa
            if isinstance(a,tuple): pair=(times(a,b),plus(times(da,b),times(a,db)))
            elif isinstance(b,tuple): pair=(times(b,a),plus(times(db,a),times(b,da)))
            else: pair=(a*b,da*b+a*db)
        elif op=='/':
            (a,da),(b,db)=aa
            if not b: raise ErroOmega('Divisão por zero')
            pair=(times(a,F(1)/b),plus(times(da,F(1)/b),times(a,-db/(b*b)))) if isinstance(a,tuple) else (a/b,(da*b-a*db)/(b*b))
        elif op=='^':
            (a,da),(b,_)=aa; n=int(b)
            pair=(a**n, F(0) if n==0 else n*a**(n-1)*da)
        elif op=='@':
            (a,da),(b,db)=aa
            pair=(mm(a,b),plus(mm(da,b),mm(a,db)))
        elif op=='dot':
            (a,da),(b,db)=aa
            pair=(sum((x*y for x,y in zip(a,b)),F(0)),
                  sum((x*y+u*v for x,y,u,v in zip(da,b,a,db)),F(0)))
        elif op=='relu':
            a,da=aa[0]
            pair=(elem(lambda x:max(F(0),x),a),elem(lambda x,y:y if x>0 else F(0),a,da))
        elif op=='soma': pair=(total(aa[0][0]),total(aa[0][1]))
        elif op=='transposta':
            a,da=aa[0]
            pair=(tuple(tuple(a[i][j] for i in range(len(a))) for j in range(len(a[0]))),
                  tuple(tuple(da[i][j] for i in range(len(da))) for j in range(len(da[0]))))
        else: raise ErroOmega('Operador sem semântica dual')
        out.append(pair)
    return out


def campos(v):
    if isinstance(v,tuple):
        for e in v: yield from campos(e)
    else: yield v


def shape_indices(shape):
    if not shape: yield ()
    elif len(shape)==1:
        for i in range(shape[0]): yield (i,)
    else:
        for i in range(shape[0]):
            for j in range(shape[1]): yield (i,j)


def valor_indice(v,idx):
    for j in idx: v=v[j]
    return v


def direcao_estrutura(shape,indices,valor=F(1)):
    S=set(indices)
    if not shape:return valor if () in S else F(0)
    if len(shape)==1:return tuple(valor if (i,) in S else F(0) for i in range(shape[0]))
    return tuple(tuple(valor if (i,j) in S else F(0) for j in range(shape[1])) for i in range(shape[0]))


def direcoes(params,estado):
    coords=[(p['nome'],idx) for p in params for idx in shape_indices(formato(estado[p['nome']]))]
    if len(coords)<=64:
        for nome,idx in coords:
            yield {p['nome']:direcao_estrutura(formato(estado[p['nome']]),[idx]) if p['nome']==nome else z(formato(estado[p['nome']])) for p in params}
    else:
        for j in range(8):
            rng=random.Random(5821+j)
            vals={}
            for p in params:
                name=p['nome']; shape=formato(estado[name]); indices=list(shape_indices(shape))
                d={idx:(F(1) if j==0 else F(rng.randrange(-1,2))) for idx in indices}
                if not shape: vals[name]=d[()]
                elif len(shape)==1: vals[name]=tuple(d[(i,)] for i in range(shape[0]))
                else: vals[name]=tuple(tuple(d[(i,k)] for k in range(shape[1])) for i in range(shape[0]))
            yield vals


def validar_estado(ir,serial):
    if not isinstance(serial,dict) or set(serial)!={p['nome'] for p in ir['parametros']}:
        raise ErroOmega('Conjunto de parâmetros inválido')
    st={}
    for p in ir['parametros']:
        val=read(serial[p['nome']]); shape=tuple(ir['nos'][p['id']]['forma'])
        if formato(val)!=shape: raise ErroOmega('Estado com dimensões adulteradas')
        st[p['nome']]=val
    return st


def comp_grad(ir,st,claimed,perda):
    """Gradiente via dual exato para todas as coordenadas até 64."""
    if not isinstance(claimed,dict) or set(claimed)!=set(st): return False
    grad={k:read(v) for k,v in claimed.items()}
    if any(formato(grad[k])!=formato(st[k]) for k in st):return False
    if perda not in ir['perdas']:return False
    idx=ir['perdas'][perda]
    for d in direcoes(ir['parametros'],st):
        comp=aval_dual(ir,st,d)[idx][1]
        esperado=sum((total(elem(lambda x,y:x*y,grad[name],d[name])) for name in st),F(0))
        if comp != esperado:return False
    return True


def ruido_indep(shape,taxa,seed):
    rng=random.Random(seed)
    if not shape:return taxa*F(rng.randrange(-1,2),16)
    def rec(s):
        if not s:return taxa*F(rng.randrange(-1,2),16)
        return tuple(rec(s[1:]) for _ in range(s[0]))
    return rec(shape)


def verificar_certificado_v1(cert):
    try:
        if not isinstance(cert,dict) or cert.get('tipo') not in ('gradiente_ir','passo_ir'):return False
        ir=cert['ir']; validar_ir(ir)
        st=validar_estado(ir,cert['estado_antes']); loss=cert['perda']
        if not comp_grad(ir,st,cert['gradientes'],loss):return False
        if cert['tipo']=='gradiente_ir':return True
        policy=cert['politica']; target=cert['alvo']; grads={n:read(v) for n,v in cert['gradientes'].items()}
        if policy not in ('passo','passo_livre','passo_ruidoso') or target not in st:return False
        if not any(c.get('tipo')==policy and c.get('nome')==loss and c.get('parametro')==target
                   and (policy!='passo_ruidoso' or c.get('semente')==cert.get('semente')) for c in ir['comandos']): return False
        # taxa vem de uma instrução do programa, não de entrada arbitrária da prova
        cmds=[c for c in ir['comandos'] if c.get('tipo')==policy and c.get('nome')==loss and c.get('parametro')==target]
        taxas=[aval_dual(ir,st,{name:z(formato(v)) for name,v in st.items()})[c['taxa']][0] for c in cmds]
        t=F(cert['taxa'])
        if t<=0 or t not in taxas:return False
        expected=elem(lambda x,y:x-t*y,st[target],grads[target])
        if policy=='passo_ruidoso':
            seed=cert.get('semente')
            if type(seed) is not int or not 0<=seed<2**32:return False
            expected=plus(expected,ruido_indep(formato(st[target]),t,seed))
        after=validar_estado(ir,cert['estado_depois'])
        if set(after)!=set(st) or after[target]!=expected:return False
        if any(after[k]!=v for k,v in st.items() if k!=target):return False
        null={name:z(formato(v)) for name,v in st.items()}
        l0=aval_dual(ir,st,null)[ir['perdas'][loss]][0]
        l1=aval_dual(ir,after,null)[ir['perdas'][loss]][0]
        if (l0,l1)!=(F(cert['perda_antes']),F(cert['perda_depois'])):return False
        if policy=='passo' and l1>l0:return False
        return True
    except (KeyError,TypeError,ValueError,ZeroDivisionError,OverflowError,
            IndexError,RecursionError,ErroOmega) as err:
        # Rejeita dados inválidos sem propagar falhas do verificador.
        return False
