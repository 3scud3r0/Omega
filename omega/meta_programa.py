"""Especificação declarativa do código Ômega de priorização de hipóteses.

Separada de nucleo_meta: o gerador constrói e executa o programa .omega;
o auditor valida a forma exata e o efeito em TODAS as 625 entradas.
"""
from __future__ import annotations


def fonte_politica(p):
    if len(p)!=5 or any(type(v) is not int or v not in (-1,0,1) for v in p):
        raise ValueError('Política fora do espaço permitido')
    x,y,z,t,u=p
    norma='+'.join(f'(relu({n}) + relu(-{n}))' for n in 'abcd')
    return ("# Politica de busca auto-sintetizada pela linguagem Omega.\n"
            "parametro a = 0;\nparametro b = 0;\nparametro c = 0;\nparametro d = 0;\n"
            f"tensor prioridade = ({x}) * ({norma}) + ({y}) * a + ({z}) * b + ({t}) * c + ({u}) * d;\n"
            "mostrar prioridade;\n")
