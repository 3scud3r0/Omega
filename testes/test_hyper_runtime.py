import ctypes as C
from pathlib import Path
import subprocess
from fractions import Fraction as Q
from omega_runtime_verified import emit


def test_real_edge_activations_are_recorded_in_fixed_trace_storage(tmp_path):
    graph={'inputs':1,'nodes':[{'op':'affine','terms':[[0,'2']],'bias':'1'},
             {'op':'relu','input':1},{'op':'affine','terms':[[2,'1/2']],'bias':'-1'}],'outputs':[3]}
    result=emit(graph,[[-1,1]],[[-1,1]],tmp_path/'model',input_scale=4)
    root=Path(result['source']).parent
    (root/'test.c').write_text('''#include <assert.h>
#include <stdint.h>
#include "proof_envelope.h"
int omega_edge_traced(const int64_t*,int64_t*,OmegaTraceRing*,uint64_t);
int main(void){
 OmegaTraceEvent storage[8],event;OmegaTraceRing ring;
 assert(!omega_trace_init(&ring,storage,8));int64_t input[1]={-4},output[1];
 assert(!omega_edge_traced(input,output,&ring,73));assert(ring.count==4&&ring.dropped==0);
 assert(!omega_trace_get(&ring,2,&event));assert(event.operation==7&&event.branch==0&&event.numerator==0&&event.inference_cycle==73);
 input[0]=4;assert(!omega_edge_traced(input,output,&ring,74));
 assert(!omega_trace_get(&ring,6,&event));assert(event.operation==7&&event.branch==1);
 assert(!omega_edge_traced(input,output,&ring,75));assert(ring.count==8&&ring.dropped==4);
 assert(!omega_trace_get(&ring,0,&event));assert(event.sequence==4&&event.inference_cycle==74);
 ring.sequence=UINT64_MAX;assert(omega_trace_record(&ring,76,0,0,0,0,1)==-2&&ring.halted);
 assert(omega_trace_record(&ring,76,0,0,0,0,1));return 0;
}''')
    binary=root/'test'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',str(root/'test.c'),str(root/'model.c'),str(root/'glass_box_trace.c'),'-o',str(binary)],check=True,capture_output=True)
    subprocess.run([binary],check=True,capture_output=True)
    assert result['trace_event_count']==4
