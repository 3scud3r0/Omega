#include "flat_ast_eval.cuh"
namespace omega_gpu {
__global__ void evaluate_flat_asts_kernel(
 const uint16_t *__restrict__ op_codes,const int32_t *__restrict__ left_child,
 const int32_t *__restrict__ right_child,const Rational64 *__restrict__ inputs,
 Rational64 *__restrict__ outputs,uint8_t *__restrict__ error_flags,
 Rational64 *__restrict__ scratch,const Rational64 *__restrict__ constants,
 const uint32_t *__restrict__ node_counts,const uint32_t *__restrict__ output_refs,EvalShape shape,uint64_t *evaluated_nodes){
 uint64_t job=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;
 if(job<(uint64_t)shape.count*shape.examples){
  uint32_t c=shape.first+uint32_t(job)/shape.examples;
  uint32_t executed=0;
  uint8_t status=evaluate_job(op_codes,left_child,right_child,inputs,outputs,scratch,constants,node_counts,output_refs,shape,uint32_t(job),&executed);
  atomicAdd(reinterpret_cast<unsigned long long*>(evaluated_nodes),(unsigned long long)executed);
  // One byte per candidate/example prevents racing byte read-modify-writes.
  error_flags[(uint64_t)c*shape.examples+uint32_t(job)%shape.examples]=status;
 }
}
}
