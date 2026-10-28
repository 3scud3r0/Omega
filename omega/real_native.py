"""Reusable C/GMP inference binaries from the self-hosted procedural compiler.

Two audited GMP intrinsic adapters replace explicit compiler-emitted stubs.
The rational oracle and the Lean real certificate check each admitted execution;
the C toolchain and the small intrinsic implementation remain in the trust base.
"""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import tempfile

from .certified_graph import validate, bounds_contract, _q
from .real_graph import execute
from omega_selfhost.proof_protocol import encode


def program(graph, input_bounds, *, trace_values=False):
    validate(graph)
    bounds=bounds_contract(input_bounds,graph['inputs'])
    def q(value):
        value=Q(value);return f'({value.numerator}/{value.denominator})'
    lines=['funcao omega_exp(x){fail("unlinked exp intrinsic");retornar 0;}',
           'funcao omega_rsqrt(x){fail("unlinked rsqrt intrinsic");retornar 0;}',
           'funcao infer(inputs){',f'se(len(inputs)!={graph["inputs"]}){{fail("input shape mismatch");}}']
    for i,(a,b) in enumerate(bounds):
        lines += [f'var x{i}=number(inputs[{i}]);',f'se(x{i}<{q(a)} || x{i}>{q(b)}){{fail("input outside certified domain");}}']
    for i,node in enumerate(graph['nodes'],graph['inputs']):
        op=node['op']
        if op=='affine':expr=q(node['bias'])+''.join(f'+{q(w)}*x{r}' for r,w in node['terms'])
        elif op=='relu':
            ref=node['input'];lines.append(f'var x{i}=0;se(x{ref}>0){{x{i}=x{ref};}}');continue
        elif op=='square':expr=f'x{node["input"]}*x{node["input"]}'
        elif op in ('mul','div'):
            if op=='div':lines.append(f'se(x{node["right"]}<=0){{fail("nonpositive denominator");}}')
            expr=f'x{node["left"]}{"*" if op=="mul" else "/"}x{node["right"]}'
        else:expr=f'omega_{op}(x{node["input"]})'
        lines.append(f'var x{i}={expr};')
    result='['+','.join(f'text(x{i})' for i in graph['outputs'])+']'
    if trace_values:
        lines += ['var trace=obj();put(trace,"outputs",'+result+');put(trace,"values",['+','.join(f'text(x{i})' for i in range(graph['inputs']+len(graph['nodes'])))+']);retornar trace;']
    else:lines.append('retornar '+result+';')
    lines += ['}',
              'funcao principal(){se(argc()!=2){fail("expected input JSON path");}var inputs=parsejson(read(arg(1)));',
              'print(json(infer(inputs)));retornar 0;}']
    return '\n'.join(lines)+'\n'


def build_runtime(graph, directory, input_bounds, *, static=True, trace_values=False):
    from omega_selfhost.driver import compiler,cc,PACKAGE
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    validate(graph)
    root=Path(directory).absolute()
    source=root/'model.omega';c=root/'model.c';binary=root/'model'
    if any(p.exists() for p in (source,c,binary)):raise ValueError('Native destinations already exist')
    root.mkdir(parents=True,exist_ok=True);source.write_text(program(graph,input_bounds,trace_values=trace_values))
    run([compiler(),source,c],readonly=[source],writable=[root],budget=COMPILER_BUDGET,check=True)
    text=c.read_text();bits=graph.get('precision_bits',32)
    start=text.index('static V fn_omega_exp(V v_x){')
    end=text.index('static V fn_infer(V v_inputs){',start)
    expected=text[start:end]
    if expected.count('static V fn_omega_exp(')!=1 or expected.count('static V fn_omega_rsqrt(')!=1:
        raise ValueError('Unknown intrinsic stub layout from native compiler')
    adapters=[]
    for name in ('exp','rsqrt'):
        adapters.append(f'''static V fn_omega_{name}(V x){{
 if(x->kind!=0)o_die("numeric intrinsic argument required");
 V result=o_new(0);o_qinit(result);
 if(omega_rational_{name}(result->q,x->q,{bits}))o_die("transcendental domain or precision budget exceeded");
 return result;
}}\n''')
    text=text[:start]+''.join(adapters)+text[end:]
    text=text.replace('#include "runtime.h"','#include "runtime.h"\n#include "certified_transcendental.h"',1)
    c.write_text(text);cc(c,binary,static=static)
    provenance={'format':'omega-real-native-1','graph_sha256':hashlib.sha256(encode(graph)).hexdigest(),
                'compiler_sha256':hashlib.sha256(Path(compiler()).read_bytes()).hexdigest(),
                'intrinsics_sha256':hashlib.sha256((PACKAGE/'certified_transcendental.h').read_bytes()).hexdigest(),
                'runtime_sha256':hashlib.sha256((PACKAGE/'runtime.h').read_bytes()).hexdigest(),
                'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,c,binary)},
                'input_bounds':[[str(a),str(b)] for a,b in bounds_contract(input_bounds,graph['inputs'])],
                'static':static,'trace_values':trace_values}
    (root/'model.build.json').write_bytes(encode(provenance))
    return provenance


