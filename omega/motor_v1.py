"""Ômega 1.0: IR tensorial tipada, execução racional e VJP por operações.

O grafo mantém as matrizes como nós únicos; apenas os VALORES numéricos
ocupam coordenadas. Não forma polinômios por coordenada.
"""
from __future__ import annotations

from fractions import Fraction as Q
from dataclasses import dataclass
import random
from typing import Any

from .sintaxe import (Numero, Variavel, Binario, Unario, Chamada, Lista,
                      Comando, ErroOmega)

MAX_NOS_IR = 12000
MAX_CELULAS = 1_000_000
MAX_DIMENSAO = 2048


def formato(v):
    if not isinstance(v, tuple):
        if not isinstance(v, Q):
            raise ErroOmega('Valor tensorial não racional')
        return ()
    if not v or len(v) > MAX_DIMENSAO:
        raise ErroOmega('Dimensão inválida')
    subs = [formato(x) for x in v]
    if len(set(subs)) != 1 or len(subs[0]) > 0 and len(subs[0]) > 1:
        raise ErroOmega('Tensor não retangular ou ordem maior que 2')
    return (len(v),) + subs[0]


def mk(shape, value):
    if not shape:
        return Q(value)
    return tuple(mk(shape[1:], value) for _ in range(shape[0]))


def tmap(f, *vs):
    if isinstance(vs[0], tuple):
        return tuple(tmap(f, *(v[i] for v in vs)) for i in range(len(vs[0])))
    return f(*vs)


def tadd(a, b): return tmap(lambda x, y: x + y, a, b)
def tsub(a, b): return tmap(lambda x, y: x - y, a, b)
def tneg(a): return tmap(lambda x: -x, a)
def tscale(a, q): return tmap(lambda x: x * q, a)
def tsum(a): return sum(flat(a), Q(0))


def flat(v):
    if isinstance(v, tuple):
        for x in v:
            yield from flat(x)
    else:
        yield v


def transpose(m): return tuple(tuple(m[i][j] for i in range(len(m))) for j in range(len(m[0])))


def mm(a, b):
    if not isinstance(b[0], tuple):
        return tuple(sum((x*y for x, y in zip(row, b)), Q(0)) for row in a)
    bt = transpose(b)
    return tuple(tuple(sum((x*y for x, y in zip(row, col)), Q(0)) for col in bt) for row in a)


def outer(a, b): return tuple(tuple(x*y for y in b) for x in a)


def vshape(op, shapes, extra=None):
    """Assinaturas de operações; shapes são tuplas de dimensões, não valores."""
    a = shapes[0] if shapes else ()
    b = shapes[1] if len(shapes) > 1 else ()
    if op in ('num', 'zeros', 'identidade', 'param', 'stack'):
        raise ErroOmega('Forma de literal ou parâmetro deve ser calculada externamente')
    if op in ('neg', 'relu'):
        return a
    if op in ('+', '-'):
        if a != b: raise ErroOmega(f'Formas incompatíveis: {a} e {b}')
        return a
    if op == '*':
        if a and b: raise ErroOmega('Multiplicação elemento a elemento de dois tensores não suportada')
        return a or b
    if op == '/':
        if b: raise ErroOmega('Denominador tensorial não suportado')
        return a
    if op == '^':
        if a or b: raise ErroOmega('Potência exige escalares')
        return ()
    if op == '@':
        if len(a) != 2 or len(b) not in (1, 2) or a[1] != b[0]:
            raise ErroOmega(f'Multiplicação @ incompatível: {a} e {b}')
        return (a[0],) if len(b) == 1 else (a[0], b[1])
    if op == 'dot':
        if len(a) != 1 or a != b: raise ErroOmega('dot exige vetores iguais')
        return ()
    if op == 'transposta':
        if len(a) != 2: raise ErroOmega('transposta exige matriz')
        return (a[1], a[0])
    if op == 'soma': return ()
    raise ErroOmega('Operador desconhecido: ' + op)


