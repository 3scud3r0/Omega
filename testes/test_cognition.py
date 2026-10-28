import copy
import ctypes
from fractions import Fraction as Q
from pathlib import Path
import subprocess
import pytest
from omega_cognition.linear import LinearContext
from omega_cognition.memory import plan_buffers
from omega_cognition.scheduler import FairScheduler
from omega_cognition.glass import orthogonal_basis,certify_concepts,trace,replay,native_trace

GRAPH={'inputs':1,'nodes':[
    {'op':'affine','terms':[[0,'2']],'bias':'1'},
    {'op':'relu','input':1},
    {'op':'affine','terms':[[2,'1/2']],'bias':'-1'}],'outputs':[3]}


def test_linear_moves_borrows_and_consumption():
    ctx=LinearContext(64);ctx.allocate('x',32);borrow=ctx.borrow('x')
    with pytest.raises(ValueError):ctx.move('x','y')
    with pytest.raises(ValueError):ctx.consume('x')
    with pytest.raises(ValueError):ctx.borrow('x',mutable=True)
    ctx.release_borrow(borrow);ctx.move('x','y')
    with pytest.raises(ValueError):ctx.consume('x')
    mutable=ctx.borrow('y',mutable=True)
    with pytest.raises(ValueError):ctx.borrow('y')
    ctx.release_borrow(mutable)
    with pytest.raises(ValueError):ctx.release_borrow(mutable)
    ctx.consume('y');assert ctx.finish()['remaining_bytes']==0


def test_buffer_plan_disjoint_for_every_shared_slot():
    plan=plan_buffers(GRAPH,bytes_per_value=8)
    assert plan['bytes']<plan['unreused_bytes'] and plan['admission']
    for i,slot in enumerate(plan['slots']):
        for j in range(i):
            if plan['slots'][j]==slot:assert plan['last_uses'][j]<plan['starts'][i]


def test_host_fairness_overrides_starving_neural_priorities():
    schedule=FairScheduler([('a',12),('b',3),('c',2)],max_wait=2)
    result=schedule.run(lambda tasks:tasks[0][0])
    assert result['steps']==17 and result['admission']
    assert any(e['reason']=='fairness override' for e in result['trace'])
    assert all(e['before']-e['after']==1 for e in result['trace'])


def test_concept_labels_need_grounded_logic():
    assert orthogonal_basis([[1,0],[0,1]])['admission']
    with pytest.raises(ValueError):orthogonal_basis([[1,1],[0,1]])
    graph={'inputs':1,'nodes':[{'op':'affine','terms':[[0,'1']],'bias':'0'}],'outputs':[1]}
    proof=certify_concepts(graph,[[1]],[{'name':'nonnegative sensor','ensures':'result>=0'}],{'input_0':'self>=0'})
    assert proof['concepts'][0]['proof']['admission']
    with pytest.raises(ValueError):certify_concepts(graph,[[1]],[{'name':'positive','ensures':'result>0'}],{'input_0':'true'})


def test_glass_replay_and_tampering():
    record=trace(GRAPH,['-1'],annotations={2:'clipped sensor'},thresholds={3:'-1/2'})
    assert replay(record)['outputs']==['-1']
    assert record['events'][1]['branch']=='zero'
    changed=copy.deepcopy(record);changed['events'][0]['value']='99'
    with pytest.raises(ValueError):replay(changed)


def test_native_exports_intermediate_values_and_checked_thresholds(tmp_path):
    result=native_trace(GRAPH,['1/4'],tmp_path/'trace',[[-1,1]],thresholds={3:'0'})
    assert result['trace']['outputs']==['-1/4']
    assert result['native_admission']['native_trace']==['1/4','3/2','3/2','-1/4']
    assert replay(result['trace'])['valid']


