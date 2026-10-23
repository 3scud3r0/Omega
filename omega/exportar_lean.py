"""Exporta provas Lean 4 de aritmética racional CONCRETA dos estados.

Os fatos de atualização numérica são verificáveis por Lean/Mathlib. Não há
um teorema Lean demonstrando a correção global do motor de retropropagação.
"""
from fractions import Fraction
from .sintaxe import ErroOmega


def lean_q(val):
    x=Fraction(val)
    return f'(({x.numerator} : ℚ) / {x.denominator})'


def folhas(v):
    if isinstance(v,list):
        for x in v:yield from folhas(x)
    else:yield v


def gerar_lean(certificados):
    lines=['import Mathlib', '', '-- Ômega 1.0: teoremas sobre operações racionais CONCRETAS.',
           '-- A tradução NÃO formaliza a correção dos algoritmos de VJP.',
           '-- Execute `lake env lean` em um projeto Lean 4 com Mathlib.', '',
           'namespace OmegaExport', '']
    count=0
    for i,c in enumerate(certificados):
        if c.get('tipo')!='passo_ir':continue
        before=lean_q(c['perda_antes']); after=lean_q(c['perda_depois'])
        target=c['alvo']; rate=lean_q(c['taxa'])
        old=list(folhas(c['estado_antes'][target]))
        new=list(folhas(c['estado_depois'][target]))
        grad=list(folhas(c['gradientes'][target]))
        if len(old)>20000:raise ErroOmega('Exportação limitada a 20.000 coordenadas por passo')
        for j,(a,b,g) in enumerate(zip(old,new,grad)):
            anterior=lean_q(a);atual=lean_q(b);gradient=lean_q(g)
            if c['politica']=='passo_ruidoso':
                noise=lean_q(Fraction(b)-Fraction(a)+Fraction(c['taxa'])*Fraction(g))
                eq=f'{atual} = {anterior} - {rate} * {gradient} + {noise}'
            else:
                eq=f'{atual} = {anterior} - {rate} * {gradient}'
            lines.append(f'theorem coordenada_{i}_{j} : {eq} := by norm_num')
        lines.append(f'theorem perda_registrada_{i} : {before} = {before} := by norm_num')
        if c['politica']=='passo':
            lines.append(f'theorem monotonia_{i} : {after} ≤ {before} := by norm_num')
        lines.append('')
        count+=1
    if not count:raise ErroOmega('Nenhum certificado de atualização para exportar')
    lines.extend(['end OmegaExport',''])
    return '\n'.join(lines)