class CompiladorV1:
    def __init__(self):
        self.nos = []
        self.simbolos = {}
        self.parametros = []
        self.perdas = {}
        self.comandos = []

    def no(self, op, args=(), shape=(), **kwargs):
        if len(self.nos) >= MAX_NOS_IR:
            raise ErroOmega('Limite de nós IR excedido')
        if len(shape) > 2 or any(type(n) is not int or n <= 0 or n > MAX_DIMENSAO for n in shape):
            raise ErroOmega('Dimensão IR inválida')
        produto = 1
        for n in shape: produto *= n
        if produto > MAX_CELULAS: raise ErroOmega('Limite de elementos excedido')
        i = len(self.nos)
        self.nos.append({'op': op, 'args': list(args), 'forma': list(shape), **kwargs})
        return i

    def expr(self, e):
        if isinstance(e, Numero): return self.no('num', v=str(e.valor))
        if isinstance(e, Variavel):
            if e.nome not in self.simbolos: raise ErroOmega('Identificador não declarado: '+e.nome)
            return self.simbolos[e.nome]
        if isinstance(e, Lista):
            args = [self.expr(item) for item in e.elementos]
            if not args: raise ErroOmega('Lista vazia')
            shapes = [tuple(self.nos[i]['forma']) for i in args]
            if len(set(shapes)) != 1 or len(shapes[0]) > 1:
                raise ErroOmega('Lista não retangular')
            return self.no('stack', args, (len(args),)+shapes[0])
        if isinstance(e, Unario):
            if e.operador != '-': raise ErroOmega('Unário desconhecido')
            i = self.expr(e.argumento)
            return self.no('neg', [i], self.nos[i]['forma'])
        if isinstance(e, Binario):
            a, b = self.expr(e.esquerda), self.expr(e.direita)
            op = e.operador
            sa, sb = tuple(self.nos[a]['forma']), tuple(self.nos[b]['forma'])
            if op == '^':
                if self.nos[b]['op'] != 'num': raise ErroOmega('Expoente precisa ser literal inteiro')
                n = Q(self.nos[b]['v'])
                if n.denominator != 1 or not 0 <= n <= 20: raise ErroOmega('Expoente fora do intervalo 0..20')
            shape = vshape(op, [sa,sb])
            return self.no(op, [a,b], shape)
        if isinstance(e, Chamada):
            op = e.funcao
            args = [self.expr(a) for a in e.argumentos]
            shapes = [tuple(self.nos[a]['forma']) for a in args]
            if op in ('zeros','identidade'):
                if len(args) not in (1,2): raise ErroOmega(op+' exige dimensões literais')
                nums = []
                for a in args:
                    no = self.nos[a]
                    if no['op'] != 'num': raise ErroOmega('Dimensões devem ser literais')
                    q = Q(no['v'])
                    if q.denominator != 1 or not 1 <= q <= MAX_DIMENSAO:
                        raise ErroOmega('Dimensão fora do intervalo')
                    nums.append(int(q))
                if op == 'identidade':
                    if len(nums) != 1: raise ErroOmega('identidade exige uma dimensão')
                    shape = (nums[0],nums[0])
                else: shape = tuple(nums)
                return self.no(op, [], shape)
            aridades={'relu':1, 'dot':2, 'transposta':1, 'soma':1}
            if op not in aridades or len(args) != aridades[op]:
                raise ErroOmega('Função desconhecida ou aridade inválida: '+op)
            return self.no(op, args, vshape(op, shapes))
        raise ErroOmega('Expressão desconhecida no compilador v1')

    def programa(self, comandos):
        for c in comandos:
            if c.tipo in ('parametro','parametro_tensor','tensor','vetor','matriz','perda'):
                if c.nome in self.simbolos:
                    raise ErroOmega('Redeclaração: '+c.nome)
                if c.expressao is None: raise ErroOmega('Inicializador ausente')
                i = self.expr(c.expressao)
                shape = tuple(self.nos[i]['forma'])
                if c.tipo == 'parametro_tensor':
                    if len(shape) != (1 if c.parametro=='vetor' else 2):
                        raise ErroOmega('Parâmetro tensorial com ordem inválida')
                elif c.tipo == 'parametro' and shape: raise ErroOmega('Parâmetro escalar esperado')
                elif c.tipo == 'vetor' and len(shape)!=1: raise ErroOmega('Vetor esperado')
                elif c.tipo == 'matriz' and len(shape)!=2: raise ErroOmega('Matriz esperada')
                elif c.tipo == 'perda' and shape: raise ErroOmega('Perda precisa ser escalar')
                if c.tipo in ('parametro','parametro_tensor'):
                    p = self.no('param', [], shape, nome=c.nome)
                    self.simbolos[c.nome] = p
                    self.parametros.append({'nome':c.nome, 'id':p, 'inicial':i})
                else:
                    self.simbolos[c.nome] = i
                    if c.tipo == 'perda': self.perdas[c.nome]=i
                self.comandos.append({'tipo':'declaracao', 'nome':c.nome})
            elif c.tipo in ('gradientes','gradiente','passo','passo_livre','passo_ruidoso'):
                if c.nome not in self.perdas: raise ErroOmega('Perda não declarada: '+c.nome)
                registro={'tipo':c.tipo,'nome':c.nome}
                if c.tipo != 'gradientes':
                    if c.parametro not in {p['nome'] for p in self.parametros}:
                        raise ErroOmega('Parâmetro não declarado: '+c.parametro)
                    registro['parametro']=c.parametro
                if c.tipo.startswith('passo'):
                    if c.taxa is None: raise ErroOmega('Taxa obrigatória')
                    r=self.expr(c.taxa)
                    if self.nos[r]['forma']: raise ErroOmega('Taxa precisa ser escalar')
                    registro['taxa']=r
                    if c.tipo == 'passo_ruidoso':
                        if c.semente is None or not 0<=c.semente<2**32:
                            raise ErroOmega('Semente inválida')
                        registro['semente']=c.semente
                self.comandos.append(registro)
            elif c.tipo == 'mostrar':
                if c.nome not in self.simbolos: raise ErroOmega('Símbolo ausente: '+c.nome)
                self.comandos.append({'tipo':'mostrar','nome':c.nome})
            elif c.tipo == 'reescrever':
                if c.nome not in self.perdas: raise ErroOmega('Perda inexistente')
                novo=self.expr(c.expressao)
                if self.nos[novo]['forma']: raise ErroOmega('Reescrita de perda não escalar')
                # v1 só permite equivalências reconhecidas pela normalização certificada.
                if assinatura(self.nos, novo) != assinatura(self.nos, self.perdas[c.nome]):
                    raise ErroOmega('Reescrita não demonstrável pelas regras locais')
                self.simbolos[c.nome]=novo
                self.perdas[c.nome]=novo
                self.comandos.append({'tipo':'reescrever','nome':c.nome})
            else:
                raise ErroOmega('No motor 1.0, use o motor clássico para: '+c.tipo)
        return {'formato':'omega-ir-2', 'versao':'1.0.0', 'nos':self.nos,
                'simbolos':self.simbolos, 'parametros':self.parametros,
                'perdas':self.perdas, 'comandos':self.comandos}