def run_runtime(graph, binary, inputs):
    from omega_platform.sandbox import run
    binary=Path(binary).absolute();validate(graph)
    if len(inputs)!=graph['inputs']:raise ValueError('Static input shape mismatch')
    inputs=[str(_q(x)) for x in inputs]
    with tempfile.TemporaryDirectory(prefix='omega-real-input-') as temporary:
        path=Path(temporary)/'inputs.json';path.write_bytes(encode(inputs))
        outcome=run([binary,path],readonly=[path],check=True)
    observed=json.loads(outcome.stdout)
    values=execute(graph,inputs);expected=[str(values[i]) for i in graph['outputs']]
    native_trace=None
    if type(observed) is dict:
        if set(observed)!={'outputs','values'} or observed['values']!=list(map(str,values)):raise ValueError('Changed native intermediate trace')
        native_trace=observed['values'];observed=observed['outputs']
    if observed!=expected:raise ValueError('Native transcendental execution differs from rational oracle')
    return observed,{'valid':True,'checker':'independent exact rational oracle replay',
                     **({'native_trace':native_trace} if native_trace is not None else {}),
                     'outputs_sha256':hashlib.sha256(encode(observed)).hexdigest(),
                     'scope':'observed native output equality; real semantics are checked separately by Lean'}


def infer_certified(graph, binary, inputs, *, expected_binary_sha256, input_bounds,
                    output_bounds, max_error, signing_key, nonce, context):
    """Issue a new request-bound certificate using an existing inference binary."""
    from .transformer_certificate import issue_real
    binary=Path(binary)
    if binary.is_symlink() or binary.stat().st_size>64*1024**2:
        raise ValueError('Bounded regular inference binary required')
    captured=binary.read_bytes()
    if hashlib.sha256(captured).hexdigest()!=expected_binary_sha256:
        raise ValueError('Changed inference binary')
    with tempfile.TemporaryDirectory(prefix='omega-pinned-inference-') as temporary:
        pinned=Path(temporary)/'model';pinned.write_bytes(captured);pinned.chmod(0o500)
        observed,admission=run_runtime(graph,pinned,inputs)
    certificate=issue_real(graph,inputs,input_bounds=input_bounds,output_bounds=output_bounds,
                           max_error=max_error,signing_key=signing_key,nonce=nonce,context=context)
    if observed!=certificate['payload']['statement']['outputs']:
        raise ValueError('Certificate does not bind the observed native output')
    payload={'format':'omega-native-pci-1','binary_sha256':expected_binary_sha256,
             'certificate_sha256':hashlib.sha256(encode(certificate)).hexdigest(),'outputs':observed}
    return {'payload':payload,'certificate':certificate,'signature':signing_key.sign(encode(payload)).hex(),
            'native_admission':admission}


def verify_inference(receipt, *, public_key, expected_binary_sha256, **expected):
    from .transformer_certificate import verify_real
    if type(receipt) is not dict or set(receipt)!={'payload','certificate','signature','native_admission'}:
        raise ValueError('Unknown native inference receipt')
    payload=receipt['payload']
    public_key.verify(bytes.fromhex(receipt['signature']),encode(payload))
    if type(payload) is not dict or set(payload)!={'format','binary_sha256','certificate_sha256','outputs'} or payload['format']!='omega-native-pci-1':
        raise ValueError('Unknown native inference payload')
    if payload['binary_sha256']!=expected_binary_sha256 or payload['certificate_sha256']!=hashlib.sha256(encode(receipt['certificate'])).hexdigest():
        raise ValueError('Unrelated binary or certificate')
    result=verify_real(receipt['certificate'],public_key=public_key,**expected)
    if result['outputs']!=payload['outputs']:raise ValueError('Changed native observations')
    return {**result,'binary_sha256':expected_binary_sha256}
