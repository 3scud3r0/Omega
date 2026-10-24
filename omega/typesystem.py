"""Static inference for the numeric/tensor surface language, without execution.

The procedural bootstrap dialect is separate. No claim about its dynamic
containers or I/O is made by this pass.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from types import MappingProxyType
import unicodedata

from .sintaxe import Numero,Variavel,Unario,Binario,Lista,Chamada,ErroOmega,Analisador,Token


class TypeCheckError(ErroOmega):
    pass


@dataclass(frozen=True)
class _NumberLiteral:
    text: str


class _TypeParser(Analisador):
    """Reuse the grammar without evaluating arbitrary-size rational literals."""
    def __init__(self,source):
        super().__init__(source)
        tokens=[]
        for token in self.tokens:
            if token.tipo=='NUMERO':
                text=''.join(c if c=='.' else str(unicodedata.decimal(c)) for c in token.texto)
                integer,separator,fraction=text.partition('.')
                text=(integer.lstrip('0') or '0')+(separator+fraction if separator else '')
                token=Token(token.tipo,text,token.linha,token.coluna)
            tokens.append(token)
        self.tokens=tokens
    def atomo(self):
        if self.atual.tipo=='NUMERO':
            value=_NumberLiteral(self.atual.texto);self.indice+=1;return value
        return super().atomo()


def _literal_nat(value,maximum):
    if isinstance(value,Numero):
        q=value.valor
        if q.denominator!=1 or not 0<=q<=maximum:raise TypeCheckError('Literal integer outside its static bound')
        return int(q)
    if not isinstance(value,_NumberLiteral):raise TypeCheckError('Literal integer required')
    integer,_,fraction=value.text.partition('.')
    if any(c!='0' for c in fraction) or len(integer)>len(str(maximum)):
        raise TypeCheckError('Literal integer outside its static bound')
    result=int(integer)
    if result>maximum:raise TypeCheckError('Literal integer outside its static bound')
    return result


@dataclass(frozen=True)
class NumericType:
    shape: tuple[int,...]=()

    def __post_init__(self):
        if type(self.shape) is not tuple or len(self.shape)>2:
            raise TypeCheckError('Numeric tensors have rank at most two')
        size=1
        for dimension in self.shape:
            if type(dimension) is not int or not 1<=dimension<=2048:
                raise TypeCheckError('Tensor dimensions must be integers in 1..2048')
            size*=dimension
        if size>1_000_000:raise TypeCheckError('Tensor element budget exceeded')

    @property
    def scalar(self):return not self.shape

    def to_dict(self):return {'element':'rational','shape':list(self.shape)}


RATIONAL=NumericType()


def infer_operation(operator,arguments):
    """Type rules use dimensions alone, never concrete tensor values."""
    arities={'neg':1,'relu':1,'soma':1,'transposta':1,
             '+':2,'-':2,'*':2,'/':2,'^':2,'@':2,'dot':2}
    if operator not in arities or len(arguments)!=arities[operator]:
        raise TypeCheckError('Unknown operation or wrong arity: '+str(operator))
    if any(not isinstance(t,NumericType) for t in arguments):
        raise TypeCheckError('Numeric operands required')
    a=arguments[0];b=arguments[1] if len(arguments)==2 else RATIONAL
    if operator in ('neg','relu'):return a
    if operator in ('+','-'):
        if a!=b:raise TypeCheckError('Addition/subtraction requires identical tensor types')
        return a
    if operator=='*':
        if not a.scalar and not b.scalar:raise TypeCheckError('Scalar multiplication requires a scalar operand')
        return b if a.scalar else a
    if operator=='/':
        if not b.scalar:raise TypeCheckError('The denominator must be scalar')
        return a
    if operator=='^':
        if not a.scalar or not b.scalar:raise TypeCheckError('Power requires scalar operands')
        return RATIONAL
    if operator=='@':
        if len(a.shape)!=2 or len(b.shape) not in (1,2) or a.shape[1]!=b.shape[0]:
            raise TypeCheckError('Matrix product has incompatible tensor types')
        return NumericType((a.shape[0],) if len(b.shape)==1 else (a.shape[0],b.shape[1]))
    if operator=='dot':
        if len(a.shape)!=1 or a!=b:raise TypeCheckError('Dot product requires identical vector types')
        return RATIONAL
    if operator=='transposta':
        if len(a.shape)!=2:raise TypeCheckError('Transpose requires a matrix')
        return NumericType(tuple(reversed(a.shape)))
    return RATIONAL  # soma


def _infer_expression(expression,context,proof_variables,budget,depth):
    budget[0]-=1
    if budget[0]<0 or depth>200:raise TypeCheckError('Type inference budget exceeded')
    def infer(e):return _infer_expression(e,context,proof_variables,budget,depth+1)
    if isinstance(expression,(Numero,_NumberLiteral)):return RATIONAL
    if isinstance(expression,Variavel):
        if expression.nome in context:
            value=context[expression.nome]
            if not isinstance(value,NumericType):raise TypeCheckError('Invalid type binding: '+expression.nome)
            return value
        if proof_variables:return RATIONAL
        raise TypeCheckError('Undeclared identifier: '+expression.nome)
    if isinstance(expression,Unario):
        if expression.operador!='-':raise TypeCheckError('Unknown unary operator')
        return infer_operation('neg',[infer(expression.argumento)])
    if isinstance(expression,Lista):
        types=[infer(e) for e in expression.elementos]
        if not types or any(t!=types[0] for t in types):
            raise TypeCheckError('Tensor literals must be nonempty and rectangular')
        return NumericType((len(types),*types[0].shape))
    if isinstance(expression,Binario):
        arguments=[infer(e)
                   for e in (expression.esquerda,expression.direita)]
        if expression.operador=='^':
            _literal_nat(expression.direita,20)
        return infer_operation(expression.operador,arguments)
    if isinstance(expression,Chamada):
        if expression.funcao in ('zeros','identidade'):
            dimensions=[]
            for argument in expression.argumentos:
                dimensions.append(_literal_nat(argument,2048))
            arities=(1,) if expression.funcao=='identidade' else (1,2)
            if len(dimensions) not in arities:raise TypeCheckError('Wrong tensor constructor arity')
            if expression.funcao=='identidade':dimensions*=2
            return NumericType(tuple(dimensions))
        if expression.funcao not in ('relu','soma','transposta','dot'):
            raise TypeCheckError('Unknown numeric function: '+expression.funcao)
        arguments=[infer(e) for e in expression.argumentos]
        return infer_operation(expression.funcao,arguments)
    raise TypeCheckError('Unsupported numeric expression')


def infer_expression(expression,context:Mapping[str,NumericType],*,proof_variables=False):
    return _infer_expression(expression,context,proof_variables,[12000],0)


@dataclass(frozen=True)
class ProgramTypes:
    symbols: Mapping[str,NumericType]
    parameters: frozenset[str]
    losses: frozenset[str]
    theorems: frozenset[str]

    def __post_init__(self):
        object.__setattr__(self,'symbols',MappingProxyType(dict(self.symbols)))

    def to_dict(self):
        return {'format':'omega-inferred-types-1','symbols':{name:t.to_dict() for name,t in sorted(self.symbols.items())},
                'parameters':sorted(self.parameters),'losses':sorted(self.losses),'theorems':sorted(self.theorems)}


def infer_program(source):
    symbols={};parameters=set();losses=set();theorems=set()
    if not isinstance(source,str) or len(source)>256*1024:raise TypeCheckError('Source size budget exceeded')
    try:commands=_TypeParser(source).programa()
    except RecursionError:raise TypeCheckError('Parser depth budget exceeded') from None
    except ValueError:raise TypeCheckError('Literal outside parser bounds') from None
    for command in commands:
        kind=command.tipo;name=command.nome
        if kind in ('parametro','parametro_tensor','perda','tensor','vetor','matriz'):
            if name in symbols or name in theorems:raise TypeCheckError('Redeclared identifier: '+name)
            inferred=infer_expression(command.expressao,symbols)
            rank={'parametro':0,'perda':0,'vetor':1,'matriz':2}.get(kind)
            if kind=='parametro_tensor':rank=1 if command.parametro=='vetor' else 2
            if rank is not None and len(inferred.shape)!=rank:raise TypeCheckError('Declaration has the wrong tensor rank: '+name)
            symbols[name]=inferred
            if kind in ('parametro','parametro_tensor'):parameters.add(name)
            if kind=='perda':losses.add(name)
        elif kind in ('gradiente','gradientes','passo','passo_livre','passo_ruidoso','reescrever'):
            if name not in losses:raise TypeCheckError('Loss required: '+name)
            if kind in ('gradiente','passo','passo_livre','passo_ruidoso') and command.parametro not in parameters:
                raise TypeCheckError('Parameter required: '+command.parametro)
            if kind.startswith('passo') and not infer_expression(command.taxa,symbols).scalar:
                raise TypeCheckError('Learning rate must be scalar')
            if kind=='passo_ruidoso' and (type(command.semente) is not int or not 0<=command.semente<2**32):
                raise TypeCheckError('Seed must be a 32-bit unsigned integer')
            if kind=='reescrever' and not infer_expression(command.expressao,symbols).scalar:
                raise TypeCheckError('Rewritten loss must be scalar')
        elif kind in ('provar','teorema'):
            left=infer_expression(command.expressao,symbols,proof_variables=True)
            right=infer_expression(command.direita,symbols,proof_variables=True)
            if left!=right:raise TypeCheckError('Identity has operands of different types')
            if kind=='teorema':
                if name in symbols or name in theorems:raise TypeCheckError('Redeclared theorem: '+name)
                theorems.add(name)
        elif kind=='verificar':
            if name not in theorems:raise TypeCheckError('Unknown theorem: '+name)
        elif kind=='mostrar':
            if name not in symbols and name not in theorems:raise TypeCheckError('Unknown output: '+name)
        else:raise TypeCheckError('Unknown numeric statement: '+kind)
    return ProgramTypes(dict(symbols),frozenset(parameters),frozenset(losses),frozenset(theorems))