def assinatura(nos, i):
    no=nos[i]
    op=no['op']
    if op=='num': return ('num', str(Q(no['v'])))
    if op=='param': return ('param', no['nome'])
    args=[assinatura(nos,j) for j in no['args']]
    if op in ('+', '*') and all(not nos[j]['forma'] for j in no['args']):
        args=sorted(args, key=str)
    if op=='transposta' and nos[no['args'][0]]['op']=='transposta':
        return assinatura(nos,nos[no['args'][0]]['args'][0])
    if op=='relu' and nos[no['args'][0]]['op']=='relu':
        return assinatura(nos,no['args'][0])
    if op in ('zeros','identidade'): return (op,tuple(no['forma']))
    return (op,tuple(no['forma']),tuple(args))


def num(v):
    if isinstance(v,tuple): return [num(x) for x in v]
    return str(v)


def denum(v):
    if isinstance(v,list): return tuple(denum(x) for x in v)
    if not isinstance(v,str) or len(v)>10000: raise ErroOmega('Número de estado inválido')
    return Q(v)


def perturbar(shape, noise):
    it=iter(noise)
    def rec(s):
        if not s: return next(it)
        return tuple(rec(s[1:]) for _ in range(s[0]))
    return rec(shape)


def ruido(shape, taxa, seed):
    rng=random.Random(seed)
    return perturbar(shape, (taxa*Q(rng.randrange(-1,2),16) for _ in range(prod(shape))))


def prod(shape):
    v=1
    for n in shape: v*=n
    return v


