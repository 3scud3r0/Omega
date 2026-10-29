#include "../cuda/flat_ast_eval.cuh"
#include <cuda_runtime.h>
using namespace omega_gpu;
// Each warp evaluates 32 independent candidate/example jobs. Dependencies in an
// individual topological AST remain ordered; no fictitious parallel dependency
// execution or fixed throughput guarantee is attached to this kernel.
extern "C" __global__ void omega_warp_evaluate_kernel(const uint16_t *ops,const int32_t *left,const int32_t *right,const Rational64 *inputs,Rational64 *outputs,Rational64 *scratch,const Rational64 *constants,const uint32_t *counts,const uint32_t *roots,uint8_t *errors,EvalShape shape,uint64_t *evaluated){
 uint32_t job=blockIdx.x*blockDim.x+threadIdx.x;uint32_t executed=0;
 uint8_t status=0;bool active=job<(uint64_t)shape.count*shape.examples;
 if(active){status=evaluate_job(ops,left,right,inputs,outputs,scratch,constants,counts,roots,shape,job,&executed);uint32_t c=shape.first+job/shape.examples;errors[(uint64_t)c*shape.examples+job%shape.examples]=status;}
 unsigned mask=__activemask();
 for(int offset=16;offset;offset/=2)executed+=__shfl_down_sync(mask,executed,offset);
 if((threadIdx.x&31)==0)atomicAdd((unsigned long long*)evaluated,(unsigned long long)executed);
}
