"""Reproducible numerical-control benchmark; measurements never imply safety.

The plant is the explicitly declared linearized inverted pendulum with exact
Euler updates. Common inputs isolate inference rounding; separate rollouts
measure controller-induced divergence using the same exact plant arithmetic.
"""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys

from omega.certified_proof import check, rational_literal as lit
from omega_selfhost.proof_protocol import encode


def controller():
    import torch
    from omega.certify import trace
    model = torch.nn.Sequential(torch.nn.Linear(2,4,bias=False),torch.nn.ReLU(),torch.nn.Linear(4,2,bias=False))
    with torch.no_grad():
        model[0].weight.copy_(torch.tensor([[1.,0.],[-1.,0.],[0.,1.],[0.,-1.]]))
        model[2].weight.copy_(torch.tensor([[-50/3,50/3,-50/7,50/7],[50/3,-50/3,50/7,-50/7]]))
    model.eval()
    return model, trace(model,torch.zeros(2))


def _source(graph):
    def q(x):
        x=Q(x);return f'({x.numerator}/{x.denominator})'
    lines=['funcao control(x) {', 'var x0=number(x[0]);var x1=number(x[1]);']
    for i,node in enumerate(graph['nodes'],graph['inputs']):
        if node['op']=='affine':
            expr=q(node['bias'])+''.join(f'+{q(w)}*x{r}' for r,w in node['terms'])
        else:
            ref=node['input'];expr=f'x{ref}'
            lines.append(f'var x{i}=0;se(x{ref}>0){{x{i}=x{ref};}}');continue
        lines.append(f'var x{i}={expr};')
    lines += ['retornar ['+','.join(f'x{i}' for i in graph['outputs'])+'];','}',
              'funcao principal(){var data=parsejson(read(arg(1)));var bank=[];var i=0;',
              'enquanto(i<len(data["inputs"])){var y=control(data["inputs"][i]);push(bank,[text(y[0]),text(y[1])]);i=i+1;}',
              'var theta=number(data["initial"][0]);var velocity=number(data["initial"][1]);var trajectory=[];i=0;',
              'enquanto(i<data["steps"]){var y=control([text(theta),text(velocity)]);var u=y[0];push(trajectory,[text(theta),text(velocity),text(u)]);',
              'var next_theta=theta+(1/50)*velocity;velocity=velocity+(1/50)*(10*theta+u);theta=next_theta;i=i+1;}',
              'var report=obj();put(report,"bank",bank);put(report,"trajectory",trajectory);print(json(report));retornar 0;}']
    return '\n'.join(lines)+'\n'


