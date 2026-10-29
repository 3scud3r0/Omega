#ifndef OMEGA_PTX_ALGEBRA_OPS_CUH
#define OMEGA_PTX_ALGEBRA_OPS_CUH
#include "../cuda/rational_alu.cuh"
namespace omega_cuda_native {
struct WideProduct {uint64_t low,high;};
OMEGA_HD WideProduct multiply_wide(uint64_t a,uint64_t b){
#ifdef __CUDA_ARCH__
 return {a*b,__umul64hi(a,b)};
#else
 unsigned __int128 p=(unsigned __int128)a*b;return {uint64_t(p),uint64_t(p>>64)};
#endif
}
OMEGA_HD omega_gpu::Checked exact_fma(omega_gpu::Rational64 a,omega_gpu::Rational64 b,omega_gpu::Rational64 sum){
 auto p=omega_gpu::rat_mul(a,b);if(p.error)return p;return omega_gpu::rat_add(sum,p.value);
}
// Integer SIMT arithmetic. NVIDIA floating-point Tensor Cores cannot implement
// arbitrary exact rational multiplication without a different encoded algorithm.
}
#endif
