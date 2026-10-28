"""Real-analysis certificates, transformer lowering and control measurements."""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import copy
import json
from pathlib import Path
import subprocess

import pytest
import torch

from omega.certify import trace, export
from omega.certified_graph import evaluate
from omega.real_graph import analyze, certify
from omega.transcendental import exp_enclosure, rsqrt_enclosure, ProofBuilder
from omega.transformer import CertifiedSelfAttention, CertifiedSwiGLU


def attention(causal=True):
    model=CertifiedSelfAttention(2,1,max_sequence_length=2,causal=causal,bias=False)
    with torch.no_grad():
        for layer in (model.q_proj,model.k_proj,model.v_proj,model.out_proj):
            layer.weight.copy_(torch.eye(2)*0.25)
    return model.eval()


@pytest.mark.parametrize('value',['-32','-2','-1/3','0','1/7','1','8','32'])
def test_exp_rational_enclosure_against_independent_decimal(value):
    a,b,_=exp_enclosure(value,bits=32)
    assert a>0 and b-a<=Q(1,2**32)
    with localcontext() as ctx:
        ctx.prec=100
        x=Q(value);actual=(Decimal(x.numerator)/Decimal(x.denominator)).exp()
        assert Decimal(a.numerator)/Decimal(a.denominator)<=actual<=Decimal(b.numerator)/Decimal(b.denominator)


@pytest.mark.parametrize('low,high',[('1/1000000','1/1000'),('1','2'),('4','4')])
def test_inverse_sqrt_enclosure(low,high):
    a,b,(s,t)=rsqrt_enclosure(low,high,bits=32)
    assert s>0 and s*s<=Q(low) and t*t>=Q(high)
    with localcontext() as ctx:
        ctx.prec=100
        for value in (Q(low),Q(high)):
            actual=1/(Decimal(value.numerator)/Decimal(value.denominator)).sqrt()
            assert Decimal(a.numerator)/Decimal(a.denominator)<=actual<=Decimal(b.numerator)/Decimal(b.denominator)


@pytest.mark.parametrize('call',[lambda:exp_enclosure('33'),lambda:exp_enclosure(True),lambda:exp_enclosure('1',bits=True),
                                 lambda:rsqrt_enclosure('0'),lambda:rsqrt_enclosure('-1'),lambda:rsqrt_enclosure('2','1')])
def test_transcendental_contracts_reject_invalid_domains(call):
    with pytest.raises(ValueError):call()


@pytest.mark.lean
def test_endpoint_analytic_proofs_and_kernel_rejects_tampered_endpoint():
    from omega.certified_proof import check
    builder=ProofBuilder()
    for value in ('0','1/2','-1','2'):
        builder.exp_endpoint(Q(value),bits=24)
    assert check(builder.finish(),builder.names)['theorems']
    false='import Omega.Transcendental\ntheorem false_exp : (3:ℝ) ≤ Real.exp 0 := by norm_num\n#print axioms false_exp\n'
    with pytest.raises(ValueError,match='Lean rejected'):
        check(false,['false_exp'])


@pytest.mark.lean
def test_softmax_argmax_without_exp_evaluation_outside_approximation_domain():
    from omega.transcendental import certify_softmax_argmax
    result=certify_softmax_argmax(['1000','-1000','1/3'],max_denominator=100)
    assert result['argmax']==0 and len(result['softmax_admission']['theorems'])==2


@pytest.mark.parametrize('layer,x',[(torch.nn.Softmax(-1),[0.,1.]),(torch.nn.RMSNorm(2,eps=0.01),[1.,2.]),(torch.nn.SiLU(),[-1.,1.])])
def test_fx_transcendentals_agree_with_fp64_reference(layer,x):
    sample=torch.tensor(x,dtype=torch.float64)
    graph=trace(layer.double(),sample)
    exact_inputs=[Q(float(v)) for v in sample]
    result=evaluate(graph,exact_inputs)
    reference=layer(sample).detach().tolist()
    assert [float(v) for v in result]==pytest.approx(reference,abs=1e-8)


@pytest.mark.lean
@pytest.mark.parametrize('layer,x,domain,outputs',[
    (torch.nn.Softmax(-1),[0.,1.],[[-1,1],[-1,1]],[[0,1],[0,1]]),
    (torch.nn.RMSNorm(2,eps=0.01),[1.,2.],[[-2,2],[-2,2]],[[-30,30],[-30,30]])])