def _native(source, destination, *, limit=None):
    from omega_selfhost.driver import compiler, cc, PACKAGE
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    destination=Path(destination)
    c=destination.with_suffix('.c')
    run([compiler(),source,c],readonly=[source],writable=[destination.parent],budget=COMPILER_BUDGET,check=True)
    text=c.read_text()
    # Instrument the generated controller only. The plant remains exact in
    # both native modes, so plant rounding cannot masquerade as controller drift.
    start=text.index('static V fn_control(V v_x){')
    end=text.index('static V fn_principal(',start)
    body=text[start:end]
    for op in ('add','sub','mul','div','neg'):
        body=body.replace(f'o_{op}(',f'bench_{op}(')
    body=body.replace('static V fn_control(', 'static V bench_control_impl(')
    helper='''
#include "rational_pruning.h"
#include <sys/resource.h>
static unsigned long long control_ns=0, control_calls=0;
static size_t temporary_bits=0, retained_bits=0;
static unsigned long long ns_now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (unsigned long long)t.tv_sec*1000000000ULL+t.tv_nsec;}
static V bench_round(V x){if(x->kind!=0)return x;
 size_t n=mpz_sizeinbase(mpq_numref(x->q),2),d=mpz_sizeinbase(mpq_denref(x->q),2);size_t bits=n>d?n:d;if(bits>temporary_bits)temporary_bits=bits;
 LIMIT_ACTION
 n=mpz_sizeinbase(mpq_numref(x->q),2);d=mpz_sizeinbase(mpq_denref(x->q),2);bits=n>d?n:d;if(bits>retained_bits)retained_bits=bits;return x;}
static V bench_add(V a,V b){return bench_round(o_add(a,b));}
static V bench_sub(V a,V b){return bench_round(o_sub(a,b));}
static V bench_mul(V a,V b){return bench_round(o_mul(a,b));}
static V bench_div(V a,V b){return bench_round(o_div(a,b));}
static V bench_neg(V a){return bench_round(o_neg(a));}
'''.replace('LIMIT_ACTION',f'omega_mpq_limit_denominator(x->q,x->q,{limit}UL);' if limit else '')
    wrapper='''static V fn_control(V x){unsigned long long t=ns_now();V y=bench_control_impl(x);control_ns+=ns_now()-t;control_calls++;return y;}\n'''
    text=text[:start]+body+wrapper+text[end:]
    text=text.replace('#include "runtime.h"','#include "runtime.h"\n'+helper,1)
    text=text.replace('int main(int argc,char **argv)', 'int bench_program_main(int argc,char **argv)')
    text+='''\nint main(int argc,char **argv){int rc=bench_program_main(argc,argv);struct rusage r;getrusage(RUSAGE_SELF,&r);fprintf(stderr,"OMEGA_METRICS {\\"control_ns\\":%llu,\\"calls\\":%llu,\\"peak_rss_kib\\":%ld,\\"temporary_bits\\":%zu,\\"retained_bits\\":%zu}\\n",control_ns,control_calls,r.ru_maxrss,temporary_bits,retained_bits);return rc;}\n'''
    c.write_text(text)
    cc(c,destination)


def _run(argv):
    from omega_platform.sandbox import trusted
    from omega_platform.budget import BUILD_BUDGET
    result=trusted(argv,budget=BUILD_BUDGET,check=True)
    metrics=[line for line in result.stderr.splitlines() if line.startswith('OMEGA_METRICS ')]
    if len(metrics)!=1:
        raise ValueError('Missing per-process benchmark measurements')
    return json.loads(result.stdout),json.loads(metrics[0].split(' ',1)[1])


def _proof(graph,data,exact,pruned,fp32):
    kp=-Q(graph['nodes'][-2]['terms'][0][1]);kd=-Q(graph['nodes'][-2]['terms'][2][1])
    lines=['import ProofPrelude','namespace OmegaControlBenchmark',
           f'def policy (theta velocity : ℚ) : ℚ := -{lit(kp)}*theta-{lit(kd)}*velocity',
           f'theorem relu_controller (theta velocity : ℚ) :',
           f'  -{lit(kp)} * max 0 theta + {lit(kp)} * max 0 (-theta) - {lit(kd)} * max 0 velocity + {lit(kd)} * max 0 (-velocity) = policy theta velocity := by',
           '  by_cases ht : 0 ≤ theta <;> by_cases hv : 0 ≤ velocity <;>',
           '    simp [policy, max_eq_right, max_eq_left, ht, hv, le_of_not_ge, neg_nonpos, neg_nonneg] <;> ring',
           '#print axioms relu_controller']
    names=['OmegaControlBenchmark.relu_controller']
    errors=[]; decisions=[]
    for i,(inputs,truth,p,f) in enumerate(zip(data['inputs'],exact['bank'],pruned['bank'],fp32['bank'])):
        x,y=map(Q,inputs);a=Q(truth[0]);pv,fv=Q(p[0]),Q(f[0])
        if a != -kp*x-kd*y:
            raise ValueError('Native exact controller differs from rational reference')
        pe,fe=abs(a-pv),abs(a-fv)
        lines += [f'theorem exact_{i} : policy {lit(x)} {lit(y)} = {lit(a)} := by norm_num [policy]',
                  f'#print axioms exact_{i}',
                  f'theorem errors_{i} : |{lit(a)}-{lit(pv)}| ≤ {lit(pe)} ∧ |{lit(a)}-{lit(fv)}| ≤ {lit(fe)} := by simp only [abs_le]; norm_num',
                  f'#print axioms errors_{i}']
        names += [f'OmegaControlBenchmark.exact_{i}',f'OmegaControlBenchmark.errors_{i}']
        margin=2*abs(a)
        accepted=margin>2*pe
        if accepted:
            if (a>0)!=(pv>0):raise ValueError('Admitted pruned decision changed sign')
            relation='0 <' if a>0 else ''
            claim=f'0 < {lit(pv)}' if a>0 else f'{lit(pv)} < 0'
            lines += [f'theorem decision_{i} : {claim} := by norm_num',f'#print axioms decision_{i}']
            names.append(f'OmegaControlBenchmark.decision_{i}')
        errors.append((pe,fe));decisions.append(accepted)
    lines.append('end OmegaControlBenchmark')
    source='\n'.join(lines)+'\n'
    return source,check(source,names),errors,decisions