class MaquinaV1:
    def __init__(self, ir):
        self.ir=ir
        self.estado={}
        self.saidas=[]
        self.certificados=[]

    def frente(self, estado=None, limite=None):
        st=self.estado if estado is None else estado
        valores=[]
        for no in self.ir['nos']:
            op=no['op']; a=[valores[j] for j in no['args']]
            if op=='num': v=Q(no['v'])
            elif op=='param':
                if no['nome'] not in st: v=mk(no['forma'],0)
                else: v=st[no['nome']]
            elif op=='stack': v=tuple(a)
            elif op=='zeros': v=mk(no['forma'],0)
            elif op=='identidade':
                n=no['forma'][0]
                v=tuple(tuple(Q(int(i==j)) for j in range(n)) for i in range(n))
            elif op=='neg': v=tneg(a[0])
            elif op=='+': v=tadd(a[0],a[1])
            elif op=='-': v=tsub(a[0],a[1])
            elif op=='*': v=a[0]*a[1] if not isinstance(a[0],tuple) and not isinstance(a[1],tuple) else tscale(a[0],a[1]) if isinstance(a[0],tuple) else tscale(a[1],a[0])
            elif op=='/':
                if a[1]==0: raise ErroOmega('Divisão por zero')
                v=tscale(a[0],1/a[1]) if isinstance(a[0],tuple) else a[0]/a[1]
            elif op=='^': v=a[0]**int(a[1])
            elif op=='@': v=mm(a[0],a[1])
            elif op=='dot': v=sum((x*y for x,y in zip(a[0],a[1])),Q(0))
            elif op=='relu': v=tmap(lambda x:max(x,Q(0)),a[0])
            elif op=='soma': v=tsum(a[0])
            elif op=='transposta': v=transpose(a[0])
            else: raise ErroOmega('Operador IR não executável: '+op)
            valores.append(v)
            if limite is not None and len(valores) - 1 == limite:
                break
        return valores

    def gradientes(self, perda, valores):
        adj=[None]*len(valores)
        def add(i,g): adj[i]=g if adj[i] is None else tadd(adj[i],g)
        add(self.ir['perdas'][perda],Q(1))
        for i in reversed(range(len(valores))):
            if adj[i] is None: continue
            no=self.ir['nos'][i]; op=no['op']; args=no['args']; a=[valores[j] for j in args]; g=adj[i]
            if op in ('num','zeros','identidade','param'): continue
            if op=='stack':
                for j,gj in zip(args,g): add(j,gj)
            elif op=='neg': add(args[0],tneg(g))
            elif op in ('+','-'):
                add(args[0],g); add(args[1],g if op=='+' else tneg(g))
            elif op=='*':
                if not isinstance(a[0],tuple) and not isinstance(a[1],tuple):
                    add(args[0],g*a[1]); add(args[1],g*a[0])
                elif isinstance(a[0],tuple):
                    add(args[0],tscale(g,a[1])); add(args[1],tsum(tmap(lambda x,y:x*y,g,a[0])))
                else:
                    add(args[0],tsum(tmap(lambda x,y:x*y,g,a[1]))); add(args[1],tscale(g,a[0]))
            elif op=='/':
                add(args[0],tscale(g,1/a[1]) if isinstance(g,tuple) else g/a[1])
                add(args[1], -tsum(tmap(lambda x,y:x*y,g,a[0]))/(a[1]**2) if isinstance(g,tuple) else -g*a[0]/(a[1]**2))
            elif op=='^':
                n=int(a[1]); add(args[0],g*n*(a[0]**(n-1)) if n else Q(0))
            elif op=='@':
                if isinstance(a[1][0],tuple):
                    add(args[0],mm(g,transpose(a[1])))
                    add(args[1],mm(transpose(a[0]),g))
                else:
                    add(args[0],outer(g,a[1]))
                    add(args[1],mm(transpose(a[0]),g))
            elif op=='dot':
                add(args[0],tscale(a[1],g)); add(args[1],tscale(a[0],g))
            elif op=='relu': add(args[0],tmap(lambda x,up: up if x>0 else Q(0),a[0],g))
            elif op=='soma': add(args[0],mk(self.ir['nos'][args[0]]['forma'],g))
            elif op=='transposta': add(args[0],transpose(g))
            else: raise ErroOmega('Regra de derivação ausente: '+op)
        return {p['nome']: adj[p['id']] if adj[p['id']] is not None else mk(self.ir['nos'][p['id']]['forma'],0)
                for p in self.ir['parametros']}


    def substituir_ir(self, novo_ir, certificado):
        """Troca SOMENTE o grafo de execução, preservando parâmetros vivos.

        Exige prova estrutural da reescrita e igualdade operacional das perdas
        no estado presente. Não recompila nem reescreve o interpretador Python.
        """
        from .otimizador_v1 import validar_otimizacao
        from .nucleo_v1 import validar_ir
        if certificado.get('original') != self.ir or certificado.get('otimizado') != novo_ir:
            raise ErroOmega('Certificado não corresponde aos grafos')
        if not validar_otimizacao(certificado):
            raise ErroOmega('Troca rejeitada: reescrita não verificável')
        validar_ir(novo_ir)
        if {p['nome']:p['id'] for p in self.ir['parametros']}.keys() != {p['nome']:p['id'] for p in novo_ir['parametros']}.keys():
            raise ErroOmega('Conjunto de parâmetros incompatível')
        anterior=self.frente() if self.estado else None
        maquina=MaquinaV1(novo_ir)
        if self.estado:
            maquina.estado=dict(self.estado)
            depois=maquina.frente()
            if any(anterior[self.ir['perdas'][name]] != depois[novo_ir['perdas'][name]] for name in self.ir['perdas']):
                raise ErroOmega('Troca rejeitada: valor atual da perda diferente')
        self.ir=novo_ir
        return True

    def auto_otimizar(self):
        """Auto-otimização limitada às regras algébricas permitidas."""
        from .otimizador_v1 import otimizar
        novo,certificado=otimizar(self.ir)
        self.substituir_ir(novo,certificado)
        return certificado

    def executar(self):
        from .nucleo_v1 import verificar_certificado_v1, validar_ir
        validar_ir(self.ir)
        # Inicializações podem depender de parâmetros declarados anteriormente.
        for p in self.ir['parametros']:
            val=self.frente(limite=p['inicial'])[p['inicial']]
            if formato(val) != tuple(self.ir['nos'][p['id']]['forma']):
                raise ErroOmega('Inicialização com forma incorreta')
            self.estado[p['nome']]=val
        for c in self.ir['comandos']:
            op=c['tipo']
            if op=='declaracao':
                self.saidas.append('declarado: '+c['nome']); continue
            if op=='reescrever':
                self.saidas.append('reescrita local certificável: '+c['nome']); continue
            valores=self.frente()
            if op=='mostrar':
                self.saidas.append(c['nome']+' = '+str(num(valores[self.ir['simbolos'][c['nome']]])))
                continue
            if op in ('gradiente','gradientes','passo','passo_livre','passo_ruidoso'):
                grads=self.gradientes(c['nome'],valores)
                alvo = c.get('parametro')
                antes=dict(self.estado)
                cert={'tipo':'gradiente_ir' if not op.startswith('passo') else 'passo_ir',
                      'ir':self.ir,'perda':c['nome'], 'estado_antes':{n:num(v) for n,v in antes.items()},
                      'gradientes':{n:num(v) for n,v in grads.items()}}
                if op.startswith('passo'):
                    t=valores[c['taxa']]
                    if t <= 0: raise ErroOmega('Taxa precisa ser positiva')
                    pval=antes[alvo]; gradient=grads[alvo]
                    candidato=tsub(pval,tscale(gradient,t))
                    if op=='passo_ruidoso':
                        candidato=tadd(candidato,ruido(formato(pval),t,c['semente']))
                        cert['semente']=c['semente']
                    depois=dict(antes); depois[alvo]=candidato
                    antiga=valores[self.ir['perdas'][c['nome']]]
                    nova=self.frente(depois)[self.ir['perdas'][c['nome']]]
                    if op=='passo' and nova>antiga:
                        raise ErroOmega(f'Passo rejeitado: perda aumentaria de {antiga} para {nova}')
                    cert.update({'alvo':alvo,'politica':op,'taxa':str(t),
                                 'estado_depois':{n:num(v) for n,v in depois.items()},
                                 'perda_antes':str(antiga),'perda_depois':str(nova)})
                if not verificar_certificado_v1(cert):
                    raise ErroOmega('Núcleo independente rejeitou certificado')
                self.certificados.append(cert)
                if op.startswith('passo'):
                    self.estado=depois
                    self.saidas.append(f'{op} {alvo}: {antiga} -> {nova} (taxa {t})')
                elif op=='gradientes':
                    self.saidas.append(f'gradientes {c["nome"]}: '+str({k:num(v) for k,v in grads.items()}))
                else:
                    self.saidas.append(f'gradiente {alvo}: '+str(num(grads[alvo])))
            else: raise ErroOmega('Comando da VM desconhecido: '+op)
        return self