def test_universal_domain_and_concrete_error_are_proved(layer,x,domain,outputs):
    graph=trace(layer,torch.tensor(x))
    result=certify(graph,list(map(Q,x)),domain,outputs,'1/1000000')
    assert 'OmegaApprox.domain_bounds' in result['admission']['theorems']
    assert 'OmegaApprox.execution_error' in result['admission']['theorems']
    assert all(Q(e)<=Q('1/1000000') for e in result['error_bounds'])


def test_error_budget_and_positive_denominator_gate_fail_closed():
    sample=torch.tensor([1.,2.]);graph=trace(torch.nn.RMSNorm(2,eps=0.01),sample)
    with pytest.raises(ValueError,match='exceeds requested'):
        certify(graph,[1,2],[[1,1],[2,2]],[[-30,30],[-30,30]],'1/100000000000000000000000')
    with pytest.raises(ValueError,match='epsilon'):
        trace(torch.nn.RMSNorm(2,eps=0),sample)
    bad={'inputs':1,'nodes':[{'op':'div','left':0,'right':0}],'outputs':[1]}
    with pytest.raises(ValueError,match='positive'):
        analyze(bad,[[-1,1]])


@pytest.mark.parametrize('causal',[False,True])
def test_self_attention_qkv_scaling_heads_and_causal_dependencies(causal):
    model=attention(causal)
    sample=torch.tensor([[0.1,0.2],[0.3,0.4]],dtype=torch.float64)
    model=model.double()
    graph=trace(model,sample)
    actual=evaluate(graph,[Q(float(v)) for v in sample.reshape(-1)])
    assert [float(v) for v in actual]==pytest.approx(model(sample).detach().reshape(-1).tolist(),abs=1e-8)
    assert graph['input_shape']==[2,2] and graph['output_shape']==[2,2]
    if causal:
        mutated=sample.clone();mutated[1]=torch.tensor([2.,-2.])
        after=evaluate(graph,[Q(float(v)) for v in mutated.reshape(-1)])
        assert actual[:2]==after[:2]
    with pytest.raises(ValueError,match='maximum'):
        trace(model,torch.zeros(3,2))


def test_multiple_heads_and_standard_mha_adapter():
    sample=torch.tensor([[0.1,0.2],[0.3,0.4]])
    model=CertifiedSelfAttention(2,2,max_sequence_length=2,bias=False)
    with torch.no_grad():
        for p in (model.q_proj,model.k_proj,model.v_proj,model.out_proj):p.weight.copy_(torch.eye(2)*0.25)
    actual=evaluate(trace(model,sample),[Q(float(v)) for v in sample.reshape(-1)])
    assert [float(v) for v in actual]==pytest.approx(model(sample).detach().reshape(-1).tolist(),abs=1e-7)
    class Standard(torch.nn.Module):
        def __init__(self):
            super().__init__();self.attention=torch.nn.MultiheadAttention(2,1,batch_first=True,bias=False)
            with torch.no_grad():
                self.attention.in_proj_weight.copy_(torch.eye(2).repeat(3,1)*0.25)
                self.attention.out_proj.weight.copy_(torch.eye(2)*0.25)
        def forward(self,x):return self.attention(x,x,x,need_weights=False)[0]
    standard=Standard().eval()
    result=evaluate(trace(standard,sample),[Q(float(v)) for v in sample.reshape(-1)])
    assert [float(v) for v in result]==pytest.approx(standard(sample).detach().reshape(-1).tolist(),abs=1e-7)
    batched=sample.unsqueeze(0).repeat(2,1,1)
    for candidate in (model,standard):
        graph=trace(candidate,batched)
        result=evaluate(graph,[Q(float(v)) for v in batched.reshape(-1)])
        assert graph['input_shape']==[2,2,2]
        assert [float(v) for v in result]==pytest.approx(candidate(batched).detach().reshape(-1).tolist(),abs=1e-7)