def run(directory, *, samples=32, steps=64, repetitions=3, max_denominator=65536):
    if any(type(n) is not int for n in (samples,steps,repetitions,max_denominator)) or not 2<=samples<=256 or not 1<=steps<=256 or not 1<=repetitions<=20 or not 1<=max_denominator<=2**31:
        raise ValueError('Benchmark budgets exceeded')
    root=Path(directory).absolute();root.mkdir(parents=True,exist_ok=False)
    _,graph=controller()
    data={'inputs':[[str(Q(i-samples//2,1024)),str(Q(i%7-3,512))] for i in range(samples)],
          'initial':['1/20','0'],'steps':steps,'graph':graph,'seed':0}
    data['inputs'][0]=['0','0']  # Explicit tie: certification must abstain.
    dataset=root/'dataset.json';dataset.write_bytes(encode(data))
    source=root/'controller.omega';source.write_text(_source(graph))
    exact_binary,pruned_binary=root/'exact',root/'pruned'
    _native(source,exact_binary);_native(source,pruned_binary,limit=max_denominator)
    outcomes={};measurements={}
    for mode,argv in [('exact',[str(exact_binary),str(dataset)]),('pruned',[str(pruned_binary),str(dataset)]),
                      ('fp32',[sys.executable,'-m','omega_bench.certified_control_worker',str(dataset)])]:
        times=[];rss=[];observed=None;last=None
        # One untimed warm-up per backend; subsequent independent-process runs
        # retain process-startup RSS but time only controller calls internally.
        _run(argv)
        for _ in range(repetitions):
            result,metrics=_run(argv)
            if metrics['calls']!=samples+steps:raise ValueError('Benchmark did not execute the complete selected workload')
            if observed is not None and result!=observed:raise ValueError('Nondeterministic benchmark output')
            observed=result;last=metrics
            times.append(metrics['control_ns']/metrics['calls']);rss.append(metrics['peak_rss_kib'])
        outcomes[mode]=observed
        measurements[mode]={'median_controller_ns':statistics.median(times),'maximum_run_mean_ns':max(times),
                            'process_peak_rss_kib':max(rss),'repetitions':repetitions,
                            'temporary_bits':last.get('temporary_bits'),'retained_bits':last.get('retained_bits')}
    # Validate native arithmetic and both closed-loop histories independently.
    kp=-Q(graph['nodes'][-2]['terms'][0][1]);kd=-Q(graph['nodes'][-2]['terms'][2][1])
    for mode in ('exact','pruned','fp32'):
        theta,velocity=map(Q,data['initial'])
        for row in outcomes[mode]['trajectory']:
            a,b,u=map(Q,row)
            if (a,b)!=(theta,velocity):raise ValueError('Inconsistent rollout state transition')
            if mode=='exact' and -kp*a-kd*b!=u:raise ValueError('Exact native rollout drifted')
            theta,velocity=theta+Q(1,50)*velocity,velocity+Q(1,50)*(10*theta+u)
    proof,admission,errors,accepted=_proof(graph,data,outcomes['exact'],outcomes['pruned'],outcomes['fp32'])
    (root/'benchmark.lean').write_text(proof)
    def maximum(index):return str(max(e[index] for e in errors))
    rollout={}
    for mode in ('pruned','fp32'):
        drift=max(abs(Q(r[0])-Q(e[0])) for r,e in zip(outcomes[mode]['trajectory'],outcomes['exact']['trajectory']))
        rollout[mode]={'max_angle_divergence':str(drift)}
    report={'format':'omega-control-benchmark-1','plant':'linearized inverted pendulum; exact Euler dt=1/50, g/l=10',
            'samples':samples,'steps':steps,'max_denominator':max_denominator,'measurements':measurements,
            'common_input_max_error':{'exact':'0','pruned':maximum(0),'fp32':maximum(1)},
            'pruned_certified_decisions':sum(accepted),'pruned_refused_decisions':len(accepted)-sum(accepted),
            'rollout':rollout,'proof':admission,'platform':platform.platform(),'python':sys.version.split()[0],
            'claim':'exact native observations match rational semantics; pruned and FP32 errors are measured and bounded for these cases; no nonlinear plant stability claim',
            'timing_scope':'input conversion and all common-bank plus rollout controller calls; dataset parsing, build and Lean checking excluded; pruning admission is audited offline, not included in execution timings',
            'memory_scope':'peak RSS of each complete process, including Python/PyTorch runtime for FP32',
            'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,dataset,exact_binary,pruned_binary,root/'benchmark.lean')}}
    import torch
    from omega_selfhost.driver import PACKAGE
    report['torch_version']=torch.__version__
    report['c_compiler']=subprocess.check_output(['cc','--version'],text=True).splitlines()[0]
    report['c_flags']=['-std=gnu11','-O2','-s','-lgmp']
    report['warmup_processes_per_backend']=1
    report['controller_calls_per_measured_process']=samples+steps
    report['pruning_header_sha256']=hashlib.sha256((PACKAGE/'rational_pruning.h').read_bytes()).hexdigest()
    for path in (root/'exact.c',root/'pruned.c'):
        report['artifacts'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    def decision(scores):return max(range(len(scores)),key=lambda i:Q(scores[i]))
    report['changed_decisions']={mode:sum(decision(a)!=decision(b) for a,b in zip(outcomes[mode]['bank'],outcomes['exact']['bank'])) for mode in ('pruned','fp32')}
    (root/'observations.json').write_bytes(encode(outcomes))
    (root/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    return report


def plot(report, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    modes=['exact','pruned','fp32'];labels=['C/GMP exact','C/GMP pruned','PyTorch FP32']
    figure,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    latency=[report['measurements'][mode]['median_controller_ns']/1000 for mode in modes]
    memory=[report['measurements'][mode]['process_peak_rss_kib']/1024 for mode in modes]
    errors=[float(Q(report['common_input_max_error'][mode])) for mode in modes]
    axes[0].bar(labels,latency);axes[0].set_ylabel('Microseconds / controller call');axes[0].set_yscale('log')
    axes[1].bar(labels,memory);axes[1].set_ylabel('Complete process peak RSS (MiB)');axes[1].set_yscale('log')
    axes[2].bar(labels,errors);axes[2].set_ylabel('Maximum absolute error on common inputs')
    for axis in axes:axis.tick_params(axis='x',labelrotation=25)
    axes[2].annotate('0 (exact)',(0,0),xytext=(0,8),textcoords='offset points',ha='center')
    figure.suptitle('Linearized inverted pendulum: measured inference, memory and numerical error')
    figure.savefig(destination);plt.close(figure)
    destination=Path(destination)
    if destination.suffix=='.svg':
        destination.write_text('\n'.join(line.rstrip() for line in destination.read_text().splitlines())+'\n')


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--samples',type=int,default=32);parser.add_argument('--steps',type=int,default=64)
    parser.add_argument('--repetitions',type=int,default=3);parser.add_argument('--max-denominator',type=int,default=65536)
    parser.add_argument('--plot',action='store_true',help='Write a standalone comparison.svg using matplotlib')
    args=parser.parse_args()
    report=run(args.output,samples=args.samples,steps=args.steps,repetitions=args.repetitions,max_denominator=args.max_denominator)
    if args.plot:plot(report,args.output/'comparison.svg')
    print(json.dumps(report,sort_keys=True,indent=2))


if __name__=='__main__':main()
