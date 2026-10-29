#include <cuda_runtime.h>
#include "ptx_algebra_ops.cuh"
using namespace omega_gpu;
extern "C" __global__ void omega_rational_gemm_kernel(const Rational64 *a,const Rational64 *b,Rational64 *out,uint8_t *errors,uint32_t rows,uint32_t inner,uint32_t cols){
 uint64_t index=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;
 if(index>=(uint64_t)rows*cols)return;
 Rational64 sum={0,1};uint8_t status=OK;uint32_t row=index/cols,col=index%cols;
 for(uint32_t k=0;k<inner;k++){
  auto result=omega_cuda_native::exact_fma(a[(uint64_t)row*inner+k],b[(uint64_t)k*cols+col],sum);
  if(result.error){status=result.error;break;}sum=result.value;
 }
 out[index]=status?Rational64{0,1}:sum;errors[index]=status;
}
extern "C" int omega_rational_gemm(const Rational64 *a,const Rational64 *b,Rational64 *out,uint8_t *errors,uint32_t rows,uint32_t inner,uint32_t cols,cudaStream_t stream){
 if(!a||!b||!out||!errors||!rows||!inner||!cols||rows>4096||inner>4096||cols>4096||(uint64_t)rows*cols>1048576)return 1;
 omega_rational_gemm_kernel<<<((uint64_t)rows*cols+255)/256,256,0,stream>>>(a,b,out,errors,rows,inner,cols);
 return cudaGetLastError()==cudaSuccess?0:2;
}