@pytest.mark.lean
def test_micro_transformer_native_signed_export_and_audit(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.exceptions import InvalidSignature
    from omega.pci import verify_export,digest
    model=torch.nn.Sequential(torch.nn.RMSNorm(2,eps=0.01),attention(True))
    sample=torch.tensor([[0.25,0.5],[0.75,1.]])
    key=Ed25519PrivateKey.generate()
    result=export(model,sample,tmp_path/'micro',input_bounds=[[-1,1]]*4,output_bounds=[[-30,30]]*4,
                  signing_key=key,nonce='micro-1',max_error='1/100000',precision_bits=32)
    cert=result['certificate'];statement=cert['payload']['statement']
    kwargs=dict(public_key=key.public_key(),expected_graph_sha256=digest(statement['graph']),
                expected_inputs=[Q(float(v)) for v in sample.reshape(-1)],expected_nonce='micro-1',expected_context='critical-system',
                expected_input_bounds=[[-1,1]]*4,expected_output_bounds=[[-30,30]]*4,expected_max_error='1/100000')
    assert verify_export(result['directory'],**kwargs)['valid']
    assert 'statically linked' in subprocess.check_output(['file',str(tmp_path/'micro/model')],text=True)
    from omega.real_native import run_runtime
    new_outputs,replay=run_runtime(statement['graph'],tmp_path/'micro/model',['1/2','1/4','1','3/4'])
    assert replay['valid'] and len(new_outputs)==4
    with pytest.raises(ValueError,match='contract|proof'):
        verify_export(result['directory'],**{**kwargs,'expected_max_error':'1/1000'})
    changed=copy.deepcopy(cert);changed['payload']['statement']['max_error'][0]='1'
    from omega.pci import verify
    with pytest.raises(InvalidSignature):verify(changed,**kwargs)


def test_swiglu_and_explicit_approximation_opt_in(tmp_path):
    model=CertifiedSwiGLU(2,2,bias=False)
    with torch.no_grad():
        for p in (model.gate,model.value,model.out):p.weight.copy_(torch.eye(2)*0.25)
    sample=torch.tensor([0.25,0.5])
    actual=evaluate(trace(model,sample),[Q(float(v)) for v in sample])
    assert [float(v) for v in actual]==pytest.approx(model(sample).detach().tolist(),abs=1e-8)
    with pytest.raises(ValueError,match='max_error'):
        export(model,sample,tmp_path/'refused',input_bounds=[[-1,1]]*2,output_bounds=[[-1,1]]*2,signing_key=None,nonce='refused')
    class Dynamic(torch.nn.Module):
        def forward(self,x):
            if x.sum()>0:return x
            return -x
    with pytest.raises(ValueError,match='control flow'):
        trace(Dynamic(),sample)
    class Functional(torch.nn.Module):
        def forward(self,x):return torch.nn.functional.softmax(torch.nn.functional.silu(x),dim=-1)
    functional=Functional()
    result=evaluate(trace(functional,sample),[Q(float(v)) for v in sample])
    assert [float(v) for v in result]==pytest.approx(functional(sample).detach().tolist(),abs=1e-7)


def test_native_continued_fraction_matches_python_and_aliases(tmp_path):
    from omega_selfhost.driver import PACKAGE
    cases=[(Q(n,d),limit) for n in (-355,-1,0,1,355) for d in (2,7,113) for limit in (1,3,100)]
    literals=','.join('"'+str(v)+'"' for v,_ in cases)
    limits=','.join(str(limit) for _,limit in cases)
    source=tmp_path/'check.c'
    source.write_text('#include <stdio.h>\n#include <stdlib.h>\n#include "rational_pruning.h"\n'
                      'int main(void){const char* inputs[]={'+literals+'};unsigned long limits[]={'+limits+'};'
                      'mpq_t q;mpq_init(q);for(unsigned i=0;i<sizeof(limits)/sizeof(limits[0]);i++){mpq_set_str(q,inputs[i],10);mpq_canonicalize(q);'
                      'if(omega_mpq_limit_denominator(q,q,limits[i]))return 1;char*s=mpq_get_str(NULL,10,q);puts(s);free(s);}mpq_clear(q);return 0;}')
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(PACKAGE),str(source),'-lgmp','-o',str(tmp_path/'check')],check=True)
    result=subprocess.check_output([str(tmp_path/'check')],text=True).splitlines()
    assert list(map(Q,result))==[value.limit_denominator(limit) for value,limit in cases]