def test_standalone_checkpoint_compiles_runs_without_heap_or_python(tmp_path):
    import torch
    from omega_cognition.standalone import export
    model=torch.nn.Sequential(torch.nn.Linear(1,1),torch.nn.ReLU(),torch.nn.Linear(1,1))
    with torch.no_grad():
        model[0].weight.fill_(2);model[0].bias.fill_(1)
        model[2].weight.fill_(0.5);model[2].bias.fill_(-1)
    checkpoint=tmp_path/'weights.pt';torch.save(model.state_dict(),checkpoint)
    architecture=[{'type':'linear','in':1,'out':1,'bias':True},{'type':'relu'},{'type':'linear','in':1,'out':1,'bias':True}]
    result=export(checkpoint,architecture,tmp_path/'standalone',input_bounds=[[-1,1]],output_bounds=[[-1,1]],input_scale=4)
    source=Path(result['source']);assert 'malloc' not in source.read_text()
    assert 'buffer[' in source.read_text() and result['memory_plan']['admission']
    library=tmp_path/'model.so'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-ffreestanding','-shared','-fPIC',str(source),'-o',str(library)],check=True,capture_output=True)
    native=ctypes.CDLL(str(library)).omega_edge
    native.argtypes=[ctypes.POINTER(ctypes.c_int64),ctypes.POINTER(ctypes.c_int64)]
    for x in range(-4,5):
        inputs=(ctypes.c_int64*1)(x);outputs=(ctypes.c_int64*1)()
        assert native(inputs,outputs)==0
        expected=max(Q(0),Q(2*x,4)+1)/2-1
        assert Q(outputs[0],result['output_scales'][0])==expected
    assert native((ctypes.c_int64*1)(5),(ctypes.c_int64*1)())==-2
    symbols=subprocess.check_output(['nm','-u',str(library)],text=True)
    assert not any(name in symbols for name in ('malloc','free','GMP','Py_'))


def test_freestanding_headers_overflow_and_expired_handles(tmp_path):
    root=Path(__file__).resolve().parents[1];source=tmp_path/'kernel.c'
    source.write_text('''#include <assert.h>
#include "bounded_rational.h"
#include "proof_microkernel.h"
int main(void){
 omega_q64 q,a={INT64_MAX,1},b={1,1};
 assert(omega_q64_add(&q,a,b)==OMEGA_Q_OVERFLOW);
 a=(omega_q64){1,3};b=(omega_q64){2,3};
 assert(omega_q64_add(&q,a,b)==0 && q.numerator==1 && q.denominator==1);
 assert(omega_q64_mul(&q,a,b)==0 && q.numerator==2 && q.denominator==9);
 assert(omega_q64_div(&q,a,b)==0 && q.numerator==1 && q.denominator==2);
 assert(omega_q64_div(&q,a,(omega_q64){0,1})==OMEGA_Q_ZERO_DENOM);
 unsigned __int128 high=(unsigned __int128)1<<127;
 __int128 lowest=-(__int128)(high-1)-1;
 assert(omega_q64_make(&q,lowest,high)==0 && q.numerator==-1 && q.denominator==1);
 unsigned char pool[32];omega_microkernel k;omega_kernel_init(&k,pool,sizeof pool);
 omega_handle h,m,next;void *pointer;
 assert(!omega_kernel_allocate(&k,1,16,&h));
 assert(!omega_kernel_borrow(&k,h,0,&pointer));
 assert(omega_kernel_move(&k,h,2,&m));assert(omega_kernel_consume(&k,h));
 assert(!omega_kernel_unborrow(&k,h,0));assert(!omega_kernel_move(&k,h,2,&m));
 assert(omega_kernel_borrow(&k,h,0,&pointer));assert(!omega_kernel_consume(&k,m));
 assert(!omega_kernel_allocate(&k,1,32,&next));assert(omega_kernel_consume(&k,m));
 assert(!omega_kernel_consume(&k,next));return 0;
}''')
    binary=tmp_path/'kernel'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(root/'omega_selfhost'),str(source),'-o',str(binary)],check=True,capture_output=True)
    subprocess.run([binary],check=True,capture_output=True)
