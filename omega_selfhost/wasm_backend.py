"""Checked scalar i64 backend. Nonintegral values, overflow and division trap.

Tensor and general rational programs must use the native GMP backend.
"""
from fractions import Fraction
from omega.typed_ir import TypedIR
from omega_platform.wasm import execute
HELPERS='''
(func $add (param $a i64)(param $b i64)(result i64)(local $r i64)
 (local.set $r (i64.add (local.get $a)(local.get $b)))
 (if (i32.or (i32.and (i64.gt_s (local.get $b)(i64.const 0))(i64.lt_s (local.get $r)(local.get $a)))
             (i32.and (i64.lt_s (local.get $b)(i64.const 0))(i64.gt_s (local.get $r)(local.get $a))))(then unreachable))
 (local.get $r))
(func $sub (param $a i64)(param $b i64)(result i64)(local $r i64)
 (local.set $r (i64.sub (local.get $a)(local.get $b)))
 (if (i32.or (i32.and (i64.gt_s (local.get $b)(i64.const 0))(i64.gt_s (local.get $r)(local.get $a)))
             (i32.and (i64.lt_s (local.get $b)(i64.const 0))(i64.lt_s (local.get $r)(local.get $a))))(then unreachable))
 (local.get $r))
(func $mul (param $a i64)(param $b i64)(result i64)(local $r i64)
 (if (i64.eqz (local.get $a))(then (return (i64.const 0))))
 (if (i32.and (i64.eq (local.get $a)(i64.const -1))(i64.eq (local.get $b)(i64.const -9223372036854775808)))(then unreachable))
 (local.set $r (i64.mul (local.get $a)(local.get $b)))
 (if (i64.ne (i64.div_s (local.get $r)(local.get $a))(local.get $b))(then unreachable)) (local.get $r))
(func $div (param $a i64)(param $b i64)(result i64)
 (if (i64.eqz (local.get $b))(then unreachable))
 (if (i64.ne (i64.rem_s (local.get $a)(local.get $b))(i64.const 0))(then unreachable))
 (i64.div_s (local.get $a)(local.get $b)))
'''
def compile_ir(ir,symbol):
    if type(ir) is not TypedIR:raise TypeError('Validated TypedIR required')
    graph=ir.legacy()
    if symbol not in graph['simbolos']:raise ValueError('Unknown output symbol')
    parameters={p['nome']:i for i,p in enumerate(graph['parametros'])}
    if len(parameters)>64:raise ValueError('WASM parameter budget exceeded')
    lines=['(module',HELPERS,'(func (export "evaluate") '+''.join(f'(param $p{i} i64)' for i in range(len(parameters)))+'(result i64)']
    lines.extend(f'(local $n{i} i64)' for i in range(len(graph['nos'])))
    for i,node in enumerate(graph['nos']):
        if node['forma']:raise ValueError('WASM backend supports scalar i64 only')
        op=node['op'];args=[f'(local.get $n{j})' for j in node['args']]
        if op=='num':
            q=Fraction(node['v'])
            if q.denominator!=1 or not -(2**63)<=q<2**63:raise ValueError('Non-i64 literal')
            expression=f'(i64.const {q.numerator})'
        elif op=='param':expression=f'(local.get $p{parameters[node["nome"]]})'
        elif op in ('+','-','*','/'):expression='(call $'+{'+':'add','-':'sub','*':'mul','/':'div'}[op]+' '+' '.join(args)+')'
        elif op=='neg':expression=f'(call $sub (i64.const 0) {args[0]})'
        elif op=='soma':expression=args[0]
        elif op=='relu':expression=f'(if (result i64) (i64.gt_s {args[0]} (i64.const 0)) (then {args[0]}) (else (i64.const 0)))'
        else:raise ValueError('Operator outside checked WASM subset: '+op)
        lines.append(f'(local.set $n{i} {expression})')
    lines.append(f'(local.get $n{graph["simbolos"][symbol]})))')
    return '\n'.join(lines),tuple(parameters)
def run(ir,symbol,state,**limits):
    wat,names=compile_ir(ir,symbol)
    if set(state)!=set(names):raise ValueError('WASM state mismatch')
    return execute(wat,tuple(state[name] for name in names),**limits)