def test_reusable_native_transcendentals_match_oracle_for_new_values(tmp_path):
    from omega.real_native import build_runtime,run_runtime
    from omega_platform.sandbox import ExecutionFailure
    graph={'inputs':2,'nodes':[{'op':'exp','input':0},{'op':'rsqrt','input':1}],
           'outputs':[2,3],'precision_bits':32}
    root=tmp_path/'runtime'
    build_runtime(graph,root,[[-32,32],['1/1000',4]])
    for inputs in [('-32','1/1000'),('-2','1/1000'),('-1','1/2'),('0','1'),('1/2','2'),('2','4'),('32','4')]:
        observed,admission=run_runtime(graph,root/'model',inputs)
        assert admission['valid'] and list(map(Q,observed))==evaluate(graph,list(map(Q,inputs)))
    with pytest.raises(ExecutionFailure,match='outside certified domain'):
        run_runtime(graph,root/'model',[33,1])


@pytest.mark.lean
def test_new_input_receipt_binds_pinned_native_bytes_and_request(tmp_path):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from omega.real_native import build_runtime,infer_certified,verify_inference
    from omega.pci import digest
    graph=trace(torch.nn.Softmax(-1),torch.tensor([0.,1.]))
    root=tmp_path/'inference';build_runtime(graph,root,[[0,1],[0,1]])
    key=Ed25519PrivateKey.generate();binary=root/'model'
    sha=hashlib.sha256(binary.read_bytes()).hexdigest()
    receipt=infer_certified(graph,binary,['1/2','1/4'],expected_binary_sha256=sha,
                            input_bounds=[[0,1],[0,1]],output_bounds=[[0,1],[0,1]],max_error='1/1000000',
                            signing_key=key,nonce='new-input',context='test')
    expected=dict(expected_graph_sha256=digest(graph),expected_inputs=['1/2','1/4'],
                  expected_input_bounds=[[0,1],[0,1]],expected_output_bounds=[[0,1],[0,1]],
                  expected_max_error='1/1000000',expected_nonce='new-input',expected_context='test')
    assert verify_inference(receipt,public_key=key.public_key(),expected_binary_sha256=sha,**expected)['valid']
    with pytest.raises(ValueError,match='Changed inference binary'):
        infer_certified(graph,binary,[0,1],expected_binary_sha256='0'*64,input_bounds=[[0,1],[0,1]],output_bounds=[[0,1],[0,1]],
                        max_error='1/1000000',signing_key=key,nonce='bad',context='test')


@pytest.mark.lean
def test_control_benchmark_three_measured_backends_and_formal_evidence(tmp_path):
    from omega_bench.certified_control import run
    result=run(tmp_path/'control',samples=4,steps=4,repetitions=1,max_denominator=256)
    assert set(result['measurements'])=={'exact','pruned','fp32'}
    assert result['common_input_max_error']['exact']=='0'
    assert all(result['measurements'][mode]['median_controller_ns']>0 for mode in result['measurements'])
    assert all(result['measurements'][mode]['process_peak_rss_kib']>0 for mode in result['measurements'])
    assert result['proof']['theorems']
    assert result['pruned_certified_decisions']+result['pruned_refused_decisions']==4
    assert result['pruned_refused_decisions']>=1


@pytest.mark.lean
def test_complete_sequence_family_and_pinned_length_dispatch(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from omega.sequence_family import export_family,verify_family
    from omega.pci import digest
    model=torch.nn.Linear(1,1,bias=False)
    with torch.no_grad():model.weight.fill_(0.5)
    examples={n:torch.ones(n,1) for n in (1,2)}
    key=Ed25519PrivateKey.generate()
    root=tmp_path/'family'
    manifest=export_family(model,examples,root,input_bounds={n:[[-1,1]]*n for n in (1,2)},
                           output_bounds={n:[[-1,1]]*n for n in (1,2)},signing_key=key,nonce='family',max_error='1/1000')
    expected={}
    for n in (1,2):
        certificate=json.loads((root/f'length-{n}'/'certificate.json').read_text())['pci']
        expected[n]=dict(expected_graph_sha256=digest(certificate['payload']['statement']['graph']),expected_inputs=[1]*n,
                         expected_input_bounds=[[-1,1]]*n,expected_output_bounds=[[-1,1]]*n,
                         expected_nonce=f'family:{n}',expected_context=f'critical-system/length/{n}')
    assert verify_family(root,public_key=key.public_key(),expected_members=expected)['maximum_length']==2
    with pytest.raises(ValueError,match='length contract'):
        verify_family(root,public_key=key.public_key(),expected_members={1:expected[1]})
    with pytest.raises(ValueError,match='every sequence length'):
        export_family(model,{2:examples[2]},tmp_path/'bad',input_bounds={},output_bounds={},signing_key=key,nonce='bad',max_error='1/1000')
