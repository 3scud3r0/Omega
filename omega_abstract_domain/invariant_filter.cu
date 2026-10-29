#include <cuda_runtime.h>
#include "interval_domain.cuh"
namespace omega_gpu {
__global__ void verify_contract_invariants_kernel(const uint16_t *__restrict__ ast_nodes,
 const RationalInterval *__restrict__ precond_intervals,const RationalInterval *__restrict__ invariant_limits,
 uint8_t *__restrict__ is_admissible_mask,const int32_t *__restrict__ left,const int32_t *__restrict__ right,
 RationalInterval *__restrict__ scratch,const Rational64 *__restrict__ constants,
 const uint32_t *__restrict__ counts,const uint32_t *__restrict__ roots,uint8_t *__restrict__ errors,EvalShape shape){
 uint32_t c=shape.first+blockIdx.x*blockDim.x+threadIdx.x;if(c>=shape.first+shape.count)return;
 uint8_t status=filter_candidate(ast_nodes,left,right,precond_intervals,invariant_limits,scratch,constants,counts,roots,shape,c);
 errors[c]=status;is_admissible_mask[c]=status==OK;
}
}
