"""Recognized IR rewrite certificates; finite observations are reported separately."""
from .otimizador_v1 import validar_otimizacao
from .typed_ir import TypedIR
from omega_selfhost.driver import verify_optimization
def certify(certificate,*,require_lean=True):
    if validar_otimizacao(certificate) is not True:raise ValueError('Rewrite certificate rejected')
    result={'valid':True,'domain':'recognized local rational/tensor rewrites'}
    if require_lean:result['lean']=verify_optimization(certificate)
    return result
def differential(left,right,states,evaluate):
    if type(left) is not TypedIR or type(right) is not TypedIR:raise TypeError('Typed IR required')
    count=0
    for state in states:
        if count>=10000:raise ValueError('Differential case budget exceeded')
        a=evaluate(left,state);b=evaluate(right,state)
        if a!=b:return {'equal_on_cases':False,'counterexample':state,'checked':count+1,'universal':False}
        count+=1
    return {'equal_on_cases':True,'checked':count,'universal':False}
